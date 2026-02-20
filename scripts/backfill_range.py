#!/usr/bin/env python3
"""Backfill HF papers date range with day-by-day pipeline.

For each date in range:
1) fetch
2) translate that date
3) optionally build index each day
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import build_index
import fetch_daily
import translate


def parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}") from exc


def iter_dates(start: datetime, end: datetime) -> list[str]:
    days: list[str] = []
    cursor = start
    while cursor <= end:
        days.append(cursor.strftime("%Y-%m-%d"))
        cursor += timedelta(days=1)
    return days


def main() -> None:
    default_workers_raw = os.getenv("TRANSLATE_WORKERS", "6").strip() or "6"
    default_prompt_lang = (
        os.getenv("TRANSLATE_PROMPT_LANG", os.getenv("OPENROUTER_PROMPT_LANG", "auto")).strip().lower()
        or "auto"
    )
    if default_prompt_lang not in ("auto", "zh", "en"):
        default_prompt_lang = "auto"
    try:
        default_workers = max(1, int(default_workers_raw))
    except ValueError:
        default_workers = 6

    parser = argparse.ArgumentParser(description="Backfill papers by date range (fetch -> translate -> index)")
    parser.add_argument("--start", type=parse_date, required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=parse_date, required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--papers-dir", type=Path, default=Path("data/papers"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--min-sleep", type=float, default=0.5)
    parser.add_argument("--max-sleep", type=float, default=1.5)
    parser.add_argument("--allow-weekend", action="store_true", help="Fetch weekend dates too")
    parser.add_argument(
        "--skip-existing-complete",
        dest="skip_existing_complete",
        action="store_true",
        default=True,
        help="Skip fetch if existing file is complete (default: true)",
    )
    parser.add_argument(
        "--no-skip-existing-complete",
        dest="skip_existing_complete",
        action="store_false",
        help="Disable skip-existing behavior",
    )
    parser.add_argument("--provider", choices=["auto", "dummy", "openrouter"], default="auto")
    parser.add_argument("--model", default="", help="Override translation model")
    parser.add_argument(
        "--prompt-lang",
        choices=["auto", "zh", "en"],
        default=default_prompt_lang,
        help="Prompt language mode for translation/summarization",
    )
    parser.add_argument("--workers", type=int, default=default_workers, help="Translation workers")
    parser.add_argument("--force-translate", action="store_true", help="Re-translate existing summary_zh")
    parser.add_argument("--build-index-each-day", action="store_true", help="Rebuild index after each day")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    if args.start > args.end:
        raise SystemExit("--start cannot be greater than --end")
    if args.min_sleep > args.max_sleep:
        raise SystemExit("--min-sleep cannot be greater than --max-sleep")
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    dates = iter_dates(args.start, args.end)
    logging.info("Backfill range: %s -> %s (%d days)", dates[0], dates[-1], len(dates))

    for date in dates:
        logging.info("=== Day pipeline: %s ===", date)
        fetch_daily.run(
            date=date,
            output_dir=args.papers_dir,
            min_sleep=args.min_sleep,
            max_sleep=args.max_sleep,
            skip_existing_complete=args.skip_existing_complete,
            allow_weekend=args.allow_weekend,
        )

        translate.run(
            data_dir=args.papers_dir,
            provider=args.provider,
            force=args.force_translate,
            model=args.model,
            prompt_lang=args.prompt_lang,
            date=date,
            workers=args.workers,
        )

        if args.build_index_each_day:
            build_index.run(papers_dir=args.papers_dir, out_dir=args.out_dir)

    build_index.run(papers_dir=args.papers_dir, out_dir=args.out_dir)
    logging.info("Backfill completed")


if __name__ == "__main__":
    main()
