# steam-price-analysis

Analysis of **paid, single-player Steam games**: data collection, cleaning, exploratory visualization, and **multiple regression models** relating list price and metadata to SteamSpy’s estimated owner counts.

**Main deliverable:** [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb) — run all cells top to bottom after setup below.

---

## Key findings (summary)

**Business question:** What list price and game characteristics are associated with stronger *estimated* sales on Steam?

| Finding | Detail |
|---------|--------|
| **Dataset** | ~**10,736** games after cleaning; target = log of SteamSpy owner-range **midpoint** (sales proxy, not verified units). |
| **Typical price** | Median list price **$5.99**; 75th percentile **$12.99**. |
| **Price vs owners** | Correlation with log owners is **modest (~0.29)**; genre/tags and unmeasured quality dominate. |
| **Linear “optimal price” (§9)** | Catalog OLS often peaks at the **high end of observed prices**—reflects confounding (hits are expensive *and* popular), **not** a causal pricing rule. |
| **Model comparison (§10)** | Seven models tested with **holdout R²**, **RMSE/MAE**, and **5-fold CV**. **Gradient Boosting / Random Forest** typically best (~**0.44** test R²); linear models ~**0.33** with full genre + tag features. |

**Recommendation for stakeholders:** Use models to **explore scenarios and rank approaches**, not to set launch price without comps, wishlist data, or experiments.

**Detailed review:** see [`FINDINGS.md`](FINDINGS.md) for the full narrative, metrics tables, chart index, and stakeholder recommendations.

Full interpretation, plots, and next steps are also in **§8–§11** of the [notebook](steam-price-analysis.ipynb).

---

## Project layout

| Path | Purpose |
|------|---------|
| [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb) | Cleaning, EDA, modeling, findings |
| [`data-retrieval.py`](data-retrieval.py) | Fetch Steam + SteamSpy data → CSV |
| [`data/single-player-games.csv`](data/single-player-games.csv) | Raw input (~10.7k games) |
| `data/single-player-games-cleaned.parquet` | **Generated locally** by notebook (gitignored) |
| `visualizations/` | **Generated locally** EDA and model plots (gitignored) |
| [`requirements.txt`](requirements.txt) | Python dependencies |

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

1. Ensure `data/single-player-games.csv` exists (see data retrieval below).
2. Open [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb) and **Run All**.
3. Outputs appear locally:
   - `data/single-player-games-cleaned.parquet`
   - `visualizations/*.png`, including:
     - **EDA (§8):** price/owners histograms, scatter plots, genre box/bar charts, correlation heatmap
     - **Tags (§8b):** `tag_prevalence_top15.png`, `mean_log_owners_by_top_tags.png`
     - **OLS (§9):** `optimal_price_revenue_curve.png`, `ols_actual_vs_predicted_test.png`, `ols_residuals_test.png`
     - **Models (§10):** `model_comparison_test_r2.png`, `model_comparison_rmse_mae.png`, `model_comparison_train_vs_test_r2.png`, `model_comparison_cv_vs_test_r2.png`, `best_model_actual_vs_predicted.png`, `best_model_feature_importance.png`

**Modeling notes:** Section 10 compares OLS, Ridge, Lasso, Random Forest, KNN (grid search), MLP, and Gradient Boosting with cross-validation where noted. Evaluation uses **R²** (primary), **RMSE**, and **MAE** on a held-out 20% test set.

Before committing the notebook, **clear cell outputs** to avoid large diffs (`Clear All Outputs` in the notebook UI).

---

## Data retrieval

```bash
python data-retrieval.py
```

Default output: `data/single-player-games.csv`. See `python data-retrieval.py --help` for options (`--max-apps`, `--csv-path`, caches, etc.).

Smoke test:

```bash
python data-retrieval-test.py
```

---

## Limitations

- SteamSpy **owner ranges** are estimates, not audited sales.
- Cross-sectional data supports **association**, not causal “optimal price.”
- Engagement fields (`steamspy_ccu`, median playtime) are often zero in this snapshot.

---

## Notes

- Store and SteamSpy APIs are rate-limited; large pulls take time.
- CSV row count is **matches**, not `--max-apps` examined.
