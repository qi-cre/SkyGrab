"""线程安全的进度聚合。

下载线程每收到一块数据就调用 update()，ProgressReporter 以固定
间隔把整个进度快照通过回调 post() 推给 UI 层，避免淹没 TUI 消息队列。
"""
from __future__ import annotations

import threading
import time
from typing import Callable


PROGRESS_INTERVAL = 0.1  # 秒


class ProgressReporter:
    def __init__(
        self,
        post: Callable[[dict], None],
        interval: float = PROGRESS_INTERVAL,
    ) -> None:
        self.post = post
        self.interval = interval
        self.lock = threading.Lock()
        self.data: dict[str, dict] = {}
        self.last_report = 0.0

    def register(self, product_id: str, total: int) -> None:
        with self.lock:
            self.data[product_id] = {
                "done": 0,
                "total": total,
                "start": time.monotonic(),
            }

    def update(self, product_id: str, n: int) -> None:
        snapshot = None
        with self.lock:
            d = self.data.get(product_id)
            if d is None:
                return
            d["done"] += n
            now = time.monotonic()
            if now - self.last_report >= self.interval:
                self.last_report = now
                snapshot = {pid: dict(v) for pid, v in self.data.items()}
        if snapshot is not None:
            self.post(snapshot)

    def finish(self, product_id: str) -> None:
        with self.lock:
            d = self.data.get(product_id)
            if d:
                d["done"] = d["total"]
            snapshot = {pid: dict(v) for pid, v in self.data.items()}
        self.post(snapshot)

    def forget(self, product_id: str) -> None:
        with self.lock:
            self.data.pop(product_id, None)
