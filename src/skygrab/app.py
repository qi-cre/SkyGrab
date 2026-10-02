"""SkyGrab Textual TUI。"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection
from textual import work

from skygrab.engine import DownloadEngine
from skygrab.sources.eumetsat import EumetsatSource
from skygrab.sources.noaa import NOAA_PUBLIC_BUCKETS, NoaaSource
from skygrab.widgets import DownloadItem


class SkyGrabApp(App):
    CSS = """
    Screen { layout: vertical; }

    #top-bar {
        height: 3;
        padding: 0 1;
        layout: horizontal;
    }
    #top-bar Input { margin: 0 1 0 0; height: 3; }
    #sel-source    { width: 13; }
    #in-collection { width: 22; }
    #in-bbox       { width: 16; }
    #in-start      { width: 18; }
    #in-end        { width: 18; }
    #in-limit      { width: 5;  }
    #in-noaa-sat   { width: 10; }
    #in-noaa-prod  { width: 18; }
    #in-noaa-year  { width: 6;  }
    #in-noaa-day   { width: 5;  }
    #in-noaa-hour  { width: 5;  }
    #top-bar Button { margin: 0 1 0 0; min-width: 10; }

    #main-area { height: 1fr; layout: horizontal; }
    #left-panel  { width: 45%; border: solid $primary; margin: 0 1; }
    #right-panel { width: 1fr;  border: solid $primary; margin: 0 1 0 0; }

    .panel-title {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    #product-list { height: 1fr; }

    .dl-item {
        height: 6;
        padding: 0 1;
        border-bottom: solid $surface-lighten-1;
    }
    .dl-title { text-style: bold; color: $accent; }
    .dl-stats { color: $text-muted; }

    #log-panel { height: 10; border: solid $primary; margin: 0 1; }
    #log { height: 1fr; }

    #status-bar {
        height: 1;
        background: $boost;
        padding: 0 1;
        color: $text;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "search", "Search"),
        ("d", "download", "Download"),
        ("c", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        output_dir: str = "./downloads",
        max_workers: int = 32,
        chunk_size: int = 8 * 1024 * 1024,
        rate_limit: float = 200 * 1024 * 1024,
        api_key: Optional[str] = None,
        initial_source: str = "noaa",
    ) -> None:
        super().__init__()
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.rate_limit = rate_limit
        self.api_key = api_key or os.environ.get("EUMETSAT_API_KEY", "")

        self._initial_source = initial_source
        self._source_mode = initial_source
        self._source = None
        self._engine: Optional[DownloadEngine] = None
        self.products: list = []
        self.download_items: dict[str, DownloadItem] = {}
        self._downloading = False
        self._last_global_bytes = 0
        self._last_global_time = time.monotonic()
        self._last_global_speed = 0.0

    # ── 布局 ─────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="top-bar"):
            yield Select(
                [("NOAA AWS", "noaa"), ("EUMETSAT", "eumetsat")],
                id="sel-source",
                value=self._initial_source,
                allow_blank=False,
            )
            yield Input(placeholder="Collection", id="in-collection")
            yield Input(placeholder="BBox", id="in-bbox")
            yield Input(placeholder="Start ISO", id="in-start")
            yield Input(placeholder="End ISO", id="in-end")
            yield Input(placeholder="Lim", id="in-limit", value="20")
            yield Input(placeholder="Sat", id="in-noaa-sat", value="goes16")
            yield Input(placeholder="Prod", id="in-noaa-prod", value="ABI-L1b-RadF-Reproc")
            yield Input(placeholder="YYYY", id="in-noaa-year")
            yield Input(placeholder="DDD", id="in-noaa-day")
            yield Input(placeholder="HH", id="in-noaa-hour")
            yield Button("Search", id="btn-search", variant="primary")
            yield Button("Download", id="btn-download", variant="success")
            yield Button("Cancel", id="btn-cancel", variant="error")

        with Horizontal(id="main-area"):
            with Vertical(id="left-panel"):
                yield Label("Products", classes="panel-title")
                yield SelectionList(id="product-list")
            with VerticalScroll(id="right-panel"):
                yield Label("Downloads", classes="panel-title")

        with Vertical(id="log-panel"):
            yield Label("Log", classes="panel-title")
            yield RichLog(id="log", highlight=True, markup=True)

        yield Static("Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log", RichLog).write(
            "[bold green]SkyGrab[/] ready. Source: "
            f"[cyan]{self._initial_source}[/]"
        )
        self._build_source()

    # ── 数据源管理 ───────────────────────────

    def _build_source(self) -> None:
        if self._source_mode == "noaa":
            self._source = NoaaSource(
                on_log=self._log_threadsafe,
                max_workers=self.max_workers,
            )
        else:
            self._source = EumetsatSource(
                api_key=self.api_key,
                on_log=self._log_threadsafe,
                max_workers=self.max_workers,
            )
        self._engine = DownloadEngine(
            source=self._source,
            output_dir=self.output_dir,
            max_workers=self.max_workers,
            chunk_size=self.chunk_size,
            rate_limit=self.rate_limit,
            on_log=self._log_threadsafe,
            on_progress=self._progress_threadsafe,
            on_product_start=self._start_threadsafe,
            on_product_done=self._done_threadsafe,
            on_product_error=self._error_threadsafe,
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "sel-source":
            return
        self._source_mode = event.value
        self._build_source()
        self._write_log(f"Source switched to [cyan]{event.value}[/]")

    # ── 线程 → UI 桥接 ────────────────────────

    def _log_threadsafe(self, text: str) -> None:
        self.call_from_thread(self._write_log, text)

    def _write_log(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.query_one("#log", RichLog).write(f"[dim]{ts}[/] {text}")

    def _progress_threadsafe(self, snapshot: dict) -> None:
        self.call_from_thread(self._apply_progress, snapshot)

    def _apply_progress(self, snapshot: dict) -> None:
        for pid, d in snapshot.items():
            item = self.download_items.get(pid)
            if item:
                item.update_progress(d["done"], d["total"])

        total_done = sum(d["done"] for d in snapshot.values())
        total_size = sum(d["total"] for d in snapshot.values())
        active = sum(1 for d in snapshot.values() if d["done"] < d["total"])

        now = time.monotonic()
        dt = now - self._last_global_time
        if dt >= 0.5:
            self._last_global_speed = (total_done - self._last_global_bytes) / dt
            self._last_global_bytes = total_done
            self._last_global_time = now

        self.query_one("#status-bar", Static).update(
            f"Threads: {self.max_workers} | Active: {active} | "
            f"Done: {total_done / 1e6:.1f}/{total_size / 1e6:.1f} MB | "
            f"Speed: {self._last_global_speed / 1e6:.1f} MB/s"
        )

    def _start_threadsafe(self, pid: str, size: int, chunks: int) -> None:
        self.call_from_thread(self._add_download_item, pid)

    def _done_threadsafe(self, pid: str, path: str) -> None:
        self.call_from_thread(self._mark_done, pid, path)

    def _mark_done(self, pid: str, path: str) -> None:
        item = self.download_items.get(pid)
        if item:
            item.mark_done(path)
        self._write_log(f"[green]done[/] {pid}")

    def _error_threadsafe(self, pid: str, err: str) -> None:
        self.call_from_thread(self._mark_error, pid, err)

    def _mark_error(self, pid: str, err: str) -> None:
        item = self.download_items.get(pid)
        if item:
            item.mark_error(err)
        self._write_log(f"[red]error[/] {pid}: {err}")

    # ── 交互 ─────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-search":
            self.action_search()
        elif event.button.id == "btn-download":
            self.action_download()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def action_search(self) -> None:
        if self._source_mode == "noaa":
            sat = self._q("#in-noaa-sat").strip() or "goes16"
            prod = self._q("#in-noaa-prod").strip()
            y = self._q("#in-noaa-year").strip()
            d = self._q("#in-noaa-day").strip()
            h = self._q("#in-noaa-hour").strip()
            self._do_search("noaa", {
                "satellite": sat,
                "product": prod,
                "year": int(y) if y.isdigit() else None,
                "day_of_year": int(d) if d.isdigit() else None,
                "hour": int(h) if h.isdigit() else None,
            })
            return

        collection = self._q("#in-collection").strip()
        if not collection:
            self._write_log("[red]Collection required for EUMETSAT[/]")
            return
        bbox = self._q("#in-bbox").strip() or None
        start = self._q("#in-start").strip() or None
        end = self._q("#in-end").strip() or None
        lim = self._q("#in-limit").strip()
        self._do_search("eumetsat", {
            "collection_id": collection,
            "bbox": bbox, "start": start, "end": end,
            "limit": int(lim) if lim.isdigit() else 20,
        })

    def _q(self, sel: str) -> str:
        return self.query_one(sel, Input).value

    @work(thread=True)
    def _do_search(self, source: str, params: dict) -> None:
        try:
            products = self._source.search(**params)
            self.call_from_thread(self._populate_products, products)
        except Exception as e:
            self.call_from_thread(self._write_log, f"[red]Search failed: {e}[/]")

    def _populate_products(self, products: list) -> None:
        self.products = products
        sl = self.query_one("#product-list", SelectionList)
        sl.clear_options()
        for p in products:
            label = getattr(p, "title", None) or p.product_id
            if len(label) > 58:
                label = label[:55] + "..."
            sl.add_option(Selection(label, p.product_id))
        self.query_one("#status-bar", Static).update(
            f"Found {len(products)} products"
        )

    def action_download(self) -> None:
        if self._downloading:
            self._write_log("[yellow]already downloading[/]")
            return
        sl = self.query_one("#product-list", SelectionList)
        selected_ids = set(sl.selected)
        if not selected_ids:
            self._write_log("[yellow]nothing selected[/]")
            return
        selected = [p for p in self.products if p.product_id in selected_ids]
        self._downloading = True
        self._do_download(selected)

    @work(thread=True)
    def _do_download(self, products: list) -> None:
        try:
            self._engine.reset_cancel()
            for p in products:
                if self._engine.cancelled:
                    break
                self._engine.download(p)
        finally:
            self.call_from_thread(self._set_not_downloading)

    def _set_not_downloading(self) -> None:
        self._downloading = False

    def action_cancel(self) -> None:
        if self._engine:
            self._engine.cancel()
            self._write_log("[yellow]cancel requested[/]")

    def _add_download_item(self, pid: str) -> None:
        container = self.query_one("#right-panel", VerticalScroll)
        item = DownloadItem(pid)
        self.download_items[pid] = item
        container.mount(item)


def run_app(
    output_dir: str = "./downloads",
    max_workers: int = 32,
    chunk_size: int = 8 * 1024 * 1024,
    rate_limit: float = 200 * 1024 * 1024,
    api_key: Optional[str] = None,
    initial_source: str = "noaa",
) -> None:
    SkyGrabApp(
        output_dir=output_dir,
        max_workers=max_workers,
        chunk_size=chunk_size,
        rate_limit=rate_limit,
        api_key=api_key,
        initial_source=initial_source,
    ).run()
