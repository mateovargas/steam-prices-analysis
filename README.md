# steam-price-analysis

Scripts to collect **paid, single-player** Steam games (by Store categories and release date), enrich rows with **Steam Spy** `appdetails`, and write CSV (and optional JSON).

## Dataset summary

The notebook [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb) cleans `data/single-player-games.csv` into `data/single-player-games-cleaned.parquet` (and optional CSV) and saves standard EDA plots into [`visualizations/`](visualizations/).

- **Rows kept (usable for ML)**: **10,736** (dropped **3** rows with unparseable `steamspy_owners` ranges)
- **Target proxy**: `owners_mid` / `log_owners_mid` derived from SteamSpy owner **ranges** (estimates, not true sales)
- **Price distribution (USD)** (see `visualizations/price_usd_hist.png`):
  - **Median**: **$5.99** (25th: **$2.99**, 75th: **$12.99**)
  - **90th/95th/99th**: **$19.99 / $24.99 / $39.99**
  - **Min**: **$0.49**
- **Owners proxy distribution is highly discrete / skewed** (see `visualizations/owners_mid_log_hist.png`):
  - **50th percentile owners_mid**: **10,000**
  - **75th/90th/95th/99th**: **35,000 / 150,000 / 350,000 / 3,500,000**
- **Engagement fields are zero-inflated**:
  - `steamspy_ccu` is **0** for ~**75.6%** of rows
  - `steamspy_median_forever` is **0** for **100%** of rows in this snapshot (treat as non-informative unless refreshed)
- **Simple correlations vs `log_owners_mid` are modest** (see `visualizations/correlation_heatmap_numeric.png`):
  - `price_usd`: **~0.29**
  - `steamspy_ccu`: **~0.25**
  - `age_days`: **~-0.06**
- **Most common `primary_genre` values** (top 5): **Action (4,901)**, **Adventure (2,223)**, **Casual (1,609)**, **Indie (1,034)**, **Simulation (218)**  
  (also see `visualizations/price_by_primary_genre_box.png` and `visualizations/mean_log_owners_by_primary_genre_bar.png`)

**Interpretation note:** because `steamspy_owners` is an estimated range, the dataset supports modeling **associations** between price/features and an ownership proxy—not causal identification of an “optimal price point.”

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

## Clean data for ML (`steam-price-analysis.ipynb`)

After you have `data/single-player-games.csv`, open [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb) and **run all cells** (from top to bottom). The first code cell sets paths and options (`REFERENCE_DATE`, `GENRE_TOP_K`, `MIN_OWNERS_MID`, `WRITE_CSV_MIRROR`).

**Outputs**

- `data/single-player-games-cleaned.parquet` (recommended for pandas / ML)
- `data/single-player-games-cleaned.csv` (optional mirror for spreadsheets), unless you set `WRITE_CSV_MIRROR = False`

**Important:** SteamSpy **owner ranges** are estimates, not true sales. The notebook parses them into `owners_mid` and `log_owners_mid` as a **sales proxy**; models describe association with that proxy, not a causal “best price.”

Requires the same stack as [`requirements.txt`](requirements.txt) (`pandas`, `numpy`, `pyarrow`). Use a Jupyter-compatible environment (e.g. VS Code / Cursor notebook UI, or `pip install jupyter` and run `jupyter notebook`).

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
