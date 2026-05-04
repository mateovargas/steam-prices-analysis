#!/usr/bin/env python3
"""
Smoke test for data-retrieval: run the same pipeline, then write **all**
matching game rows to data/test-data.csv (``run()`` already performs the write).

Store ``appdetails`` is rate-limited (~200 requests / 5 minutes); each catalog
entry needs one request, so larger ``--max-apps`` means longer runs.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_RETRIEVAL_PATH = SCRIPT_DIR / "data-retrieval.py"
TEST_CSV_PATH = SCRIPT_DIR / "data" / "test-data.csv"
# Low list positions are often before the release cutoff; skip ahead in list order.
DEFAULT_START_OFFSET = 90000
# One Store request per entry (~200 / 5 min); 50 entries ≈ 80–100 s wall time.
DEFAULT_MAX_APPS_PROBE = 50


def _load_data_retrieval():
    spec = importlib.util.spec_from_file_location("data_retrieval", DATA_RETRIEVAL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {DATA_RETRIEVAL_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--max-apps",
        type=int,
        default=DEFAULT_MAX_APPS_PROBE,
        help=(
            "How many catalog entries to inspect after the start offset "
            f"(default {DEFAULT_MAX_APPS_PROBE}). Increase if no row matches filters."
        ),
    )
    p.add_argument(
        "--start-offset",
        type=int,
        default=DEFAULT_START_OFFSET,
        help=(
            "Skip this many leading IStoreService game rows (default "
            f"{DEFAULT_START_OFFSET}). Low positions are often before the configured release cutoff."
        ),
    )
    args = p.parse_args()

    load_dotenv(SCRIPT_DIR / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    dr = _load_data_retrieval()
    results = dr.run(
        max_apps=max(1, args.max_apps),
        start_offset=max(0, args.start_offset),
        cache_path=None,
        output_path=None,
        csv_path=TEST_CSV_PATH,
        release_cutoff=date.today() - timedelta(days=dr.DEFAULT_RELEASE_CUTOFF_DAYS),
        steamspy_cache_path=None,
    )
    if not results:
        logging.error(
            "No games matched in offset=%d window of %d entries; "
            "try different --start-offset / larger --max-apps or check STEAM_WEB_API_KEY.",
            args.start_offset,
            args.max_apps,
        )
        return 1

    logging.info("Wrote %d test row(s) to %s", len(results), TEST_CSV_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
