"""数据源注册表。"""
from skygrab.sources.base import ChunkTask, DataSource, ProductInfo
from skygrab.sources.eumetsat import EumetsatSource
from skygrab.sources.noaa import NOAA_PUBLIC_BUCKETS, NoaaSource

__all__ = [
    "ChunkTask",
    "DataSource",
    "ProductInfo",
    "EumetsatSource",
    "NoaaSource",
    "NOAA_PUBLIC_BUCKETS",
]
