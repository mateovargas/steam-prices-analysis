# steam-price-analysis

Scripts to collect **paid, single-player** Steam games (by Store categories and release date), enrich rows with **Steam Spy** `appdetails`, and write CSV (and optional JSON).

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   cd /path/to/steam-price-analysis
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Steam Web API key** (required for the game list): create one at [Steam Web API](https://steamcommunity.com/dev/apikey) and set it in a `.env` file in the project root:

   ```bash
   STEAM_WEB_API_KEY=your_key_here
   ```

   The main script loads `.env` automatically (`python-dotenv`).

## Run `data-retrieval.py`

From the project directory (use the hyphenated filename):

```bash
python data-retrieval.py
```

Default output is `data/single-player-games.csv`. Matching rows are games that pass Store filters (type game, Single-player, paid USD price, release on or after the cutoff). The default rolling cutoff is **about the last 10 years** (`365 * 10` days before today); override with `--release-cutoff-days` or a fixed `--min-release-date YYYY-MM-DD`.

Useful options:

| Flag | Meaning |
|------|---------|
| `--max-apps N` | Inspect at most **N** catalog entries from IStoreService list order (after `--start-offset`). |
| `--start-offset N` | Skip the first **N** rows of that list window. |
| `--csv-path PATH` | Output CSV path (default: `data/single-player-games.csv`). |
| `--output PATH` | Also write JSON results. |
| `--cache-path PATH` | Cache raw Store `appdetails` JSON by appid to speed reruns. |
| `--steamspy-cache-path PATH` | Cache Steam Spy `appdetails` per appid (24h TTL). |
| `--full-run` | Scan the full game catalog (very slow). |

Example:

```bash
python data-retrieval.py --max-apps 500 --start-offset 0 --steamspy-cache-path data/steamspy-cache.json
```

For all flags:

```bash
python data-retrieval.py --help
```

## Run `data-retrieval-test.py`

Smoke test: runs the **same pipeline** as `data-retrieval.py` via import, writes **all** matches to `data/test-data.csv`. It uses the script defaults from `data-retrieval.py` for the release cutoff (including the default from `DEFAULT_RELEASE_CUTOFF_DAYS`).

```bash
python data-retrieval-test.py
```

Defaults are tuned for a shorter run: **`--start-offset 90000`** and **`--max-apps 50`** (50 catalog entries examined, not necessarily 50 CSV rows). Override:

```bash
python data-retrieval-test.py --max-apps 100 --start-offset 80000
```

Exit code `0` if at least one row matched; `1` if none matched in that window.

## Notes

- Store `appdetails` is rate-limited (on the order of ~200 requests per 5 minutes per IP); large `--max-apps` runs take a long time.
- Steam Spy allows about **one request per second** per their API notes; the script throttles accordingly.
- The number of CSV rows is **matches**, not `--max-apps`; many examined apps are skipped (wrong category, free, outside release window, etc.).
