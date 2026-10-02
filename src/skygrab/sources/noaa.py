"""NOAA AWS NODD 公开桶数据源。

匿名访问，无需 AWS 凭证。使用 S3 ListObjectsV2 REST API 枚举对象。
注意：这些是已定标的产品（netCDF），不是原始 baseband（IQ）。
"""
from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Callable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from skygrab.sources.base import DataSource, ProductInfo


NOAA_PUBLIC_BUCKETS: dict[str, str] = {
    "goes16": "noaa-goes16",
    "goes17": "noaa-goes17",
    "goes18": "noaa-goes18",
    "goes19": "noaa-goes19",
    "n20": "noaa-nesdis-n20-pds",
    "n21": "noaa-nesdis-n21-pds",
    "snpp": "noaa-nesdis-snpp-pds",
}

_S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


class NoaaSource(DataSource):
    name = "noaa"

    def __init__(
        self,
        on_log: Optional[Callable[[str], None]] = None,
        max_workers: int = 32,
    ) -> None:
        self.on_log = on_log or (lambda _: None)
        self.session = self._build_session(max_workers)

    def _build_session(self, max_workers: int) -> requests.Session:
        s = requests.Session()
        retry = Retry(
            total=6,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=max_workers,
            pool_maxsize=max_workers * 2,
        )
        s.mount("https://", adapter)
        # 关键：S3 公开桶不接受 Authorization: Bearer 头，
        # 所以这个 session 完全不设置认证头。
        s.headers.update({
            "User-Agent": "SkyGrab/0.1 (+https://github.com/kase/skygrab)",
        })
        return s

    def search(self, **kwargs: Any) -> list[ProductInfo]:
        satellite = kwargs.get("satellite", "goes16")
        product = kwargs.get("product", "")
        year = kwargs.get("year")
        day = kwargs.get("day_of_year")
        hour = kwargs.get("hour")

        bucket = NOAA_PUBLIC_BUCKETS.get(satellite, satellite)
        parts: list[str] = []
        if product:
            parts.append(product)
        if year:
            parts.append(str(year))
        if day:
            parts.append(f"{int(day):03d}")
        if hour is not None:
            parts.append(f"{int(hour):02d}")
        prefix = "/".join(parts)

        self.on_log(f"List s3://{bucket}/{prefix}")
        return self._list_bucket(bucket, prefix)

    def _list_bucket(self, bucket: str, prefix: str) -> list[ProductInfo]:
        base = f"https://{bucket}.s3.amazonaws.com/"
        q = urllib.parse.urlencode({
            "list-type": "2",
            "prefix": prefix,
            "max-keys": "1000",
        })
        r = self.session.get(base + "?" + q, timeout=60)
        r.raise_for_status()

        root = ET.fromstring(r.text)
        out: list[ProductInfo] = []
        for c in root.findall(".//s3:Contents", _S3_NS):
            key_el = c.find("s3:Key", _S3_NS)
            size_el = c.find("s3:Size", _S3_NS)
            if key_el is None or key_el.text is None:
                continue
            key = key_el.text
            size = int(size_el.text) if size_el is not None and size_el.text else 0
            out.append(
                ProductInfo(
                    product_id=key.rsplit("/", 1)[-1],
                    title=key,
                    download_url=base + urllib.parse.quote(key, safe="/"),
                    file_size=size,
                    bucket=bucket,
                    key=key,
                )
            )

        self.on_log(f"Found [green]{len(out)}[/] objects.")
        return out
