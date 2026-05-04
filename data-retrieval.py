#!/usr/bin/env python3
"""
Fetch **paid** Steam games that are store-type "game", list "Single-player", and
released **on or after** a configurable minimum release date (default: rolling
**~10 years** from Store ``release_date``, i.e. ``today`` minus 3650 days). Free titles and anything without
a positive list price are excluded.

Limitations
-----------
- **Two Valve endpoints**: game **app IDs** come from
  ``IStoreService/GetAppList/v1`` on ``api.steampowered.com`` (replaces removed
  ``ISteamApps/GetAppList``). That list does not include store categories or
  release strings. Metadata comes from ``store.steampowered.com/api/appdetails``.
- **``STEAM_WEB_API_KEY`` is required** for ``IStoreService/GetAppList`` (any
  Steam Web API key from https://steamcommunity.com/dev/apikey). Set it in the
  environment or in a ``.env`` file next to this script (shell wins if both are set).
- **Enumeration order** is ascending ``appid``, not chronological. A capped run
  is an arbitrary slice of the catalog, not "the first N games by release date."
- **Store rate limits**: ``appdetails`` is commonly limited to about 200
  requests per 5 minutes per IP. This script issues **one appid per HTTP
  request** so categories and release dates are reliable; a full run can take
  many hours or days.
- **Single-player** means the **Steam Store** lists the "Single-player" category
  (games that also have Multi-player are still included); this is not inferred
  from Steam Spy tags.
- **Release window** (default rolling ~10 years) uses the Store ``release_date``
  string, not Steam Spy (Steam Spy ``appdetails`` does not include release dates).
- **Price** comes from ``price_overview`` for ``cc=us`` (USD when currency is
  USD). Free-to-play and anything without a positive ``final`` price is dropped.
- **Owners / CCU / playtime** come from **Steam Spy** ``api.php?request=appdetails``
  (https://steamspy.com/api.php): ``owners`` is an estimated range; ``ccu`` is
  documented there as **peak CCU yesterday**. Respect **~1 request per second**
  to Steam Spy; data refreshes about **once per day** (optional on-disk cache).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
from dateutil import parser as date_parser
from dotenv import load_dotenv

STORE_SERVICE_GET_APP_LIST = (
    "https://api.steampowered.com/IStoreService/GetAppList/v1/"
)
APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAM_SPY_API_URL = "https://steamspy.com/api.php"
# ~200 Store requests / 5 minutes per IP.
MIN_REQUEST_INTERVAL_SEC = 300.0 / 200.0 + 0.05
# Steam Spy: ~1 request per second for appdetails (see steamspy.com/api.php).
STEAM_SPY_MIN_INTERVAL_SEC = 1.0
STEAM_SPY_CACHE_MAX_AGE_SEC = 86400
DEFAULT_MAX_APPS = 1000
DEFAULT_RELEASE_CUTOFF_DAYS = 365 * 10
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV_PATH = SCRIPT_DIR / "data" / "single-player-games.csv"
CSV_FIELDNAMES = (
    "appid",
    "name",
    "release_date",
    "release_date_iso",
    "price_currency",
    "price_final_cents",
    "price_initial_cents",
    "price_discount_percent",
    "price_final_formatted",
    "developers",
    "publishers",
    "store_url",
    "steamspy_owners",
    "steamspy_ccu",
    "steamspy_average_forever",
    "steamspy_average_2weeks",
    "steamspy_median_forever",
    "steamspy_median_2weeks",
    "steamspy_score_rank",
    "steamspy_price",
    "steamspy_initialprice",
    "steamspy_discount",
    "steamspy_genre",
    "steamspy_tags",
)
USER_AGENT = (
    "Mozilla/5.0 (compatible; steam-price-analysis/1.0; +https://example.local)"
)


@dataclass
class RunStats:
    examined: int = 0
    store_failures: int = 0
    skipped_coming_soon: int = 0
    skipped_unparsed_date: int = 0
    skipped_not_game: int = 0
    skipped_no_single_player: int = 0
    skipped_before_cutoff: int = 0
    skipped_free: int = 0
    skipped_unpriced: int = 0
    matches: int = 0
    cache_hits: int = 0
    steamspy_failures: int = 0


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


def _require_api_key() -> str:
    key = (os.environ.get("STEAM_WEB_API_KEY") or "").strip()
    if not key:
        print(
            "Missing STEAM_WEB_API_KEY. Create a key at "
            "https://steamcommunity.com/dev/apikey and export it.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return key


def fetch_game_app_list(
    session: requests.Session,
    key: str,
    need_count: int | None,
) -> list[dict[str, Any]]:
    """
    Paginate IStoreService/GetAppList until we have ``need_count`` game rows
    (or the catalog ends). ``need_count`` None means fetch entire catalog.
    """
    collected: list[dict[str, Any]] = []
    last_appid = 0

    while need_count is None or len(collected) < need_count:
        remaining = None if need_count is None else need_count - len(collected)
        page_req = 50000
        if remaining is not None:
            page_req = min(50000, max(1, remaining))

        params: dict[str, str | int] = {
            "key": key,
            "max_results": page_req,
            "last_appid": last_appid,
            "include_games": 1,
            "include_dlc": 0,
            "include_software": 0,
            "include_videos": 0,
            "include_hardware": 0,
        }

        payload: dict[str, Any] | None = None
        for attempt in range(1, 5):
            r = session.get(STORE_SERVICE_GET_APP_LIST, params=params, timeout=120)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(30, 2**attempt))
                continue
            r.raise_for_status()
            try:
                payload = r.json()
            except json.JSONDecodeError:
                time.sleep(2**attempt)
                continue
            break

        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected IStoreService/GetAppList body")

        resp = payload.get("response", payload)
        apps = resp.get("apps") if isinstance(resp, dict) else None
        if not isinstance(apps, list):
            raise RuntimeError("Unexpected IStoreService/GetAppList response shape")

        if not apps:
            break

        for row in apps:
            if not isinstance(row, dict) or "appid" not in row:
                continue
            aid = int(row["appid"])
            collected.append(
                {
                    "appid": aid,
                    "name": row.get("name") or "",
                }
            )

        last_appid = int(apps[-1]["appid"])
        if len(apps) < page_req:
            break

    return collected


def load_cache(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        logging.warning("Could not read cache %s: %s", path, e)
        return {}


def save_cache(path: Path | None, cache: dict[str, Any]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)
    tmp.replace(path)


def _parse_release_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = date_parser.parse(raw, fuzzy=True)
        return dt.date()
    except (ValueError, TypeError, OverflowError):
        return None


def _paid_price_overview(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Return ``price_overview`` when it has a positive ``final`` price (amounts
    are in the smallest currency unit, e.g. cents for USD), matching ``cc=us``
    on the Store request. Caller must reject ``is_free`` titles separately.
    """
    po = data.get("price_overview")
    if not isinstance(po, dict):
        return None
    raw = po.get("final")
    try:
        final_cents = int(raw)
    except (TypeError, ValueError):
        return None
    if final_cents <= 0:
        return None
    return po


def has_single_player(categories: Any) -> bool:
    if not isinstance(categories, list):
        return False
    for c in categories:
        if not isinstance(c, dict):
            continue
        desc = c.get("description")
        cid = c.get("id")
        if desc == "Single-player":
            return True
        if str(cid) == "2":
            return True
    return False


def match_row(aid: int, data: dict[str, Any], catalog_name: str) -> dict[str, Any]:
    """Flatten store ``data`` for JSON/CSV export (call only when filters pass)."""
    raw_date = (data.get("release_date") or {}).get("date")
    parsed = (
        _parse_release_date(raw_date)
        if isinstance(raw_date, str)
        else None
    )
    devs = data.get("developers")
    pubs = data.get("publishers")
    dev_str = (
        "; ".join(str(x) for x in devs)
        if isinstance(devs, list)
        else ""
    )
    pub_str = (
        "; ".join(str(x) for x in pubs)
        if isinstance(pubs, list)
        else ""
    )
    po = _paid_price_overview(data)
    if not po:
        raise RuntimeError("match_row requires a paid price_overview")
    final_cents = int(po["final"])
    try:
        initial_cents = int(po.get("initial", final_cents))
    except (TypeError, ValueError):
        initial_cents = final_cents
    try:
        discount_pct = int(po.get("discount_percent", 0))
    except (TypeError, ValueError):
        discount_pct = 0
    return {
        "appid": aid,
        "name": (data.get("name") or catalog_name or "").strip(),
        "release_date": raw_date if isinstance(raw_date, str) else "",
        "release_date_iso": parsed.isoformat() if parsed else "",
        "price_currency": str(po.get("currency") or ""),
        "price_final_cents": final_cents,
        "price_initial_cents": initial_cents,
        "price_discount_percent": discount_pct,
        "price_final_formatted": str(po.get("final_formatted") or ""),
        "developers": dev_str,
        "publishers": pub_str,
        "store_url": f"https://store.steampowered.com/app/{aid}/",
    }


def passes_filters(
    data: dict[str, Any],
    stats: RunStats,
    release_cutoff: date,
) -> bool:
    if data.get("type") != "game":
        stats.skipped_not_game += 1
        return False
    rd = data.get("release_date") or {}
    if rd.get("coming_soon") is True:
        stats.skipped_coming_soon += 1
        return False
    raw_date = rd.get("date")
    if not isinstance(raw_date, str):
        stats.skipped_unparsed_date += 1
        return False
    parsed = _parse_release_date(raw_date)
    if parsed is None:
        stats.skipped_unparsed_date += 1
        return False
    if parsed < release_cutoff:
        stats.skipped_before_cutoff += 1
        return False
    if not has_single_player(data.get("categories")):
        stats.skipped_no_single_player += 1
        return False
    if data.get("is_free"):
        stats.skipped_free += 1
        return False
    if _paid_price_overview(data) is None:
        stats.skipped_unpriced += 1
        return False
    stats.matches += 1
    return True


class StoreRateLimiter:
    def __init__(self, min_interval: float = MIN_REQUEST_INTERVAL_SEC) -> None:
        self._min_interval = min_interval
        self._prev: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._prev is not None:
            gap = self._min_interval - (now - self._prev)
            if gap > 0:
                time.sleep(gap)
        self._prev = time.monotonic()


def fetch_appdetails_single(
    session: requests.Session,
    appid: int,
    limiter: StoreRateLimiter,
) -> dict[str, Any] | None:
    """One ``appid`` per request (categories, release date, and ``price_overview``)."""
    params = {"appids": str(appid), "l": "english", "cc": "us"}
    limiter.wait()
    for attempt in range(1, 6):
        r = session.get(APP_DETAILS_URL, params=params, timeout=60)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(30, 2**attempt))
            continue
        if r.status_code != 200:
            logging.debug("appdetails %s HTTP %s", appid, r.status_code)
            return None
        try:
            body = r.json()
        except json.JSONDecodeError:
            time.sleep(2**attempt)
            continue
        entry = body.get(str(appid)) if isinstance(body, dict) else None
        if isinstance(entry, dict):
            return entry
        return None
    return None


def fetch_steamspy_appdetails(
    session: requests.Session,
    appid: int,
    limiter: StoreRateLimiter,
) -> dict[str, Any] | None:
    """Steam Spy ``request=appdetails`` JSON, or None if hidden/unavailable."""
    params = {"request": "appdetails", "appid": appid}
    limiter.wait()
    for attempt in range(1, 6):
        r = session.get(STEAM_SPY_API_URL, params=params, timeout=60)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(30, 2**attempt))
            continue
        if r.status_code != 200:
            logging.debug("Steam Spy appdetails %s HTTP %s", appid, r.status_code)
            return None
        try:
            body = r.json()
        except json.JSONDecodeError:
            time.sleep(2**attempt)
            continue
        if not isinstance(body, dict):
            return None
        aid_r = body.get("appid")
        if aid_r == 999999 or str(aid_r) == "999999":
            return None
        return body
    return None


def _steamspy_cache_get(
    cache: dict[str, Any],
    appid: int,
) -> dict[str, Any] | None:
    sk = str(appid)
    raw = cache.get(sk)
    if not isinstance(raw, dict):
        return None
    ts = raw.get("fetched_at")
    pl = raw.get("payload")
    if ts is None or not isinstance(pl, dict):
        return None
    if time.time() - float(ts) > STEAM_SPY_CACHE_MAX_AGE_SEC:
        return None
    return pl


def _steamspy_cache_put(
    cache: dict[str, Any],
    appid: int,
    payload: dict[str, Any],
) -> None:
    cache[str(appid)] = {"fetched_at": time.time(), "payload": payload}


def _empty_steamspy_row_cells() -> dict[str, Any]:
    return {
        "steamspy_owners": "",
        "steamspy_ccu": "",
        "steamspy_average_forever": "",
        "steamspy_average_2weeks": "",
        "steamspy_median_forever": "",
        "steamspy_median_2weeks": "",
        "steamspy_score_rank": "",
        "steamspy_price": "",
        "steamspy_initialprice": "",
        "steamspy_discount": "",
        "steamspy_genre": "",
        "steamspy_tags": "",
    }


def attach_steamspy_to_row(
    row: dict[str, Any],
    spy: dict[str, Any] | None,
) -> None:
    """Merge Steam Spy ``appdetails`` fields into ``row`` (empty strings if None)."""
    if spy is None:
        row.update(_empty_steamspy_row_cells())
        return
    tags = spy.get("tags")
    tags_s = ""
    if isinstance(tags, dict):
        tags_s = json.dumps(tags, ensure_ascii=False)

    def _num_field(key: str) -> int | str:
        v = spy.get(key)
        if v is None or v == "":
            return ""
        try:
            return int(v)
        except (TypeError, ValueError):
            return str(v)

    sr = spy.get("score_rank")
    score_cell = ""
    if sr is not None and sr != "":
        try:
            score_cell = str(int(sr))
        except (TypeError, ValueError):
            score_cell = str(sr)

    row.update(
        {
            "steamspy_owners": str(spy.get("owners") or ""),
            "steamspy_ccu": _num_field("ccu"),
            "steamspy_average_forever": _num_field("average_forever"),
            "steamspy_average_2weeks": _num_field("average_2weeks"),
            "steamspy_median_forever": _num_field("median_forever"),
            "steamspy_median_2weeks": _num_field("median_2weeks"),
            "steamspy_score_rank": score_cell,
            "steamspy_price": str(spy.get("price") if spy.get("price") is not None else ""),
            "steamspy_initialprice": str(
                spy.get("initialprice") if spy.get("initialprice") is not None else ""
            ),
            "steamspy_discount": _num_field("discount"),
            "steamspy_genre": str(spy.get("genre") or ""),
            "steamspy_tags": tags_s,
        }
    )


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            flat = {k: row.get(k, "") for k in CSV_FIELDNAMES}
            flat["appid"] = row.get("appid", "")
            for num_key in (
                "price_final_cents",
                "price_initial_cents",
                "price_discount_percent",
                "steamspy_ccu",
                "steamspy_average_forever",
                "steamspy_average_2weeks",
                "steamspy_median_forever",
                "steamspy_median_2weeks",
                "steamspy_discount",
            ):
                v = row.get(num_key, "")
                flat[num_key] = "" if v == "" else str(v)
            w.writerow(flat)
    tmp.replace(path)


def run(
    max_apps: int | None,
    start_offset: int,
    cache_path: Path | None,
    output_path: Path | None,
    csv_path: Path,
    release_cutoff: date,
    steamspy_cache_path: Path | None = None,
) -> list[dict[str, Any]]:
    session = _session()
    stats = RunStats()
    cache = load_cache(cache_path)
    steamspy_cache = load_cache(steamspy_cache_path)
    store_limiter = StoreRateLimiter()
    steamspy_limiter = StoreRateLimiter(STEAM_SPY_MIN_INTERVAL_SEC)
    api_key = _require_api_key()

    need_list_size = None if max_apps is None else start_offset + max_apps
    logging.info(
        "Fetching IStoreService/GetAppList (games only), target rows=%s …",
        need_list_size if need_list_size is not None else "ALL",
    )
    all_apps = fetch_game_app_list(session, api_key, need_list_size)
    logging.info("Collected %d catalog rows from IStoreService", len(all_apps))

    if start_offset >= len(all_apps):
        logging.warning(
            "start-offset %d is past collected list length %d",
            start_offset,
            len(all_apps),
        )
        slice_apps: list[dict[str, Any]] = []
    else:
        end = len(all_apps) if max_apps is None else min(len(all_apps), start_offset + max_apps)
        slice_apps = all_apps[start_offset:end]

    results: list[dict[str, Any]] = []

    for a in slice_apps:
        aid = int(a["appid"])
        sk = str(aid)
        stats.examined += 1

        if sk in cache:
            stats.cache_hits += 1
            entry = cache[sk]
        else:
            entry = fetch_appdetails_single(session, aid, store_limiter)
            if entry is not None:
                cache[sk] = entry
                if cache_path:
                    save_cache(cache_path, cache)

        if not isinstance(entry, dict):
            stats.store_failures += 1
            continue
        if not entry.get("success"):
            stats.store_failures += 1
            continue
        data = entry.get("data")
        if not isinstance(data, dict):
            stats.store_failures += 1
            continue

        if passes_filters(data, stats, release_cutoff):
            row = match_row(aid, data, str(a.get("name") or ""))
            spy = _steamspy_cache_get(steamspy_cache, aid)
            if spy is None:
                spy = fetch_steamspy_appdetails(session, aid, steamspy_limiter)
                if spy is not None and steamspy_cache_path:
                    _steamspy_cache_put(steamspy_cache, aid, spy)
                    save_cache(steamspy_cache_path, steamspy_cache)
            if spy is None:
                stats.steamspy_failures += 1
            attach_steamspy_to_row(row, spy)
            results.append(row)

    logging.info(
        "Done. examined=%d matches=%d store_failures=%d cache_hits=%d "
        "steamspy_failures=%d "
        "not_game=%d coming_soon=%d bad_date=%d no_sp=%d before_cutoff=%d "
        "free=%d unpriced=%d",
        stats.examined,
        stats.matches,
        stats.store_failures,
        stats.cache_hits,
        stats.steamspy_failures,
        stats.skipped_not_game,
        stats.skipped_coming_soon,
        stats.skipped_unparsed_date,
        stats.skipped_no_single_player,
        stats.skipped_before_cutoff,
        stats.skipped_free,
        stats.skipped_unpriced,
    )

    write_results_csv(csv_path, results)
    logging.info("Wrote %d rows to %s", len(results), csv_path)

    if output_path:
        text = json.dumps(results, ensure_ascii=False, indent=2)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        logging.info("Wrote %d rows to %s", len(results), output_path)
    else:
        logging.info("JSON not written (use --output path.json to export JSON)")

    return results


def main() -> None:
    load_dotenv(SCRIPT_DIR / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--max-apps",
        type=int,
        default=DEFAULT_MAX_APPS,
        help=(
            "Max apps to inspect from IStoreService game list order "
            f"(default {DEFAULT_MAX_APPS})"
        ),
    )
    p.add_argument(
        "--start-offset",
        type=int,
        default=0,
        help="Skip this many leading entries after fetching the list window",
    )
    p.add_argument(
        "--cache-path",
        type=Path,
        default=None,
        help="JSON file mapping appid string to raw appdetails object for reuse",
    )
    p.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=(
            "Write matching games as CSV (default: "
            f"<project>/data/single-player-games.csv → {DEFAULT_CSV_PATH})"
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Also write JSON results to this file (optional)",
    )
    p.add_argument(
        "--full-run",
        action="store_true",
        help=(
            "Fetch the full game catalog from IStoreService then scan every "
            "entry (extremely slow for appdetails)."
        ),
    )
    p.add_argument(
        "--release-cutoff-days",
        type=int,
        default=DEFAULT_RELEASE_CUTOFF_DAYS,
        help=(
            "Include games whose Store release date is on or after "
            "(today minus this many days). Ignored if --min-release-date is set."
        ),
    )
    p.add_argument(
        "--min-release-date",
        type=str,
        default=None,
        help=(
            "ISO date (YYYY-MM-DD): include games released on or after this date. "
            "Overrides --release-cutoff-days when set."
        ),
    )
    p.add_argument(
        "--steamspy-cache-path",
        type=Path,
        default=None,
        help="JSON file caching Steam Spy appdetails per appid (24 hour TTL).",
    )
    args = p.parse_args()

    max_apps: int | None = None if args.full_run else args.max_apps
    if args.full_run:
        logging.warning(
            "--full-run: full catalog + one Store request per app; expect a very "
            "long runtime."
        )

    if args.min_release_date:
        try:
            release_cutoff = date.fromisoformat(args.min_release_date)
        except ValueError:
            print(
                f"Invalid --min-release-date {args.min_release_date!r}; use YYYY-MM-DD.",
                file=sys.stderr,
            )
            raise SystemExit(2) from None
        logging.info("Using release cutoff (min-release-date): %s", release_cutoff)
    else:
        release_cutoff = date.today() - timedelta(days=max(0, args.release_cutoff_days))
        logging.info(
            "Using release cutoff: %s (--release-cutoff-days=%d)",
            release_cutoff,
            args.release_cutoff_days,
        )

    run(
        max_apps=max_apps,
        start_offset=max(0, args.start_offset),
        cache_path=args.cache_path,
        output_path=args.output,
        csv_path=args.csv_path,
        release_cutoff=release_cutoff,
        steamspy_cache_path=args.steamspy_cache_path,
    )


if __name__ == "__main__":
    main()
