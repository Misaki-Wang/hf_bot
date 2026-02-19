#!/usr/bin/env python3
"""Migrate flat paper files to date-based folder layout.

From:
  data/papers/YYYY-MM-DD__<paper_id>.json
To:
  data/papers/YYYY-MM-DD/<paper_id>.json
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

LEGACY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})__(.+)\.json$")


def run(papers_dir: Path, dry_run: bool) -> None:
    moved = 0
    skipped = 0
    for path in sorted(papers_dir.glob("*.json")):
        match = LEGACY_RE.match(path.name)
        if not match:
            continue
        date, paper_id = match.groups()
        target = papers_dir / date / f"{paper_id}.json"
        if target.exists():
            logging.info("Skip existing target: %s", target)
            skipped += 1
            continue
        logging.info("Move %s -> %s", path, target)
        moved += 1
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
    logging.info("Migration complete. moved=%d skipped=%d", moved, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate paper file layout to date folders")
    parser.add_argument("--papers-dir", type=Path, default=Path("data/papers"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    run(args.papers_dir, args.dry_run)


if __name__ == "__main__":
    main()
