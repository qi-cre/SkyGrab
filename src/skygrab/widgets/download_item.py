"""单个产品的下载进度卡片。"""
from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, ProgressBar, Static


class DownloadItem(Vertical):
    """显示一个产品的进度、速度、已完成字节。"""

    def __init__(self, product_id: str) -> None:
        super().__init__(classes="dl-item")
        self.product_id = product_id
        self._pb = ProgressBar(total=100, show_eta=False)
        self._stats = Static("Waiting...", classes="dl-stats")
        self._last_done = 0
        self._last_time = time.monotonic()
        self._last_speed = 0.0

    def compose(self) -> ComposeResult:
        yield Label(self.product_id, classes="dl-title")
        yield self._pb
        yield self._stats

    def update_progress(self, done: int, total: int) -> None:
        now = time.monotonic()
        dt = now - self._last_time
        if dt >= 0.3:
            self._last_speed = (done - self._last_done) / dt
            self._last_done = done
            self._last_time = now

        pct = 100 * done / total if total else 0
        try:
            self._pb.update(progress=pct)
            self._stats.update(
                f"{done / 1e6:.1f}/{total / 1e6:.1f} MB "
                f"@ {self._last_speed / 1e6:.1f} MB/s"
            )
        except Exception:
            # 控件已被移除（例如切换页面），静默忽略
            pass

    def mark_done(self, path: str) -> None:
        try:
            self._pb.update(progress=100)
            self._stats.update(f"[green]done[/] {path}")
        except Exception:
            pass

    def mark_error(self, err: str) -> None:
        try:
            self._stats.update(f"[red]error: {err}[/]")
        except Exception:
            pass
