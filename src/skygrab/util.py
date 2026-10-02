"""通用工具函数。"""
from __future__ import annotations

import re
from pathlib import Path


_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, max_len: int = 200) -> str:
    """把任意字符串转成跨平台安全的文件名。

    - 替换 Windows/Unix 非法字符
    - 去掉首尾空格和点
    - 长度截断（保留扩展名）
    """
    cleaned = _ILLEGAL.sub("_", name).strip(" .")
    if len(cleaned) <= max_len:
        return cleaned or "unnamed"

    # 保留扩展名
    p = Path(cleaned)
    ext = p.suffix
    keep = max_len - len(ext)
    if keep <= 0:
        return cleaned[:max_len]
    return p.stem[:keep] + ext


def human_size(n: int) -> str:
    """把字节数转成人类可读字符串。"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def human_speed(bps: float) -> str:
    return human_size(int(bps)) + "/s"


def is_s3_url(url: str) -> bool:
    """判断 URL 是否指向 AWS S3。"""
    return "s3.amazonaws.com" in url or ".s3." in url
