"""命令行入口。"""
from __future__ import annotations

import argparse
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="skygrab",
        description="Aggressive multi-source satellite data harvester",
    )
    p.add_argument("--source", choices=["noaa", "eumetsat"], default="noaa")
    p.add_argument("-o", "--output", default="./downloads")
    p.add_argument("-w", "--workers", type=int, default=32)
    p.add_argument("--chunk-mb", type=int, default=8)
    p.add_argument("--rate-mbps", type=float, default=200,
                   help="0 = unlimited")
    p.add_argument("--api-key", default=None,
                   help="EUMETSAT API key (or env EUMETSAT_API_KEY)")
    p.add_argument("--version", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.version:
        from skygrab import __version__
        print(f"skygrab {__version__}")
        return 0

    api_key = args.api_key or os.environ.get("EUMETSAT_API_KEY", "")
    if args.source == "eumetsat" and not api_key:
        print("ERROR: EUMETSAT mode requires --api-key or EUMETSAT_API_KEY",
              file=sys.stderr)
        return 1

    rate = args.rate_mbps * 1024 * 1024 if args.rate_mbps > 0 else float("inf")

    try:
        from skygrab.app import run_app
    except ImportError as e:
        print(f"ERROR: TUI 依赖缺失: {e}", file=sys.stderr)
        print("提示: pacman -S python-textual", file=sys.stderr)
        return 1

    run_app(
        output_dir=args.output,
        max_workers=args.workers,
        chunk_size=args.chunk_mb * 1024 * 1024,
        rate_limit=rate,
        api_key=api_key,
        initial_source=args.source,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
