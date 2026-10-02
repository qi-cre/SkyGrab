"""数据源抽象基类与共享数据模型。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProductInfo:
    """一个可下载的产品。

    不同数据源的字段略有差异，用 extra 装源特有字段。
    """
    product_id: str
    title: str
    download_url: str
    file_size: int = 0
    bucket: str = ""
    key: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkTask:
    """一个待下载的块。"""
    index: int
    offset: int
    length: int
    url: str
    product_id: str


class DataSource(ABC):
    """所有数据源的统一接口。"""

    name: str = "abstract"

    @abstractmethod
    def search(self, **kwargs: Any) -> list[ProductInfo]:
        """按参数检索产品，返回产品列表。"""
        raise NotImplementedError

    def close(self) -> None:
        """释放资源。默认无操作。"""
