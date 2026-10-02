"""下载引擎：分块并发、全局限速、断点续传。"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

from skygrab.progress import ProgressReporter
from skygrab.ratelimit import GlobalRateLimiter
from skygrab.sources.base import ChunkTask, DataSource, ProductInfo
from skygrab.util import human_size, safe_filename


RETRY_MAX = 6
RETRY_BACKOFF = 1.5
READ_CHUNK = 256 * 1024


class DownloadEngine:
    """把 ProductInfo 拆成块，多线程并行拉取，写入 .part 文件。"""

    def __init__(
        self,
        source: DataSource,
        output_dir: Path | str = "./downloads",
        max_workers: int = 32,
        chunk_size: int = 8 * 1024 * 1024,
        rate_limit: float = 200 * 1024 * 1024,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[dict], None]] = None,
        on_product_start: Optional[Callable[[str, int, int], None]] = None,
        on_product_done: Optional[Callable[[str, str], None]] = None,
        on_product_error: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.source = source
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.rate_limiter = GlobalRateLimiter(rate_limit)

        self.on_log = on_log or (lambda _: None)
        self.on_product_start = on_product_start or (lambda *a: None)
        self.on_product_done = on_product_done or (lambda *a: None)
        self.on_product_error = on_product_error or (lambda *a: None)
        self.progress = ProgressReporter(on_progress or (lambda _: None))

        self._cancelled = threading.Event()
        self._state_lock = threading.Lock()

    # ── 取消控制 ──────────────────────────────

    def cancel(self) -> None:
        self._cancelled.set()

    def reset_cancel(self) -> None:
        self._cancelled.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    # ── 下载主流程 ────────────────────────────

    def download(self, product: ProductInfo) -> Optional[Path]:
        """下载一个产品，返回最终文件路径；失败或取消返回 None。"""
        if self._cancelled.is_set():
            return None

        # 1. 确定文件大小
        try:
            size = self._resolve_size(product)
        except Exception as e:
            self.on_product_error(product.product_id, f"resolve size: {e}")
            return None
        if size <= 0:
            self.on_product_error(product.product_id, "unknown size")
            return None

        # 2. 规划路径（NOAA 按 bucket 分子目录）
        subdir = self.output_dir
        if product.bucket:
            subdir = self.output_dir / product.bucket
        subdir.mkdir(parents=True, exist_ok=True)
        final_path = subdir / safe_filename(product.product_id)
        part_path = final_path.with_suffix(final_path.suffix + ".part")
        state_path = final_path.with_suffix(final_path.suffix + ".state.json")

        # 3. 断点续传：读取已完成块
        completed: set[int] = set()
        if state_path.exists() and part_path.exists():
            try:
                data = json.loads(state_path.read_text())
                completed = set(data.get("completed", []))
            except Exception:
                completed = set()

        # 4. 规划块
        chunks = self._plan_chunks(product, size)
        self.progress.register(product.product_id, size)
        self.on_product_start(product.product_id, size, len(chunks))
        self.on_log(
            f"Start: [bold]{product.product_id}[/] | "
            f"{len(chunks)} chunks | {human_size(size)} | "
            f"{self.max_workers} threads"
        )

        # 5. 预分配文件（只在新下载时）
        if not part_path.exists():
            with open(part_path, "wb") as f:
                f.seek(size - 1)
                f.write(b"\0")

        # 6. 并发下载所有块
        try:
            self._run_chunks(
                product, chunks, completed, part_path, state_path,
            )
        except _Cancelled:
            self.on_product_error(product.product_id, "cancelled")
            return None
        except Exception as e:
            self.on_product_error(product.product_id, str(e))
            return None

        # 7. 收尾
        part_path.rename(final_path)
        if state_path.exists():
            state_path.unlink()
        self.progress.finish(product.product_id)
        self.on_product_done(product.product_id, str(final_path))
        return final_path

    # ── 内部：块执行 ──────────────────────────

    def _run_chunks(
        self,
        product: ProductInfo,
        chunks: list[ChunkTask],
        completed: set[int],
        part_path: Path,
        state_path: Path,
    ) -> None:
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futs = {}
            for task in chunks:
                if task.index in completed:
                    # 已完成的块，直接计入进度
                    self.progress.update(product.product_id, task.length)
                    continue
                futs[ex.submit(self._download_chunk, task, part_path)] = task

            for fut in as_completed(futs):
                if self._cancelled.is_set():
                    ex.shutdown(wait=False, cancel_futures=True)
                    raise _Cancelled()
                try:
                    idx = fut.result()
                except _Cancelled:
                    ex.shutdown(wait=False, cancel_futures=True)
                    raise
                except Exception as e:
                    task = futs[fut]
                    raise RuntimeError(f"chunk {task.index}: {e}") from e

                # 记录已完成块，用于断点续传
                with self._state_lock:
                    completed.add(idx)
                    try:
                        state_path.write_text(
                            json.dumps({"completed": sorted(completed)})
                        )
                    except OSError:
                        pass

    def _download_chunk(self, task: ChunkTask, part_path: Path) -> int:
        """下载单个块。成功返回 task.index。"""
        if self._cancelled.is_set():
            raise _Cancelled()

        headers = {
            "Range": f"bytes={task.offset}-{task.offset + task.length - 1}"
        }
        session = self.source.session

        last_err: Optional[Exception] = None
        for attempt in range(RETRY_MAX):
            if self._cancelled.is_set():
                raise _Cancelled()
            try:
                r = session.get(
                    task.url, headers=headers, stream=True, timeout=120,
                )
                r.raise_for_status()

                # S3 可能忽略 Range 返回 200。若 index > 0，说明 index 0
                # 已经拿到整个文件，跳过即可。
                if r.status_code == 200 and task.index > 0:
                    self.progress.update(task.product_id, task.length)
                    return task.index

                fd = os.open(str(part_path), os.O_WRONLY | os.O_CREAT)
                try:
                    write_off = task.offset
                    for data in r.iter_content(chunk_size=READ_CHUNK):
                        if not data:
                            continue
                        if self._cancelled.is_set():
                            raise _Cancelled()
                        self.rate_limiter.consume(len(data))
                        _pwrite(fd, data, write_off)
                        write_off += len(data)
                        self.progress.update(task.product_id, len(data))
                finally:
                    os.close(fd)
                return task.index
            except _Cancelled:
                raise
            except Exception as e:
                last_err = e
                if attempt == RETRY_MAX - 1:
                    break
                time.sleep(RETRY_BACKOFF ** attempt)

        raise last_err or RuntimeError("unknown error")

    # ── 内部：辅助 ────────────────────────────

    def _resolve_size(self, product: ProductInfo) -> int:
        if product.file_size > 0:
            return product.file_size
        r = self.source.session.head(
            product.download_url, allow_redirects=True, timeout=30,
        )
        r.raise_for_status()
        return int(r.headers.get("Content-Length", 0))

    def _plan_chunks(self, product: ProductInfo, size: int) -> list[ChunkTask]:
        if size <= self.chunk_size:
            return [
                ChunkTask(0, 0, size, product.download_url, product.product_id)
            ]
        out: list[ChunkTask] = []
        offset = 0
        idx = 0
        while offset < size:
            ln = min(self.chunk_size, size - offset)
            out.append(ChunkTask(
                idx, offset, ln, product.download_url, product.product_id,
            ))
            offset += ln
            idx += 1
        return out


class _Cancelled(Exception):
    """内部取消信号。"""


def _pwrite(fd: int, data: bytes, offset: int) -> None:
    """优先使用 pwrite（原子偏移写入），不支持则退回到 lseek+write。"""
    try:
        os.pwrite(fd, data, offset)
    except (AttributeError, OSError):
        os.lseek(fd, offset, os.SEEK_SET)
        os.write(fd, data)
