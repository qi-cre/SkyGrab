"""全局令牌桶速率限制器。

在全部下载线程间共享，防止多线程把服务端打挂。
"""
from __future__ import annotations

import threading
import time


class GlobalRateLimiter:
    """线程安全的令牌桶。

    rate 单位为字节/秒。传入 float('inf') 表示不限速。
    """

    def __init__(self, rate_bytes_per_sec: float) -> None:
        self.rate = rate_bytes_per_sec
        self.tokens = 0.0 if rate_bytes_per_sec == float("inf") else rate_bytes_per_sec
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, nbytes: int) -> None:
        """阻塞直到桶中有 nbytes 个令牌。"""
        if self.rate == float("inf"):
            return

        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(
                    self.rate,
                    self.tokens + elapsed * self.rate,
                )
                self.last_refill = now

                if self.tokens >= nbytes:
                    self.tokens -= nbytes
                    return

                wait = (nbytes - self.tokens) / self.rate

            # 短暂让步，避免死等
            time.sleep(min(wait, 0.5))
