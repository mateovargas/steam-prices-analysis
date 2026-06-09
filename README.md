# steam-price-analysis

Analysis of **paid, single-player Steam games**: data collection, cleaning, exploratory visualization, and **multiple regression models** relating list price and metadata to SteamSpy’s estimated owner counts.

**Main deliverable:** [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb) — run all cells top to bottom after [setup](#setup) below.

---

## Key findings (summary)

**Business question:** What list price and game characteristics are associated with stronger *estimated* sales on Steam?

| Finding | Detail |
|---------|--------|
| **Dataset** | **10,736** games after cleaning; target = log of SteamSpy owner-range **midpoint** (sales proxy, not verified units). |
| **Typical price** | Median list price **$5.99**; 75th percentile **$12.99**. |
| **Price vs owners** | Correlation with log owners **~0.29**; genre/tags and unmeasured quality dominate. |
| **Linear “optimal price” (§9)** | OLS revenue proxy peaks at the **grid maximum** (e.g. **$39.99**)—confounding, **not** a causal pricing rule. |
| **Model comparison (§10)** | **Gradient Boosting** (test R² **0.439**) and **Random Forest** (**0.434**) beat linear models (**~0.33**) with full genre + tag features. |

**For stakeholders:** Use models to **explore scenarios and rank approaches**, not to set launch price without comps, wishlist data, or experiments. See [Business recommendations](#business-recommendations) and [Detailed findings](#detailed-findings) below; the notebook (§8–§11) contains plots, code, and interpretation cells.

---

## Business recommendations

*For publishing, product, and marketing leaders. Based on **10,736** paid single-player Steam games.*

### What we learned in plain terms

Most games in this segment list around **$6** (median **$5.99**; 75% are below **$13**). Price correlates only modestly with estimated sales (~**0.29**). Genre, Steam tags, and factors we cannot see in public data—quality, marketing, franchise strength—matter more than list price alone.

Our models explain at best **~44%** of variation in estimated owners. That is useful for comparison and planning, but a large share of success remains unpredictable from catalog metadata.

**Critical caveat:** A linear model’s “revenue-maximizing” price often lands at the **top of the observed range** (~$40). That reflects confounding (hit games tend to be both popular and expensive), not proof that raising price drives sales. Do not treat model output as a launch-price mandate.

### Recommendations

1. **Anchor pricing on comps, not the catalog median alone** — Build a comp set of 10–20 titles that match your game on genre, tag profile (e.g., Story Rich, Atmospheric), scope, and visual quality. The catalog median (~$6) is a floor for many indie titles, not a target for premium or niche experiences.

2. **Use models to frame scenarios, not to set the final number** — Run what-if discussions at different price points with similar metadata. Prefer the **§9 linear baseline** when explaining trade-offs to non-technical partners; use **§10 tree models** when you need the best forecast among similar games.

3. **Validate with forward-looking signals before commit** — Wishlists, demo downloads, playtest feedback, influencer previews, and soft-launch experiments outweigh retrospective catalog regression.

4. **Align positioning with tags that correlate with reach** — Tags such as **Story Rich**, **Atmospheric**, and **Great Soundtrack** appear alongside higher estimated ownership. Ensure store page positioning honestly reflects what you deliver.

5. **Plan promos and regional pricing separately from list price** — This study uses snapshot list prices, not sale events or regional tiers. Set base list price from comps; design discount and regional strategy as distinct post-launch decisions.

6. **Invest in better data for the next decision cycle** — Title-specific comp universes, Steam review scores, wishlist metrics, and price history across sales events. Blend in first-party sales where available.

### Bottom line

**Do not** read this analysis as “charge $X and succeed.” **Do** use it to benchmark against similar games, stress-test pricing scenarios with explicit assumptions, and invest in pre-launch validation.

---

## Detailed findings

*Metrics from `data/single-player-games-cleaned.parquet` (**10,736** games), train/test split `random_state=42`, 80/20 holdout. Maps to notebook §8–§11.*

### Business problem

Indie and mid-tier publishers need evidence-informed **list prices** on Steam:

> What list price and game characteristics are **associated** with stronger estimated sales on Steam?

We proxy sales strength with **SteamSpy owner-range midpoints** (`owners_mid` → `log_owners_mid`). That is a noisy cross-sectional estimate—not verified unit sales. Conclusions describe **historical associations**, not causal pricing rules.

### Data and methodology

| Item | Detail |
|------|--------|
| **Input** | `data/single-player-games.csv` (~10.7k paid, single-player games) |
| **After cleaning** | **10,736** rows → `single-player-games-cleaned.parquet` |
| **Target** | `log_owners_mid` (log of SteamSpy owner-range midpoint) |
| **Features** | `price_usd`, `age_days`, counts, top-18 `genre__*`, top-15 `tag__*` |

**Cleaning:** Sequential drops for unparseable owners, missing price, invalid release date, or missing metadata. All retained games are paid (min price **$0.49**).

**Limitations:** SteamSpy ranges are estimates (median `owners_mid` = **10,000**); single snapshot (no price history or wishlists); engagement fields often zero; association ≠ causation.

### Exploratory analysis (§8–§8b)

| Topic | Result |
|-------|--------|
| **Price** | Median **$5.99**, p75 **$12.99**, mean **$9.30**, max **$199.99** |
| **Owners** | Median **10,000**, p75 **35,000**, highly skewed (log scale used for modeling) |
| **Price vs owners** | Pearson r **≈ 0.29** (latest: **0.288**) |
| **Top genres** | Action **4,901**, Adventure **2,223**, Casual **1,609** |
| **High-reach tags** | Great Soundtrack (**11.08**), Atmospheric (**11.00**), Story Rich (**10.99**) mean log owners |

**Plots:** `visualizations/` — histograms, scatter plots, genre box/bar charts, correlation heatmap, tag prevalence and mean-owners charts.

### Linear regression — “optimal price” (§9)

OLS predicts `log_owners_mid` from `price_usd`, counts, and **genre** flags (no tags—interpretable baseline).

| Metric | Value |
|--------|-------|
| Test **R²** | **0.297** |
| Test **RMSE** / **MAE** | **1.185** / **0.889** |
| 5-fold CV **R²** | **0.283** |
| **Price coefficient** | **+0.023** (confounded; not causal) |
| Revenue-proxy peak | **$39.99** (grid max) vs catalog median **$5.99** |

Use for transparent what-if conversations. **Do not** treat the revenue-curve maximum as a launch-price target.

### Model comparison (§10)

Seven models on the **full feature set** (price, counts, genre + tag flags). **Primary metric: test R²** (explained variance on holdout log owners). **RMSE/MAE** measure typical error on the log scale.

| Model | Test R² | CV R² | RMSE | MAE |
|-------|---------|-------|------|-----|
| **Gradient Boosting** | **0.439** | 0.416 | 1.059 | 0.783 |
| **Random Forest** | **0.434** | 0.406 | 1.064 | 0.780 |
| MLP | 0.351 | 0.330 | 1.138 | 0.849 |
| KNN | 0.332 | 0.322 | 1.155 | 0.829 |
| OLS | 0.331 | 0.308 | 1.156 | 0.867 |
| Ridge | 0.330 | 0.308 | 1.157 | 0.868 |
| Lasso | 0.329 | 0.308 | 1.158 | 0.867 |

**Methods:** Ridge/Lasso use `RidgeCV`/`LassoCV` (5-fold CV); KNN uses `GridSearchCV` over `n_neighbors`; all models evaluated on the same holdout split.

Tree ensembles gain **~+0.10 R²** over linear models via nonlinear price/genre/tag interactions. Even the best model explains **< 50%** of variance—quality, marketing, and timing remain unobserved.

### What we can and cannot claim

**Supports:** Typical price ~**$6**; price alone is weak; nonlinear models outperform linear baselines with rich metadata; linear models useful for scenario framing with caveats.

**Does not support:** “Set price to $X and maximize revenue”; causal price elasticity from one cross-section; SteamSpy as audited sales.

### Next steps (analytics)

| Priority | Action |
|----------|--------|
| High | Curate comp universe per title and refit |
| High | Collect wishlist / demo conversion data |
| Medium | Add review scores; track price history for elasticity |
| Low | Further MLP/ensemble tuning (diminishing returns vs. data quality) |

---

## Project layout

| Path | Purpose |
|------|---------|
| [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb) | Cleaning, EDA, modeling (§9–§10), findings cells |
| [`requirements.txt`](requirements.txt) | Python dependencies |
| [`data-retrieval.py`](data-retrieval.py) | Fetch Steam + SteamSpy data → CSV |
| [`data-retrieval-test.py`](data-retrieval-test.py) | Smoke test for retrieval |
| [`data/single-player-games.csv`](data/single-player-games.csv) | Primary raw input (~10.7k games) |
| `data/single-player-games-cleaned.parquet` | **Generated** cleaned dataset (gitignored) |
| `visualizations/` | **Generated** EDA and model plots (gitignored) |

Sample CSVs (`single-player-games-small.csv`, etc.) and API caches are for local testing only.

---

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   cd /path/to/steam-price-analysis
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Steam Web API key** (required for data collection): create one at [Steam Web API](https://steamcommunity.com/dev/apikey) and set it in `.env`:

   ```bash
   STEAM_WEB_API_KEY=your_key_here
   ```

---

## Run the notebook

1. Ensure `data/single-player-games.csv` exists (see [data retrieval](#data-retrieval) below).
2. Open [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb) and **Run All**.
3. Generated locally:
   - `data/single-player-games-cleaned.parquet`
   - `visualizations/*.png` (EDA §8, tags §8b, OLS §9, model comparison §10)

Before committing the notebook, **clear cell outputs** to avoid large diffs (`Clear All Outputs` in the notebook UI).

---

## Data retrieval

```bash
python data-retrieval.py
```

Default output: `data/single-player-games.csv`. See `python data-retrieval.py --help` for options.

Smoke test: `python data-retrieval-test.py`

---

## Notes

- Store and SteamSpy APIs are rate-limited; large pulls take time.
- CSV row count is **matches**, not `--max-apps` examined.
