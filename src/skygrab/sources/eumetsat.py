"""EUMETSAT Data Store 数据源。"""
from __future__ import annotations

from typing import Any, Callable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from skygrab.sources.base import DataSource, ProductInfo


EUMETSAT_API_BASE = "https://api.eumetsat.int"
EUMETSAT_SEARCH_URL = f"{EUMETSAT_API_BASE}/data/search-products"


class EumetsatSource(DataSource):
    name = "eumetsat"

    def __init__(
        self,
        api_key: str,
        on_log: Optional[Callable[[str], None]] = None,
        max_workers: int = 32,
    ) -> None:
        self.api_key = api_key
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
        s.mount("http://", adapter)
        s.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "SkyGrab/0.1 (+https://github.com/kase/skygrab)",
        })
        return s

    def search(self, **kwargs: Any) -> list[ProductInfo]:
        collection_id = kwargs["collection_id"]
        bbox = kwargs.get("bbox")
        start = kwargs.get("start")
        end = kwargs.get("end")
        limit = int(kwargs.get("limit", 20))

        params: dict[str, str] = {
            "pi": collection_id,
            "format": "json",
            "size": str(limit),
        }
        if bbox:
            params["bbox"] = bbox
        if start:
            params["dtstart"] = start
        if end:
            params["dtend"] = end

        self.on_log(f"Searching [cyan]{collection_id}[/] ...")
        r = self.session.get(EUMETSAT_SEARCH_URL, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        out: list[ProductInfo] = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            links = feat.get("links", [])
            dl = next(
                (
                    link["href"]
                    for link in links
                    if link.get("rel") == "enclosure"
                    or "download" in link.get("title", "").lower()
                ),
                None,
            )
            if not dl:
                continue
            out.append(
                ProductInfo(
                    product_id=props.get("identifier", feat.get("id", "")),
                    title=props.get("title", ""),
                    download_url=dl,
                )
            )
        self.on_log(f"Found [green]{len(out)}[/] products.")
        return out
