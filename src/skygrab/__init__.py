"""SkyGrab — Aggressive multi-source satellite data harvester."""
__version__ = "0.1.0"
__author__ = "kase"
__license__ = "MIT"

from skygrab.engine import DownloadEngine
from skygrab.sources import EumetsatSource, NoaaSource, ProductInfo

__all__ = [
    "__version__",
    "DownloadEngine",
    "EumetsatSource",
    "NoaaSource",
    "ProductInfo",
]
