# Steam single-player pricing analysis — detailed findings

This document expands on the results in [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb). It is written for review before presenting to stakeholders. Numbers below were produced from the cleaned dataset (`data/single-player-games-cleaned.parquet`, **10,736 games**) using the same train/test split and feature sets as the notebook (`random_state=42`, 80/20 holdout).

---

## 1. Business problem

Indie and mid-tier publishers need evidence-informed **list prices** on Steam. The core question is:

> What list price and game characteristics are **associated** with stronger estimated sales on Steam?

We proxy “sales strength” with **SteamSpy owner-range midpoints** (`owners_mid`, modeled as `log_owners_mid`). That is a noisy, cross-sectional estimate—not verified unit sales. All conclusions below are about **patterns in historical catalog data**, not causal pricing rules.

---

## 2. Data and methodology

### 2.1 Source and scope

| Item | Detail |
|------|--------|
| **Input** | `data/single-player-games.csv` (~10.7k paid, single-player Steam games) |
| **After cleaning** | **10,736** rows in `single-player-games-cleaned.parquet` |
| **Target** | `log_owners_mid` = log of SteamSpy owner-range midpoint |
| **Price field** | `price_usd` (list price at snapshot time) |
| **Features** | `price_usd`, `age_days`, tag/developer/publisher counts, top-18 genre flags (`genre__*`), top-15 tag flags (`tag__*`) |

### 2.2 Cleaning filters (sequential)

Games were dropped if they lacked usable owner estimates, price, release date, or genre/tag metadata needed for modeling. All retained games have **paid** list prices (minimum observed **$0.49**; no free-to-play rows in the final set).

### 2.3 Important limitations

- **SteamSpy estimates** are ranges, not audited sales; many games sit at the **10,000-owner floor** (median `owners_mid` = **10,000**).
- **Single snapshot** — no price history, sales events, or wishlist data.
- **Engagement fields** (`steamspy_ccu`, median playtime) are often zero in this extract and were not primary predictors.
- **Cross-sectional association ≠ causation** — successful titles may charge more *because* they are hits, not the other way around.

---

## 3. Exploratory data analysis (§8–§8b)

### 3.1 Price distribution

| Statistic | Value |
|-----------|-------|
| Median list price | **$5.99** |
| 75th percentile | **$12.99** |
| Mean list price | **$9.30** |
| Maximum | **$199.99** |

Most games cluster in the **$3–$13** band. The long right tail (premium and niche titles) pulls the mean above the median.

**Chart:** `visualizations/price_usd_hist.png`

### 3.2 Owner / sales proxy distribution

Estimated owners are **highly skewed**. On a log scale the distribution is more usable for regression. Many games share the same lower bound (10k owners), which compresses variation at the low end.

| Statistic | `owners_mid` |
|-----------|----------------|
| Median | **10,000** |
| 75th percentile | **35,000** |
| Mean | **142,912** (inflated by blockbuster outliers) |
| Max | **35,000,000** |

**Chart:** `visualizations/owners_mid_log_hist.png`

### 3.3 Price vs. estimated owners

Pearson correlation between `price_usd` and `log_owners_mid`: **≈ 0.29**.

That is a **modest positive** relationship: higher-priced games tend to have somewhat higher estimated owners, but the scatter is wide. Genre, quality, marketing, and franchise effects dominate what this simple correlation can explain.

**Charts:** `visualizations/price_vs_log_owners_scatter.png`, `visualizations/discount_vs_log_owners_scatter.png`

### 3.4 Genre patterns

| Genre (primary) | Share of catalog |
|-----------------|------------------|
| Action | **4,901** games (~46%) |
| Adventure | **2,223** |
| Casual | **1,609** |

Mean log owners by genre flag (multi-hot) shows **Strategy**, **Simulation**, and **RPG** titles with slightly higher typical estimated reach than Action, but differences are moderate and overlap is large.

**Charts:** `visualizations/price_by_primary_genre_box.png`, `visualizations/mean_log_owners_by_primary_genre_bar.png`

### 3.5 Tag patterns (§8b)

Among the top 15 Steam tags encoded as features, tags associated with **higher mean log owners** (among games carrying that tag, n > 50) include:

| Tag | Mean log owners | Games with tag |
|-----|-----------------|----------------|
| Great Soundtrack | **11.08** | 1,222 |
| Atmospheric | **11.00** | 1,580 |
| Story Rich | **10.99** | 1,399 |
| Singleplayer | **10.88** | 3,901 |

These tags correlate with **premium, narrative, or polish-heavy** experiences—not necessarily with “charge more.” They help explain why metadata beyond price improves prediction.

**Charts:** `visualizations/tag_prevalence_top15.png`, `visualizations/mean_log_owners_by_top_tags.png`

### 3.6 Numeric feature correlations

Age (`age_days`, median ≈ **3,186 days** ≈ 8.7 years) and counts (developers, publishers, tags) show weak to moderate relationships with owners. No single numeric feature besides price stands out as a dominant driver.

**Chart:** `visualizations/correlation_heatmap_numeric.png`

---

## 4. Linear regression and “optimal price” (§9)

### 4.1 Model specification

**OLS** predicts `log_owners_mid` from:

- `price_usd`
- `age_days`, `tag_count`, `developer_count`, `publisher_count`
- Top-K **`genre__*`** flags (no tag flags in this section—narrower, interpretable spec)

Train/test split: 80/20, `random_state=42`.

### 4.2 Results

| Metric | Value |
|--------|-------|
| Test **R²** | **≈ 0.30** |
| **Price coefficient** | **+0.023** (positive on log owners) |

A positive price coefficient means that, holding genre and counts fixed, the fitted line associates **higher list price with higher estimated owners**. That is almost certainly **confounding**: hit games can sustain higher prices *and* accumulate more owners. It does **not** imply that raising price causes more sales.

### 4.3 Revenue proxy curve

The notebook sweeps a synthetic **reference game** (median counts, modal Action genre) across a price grid and plots **revenue proxy** = `price × exp(predicted log owners)`.

Because the price term enters positively, the curve often peaks at the **top of the grid (~$40)**—the highest price tested—not at the catalog median (~$6). Treat that peak as a **model artifact**, not a launch-price recommendation.

**Charts:**

- `visualizations/optimal_price_revenue_curve.png` — exploratory revenue proxy vs. price
- `visualizations/ols_actual_vs_predicted_test.png` — holdout fit quality
- `visualizations/ols_residuals_test.png` — systematic errors (heavy tails, underestimation of blockbusters)

### 4.4 Stakeholder takeaway for §9

Use this linear model for **transparent what-if conversations** (“if we price like a typical Action game at $X, what does the formula predict?”). Do **not** use the revenue-curve maximum as a pricing target.

---

## 5. Model comparison (§10)

Seven regressors were compared on the **full feature set** (price, counts, all `genre__*` and `tag__*` columns). Same 80/20 holdout and `random_state=42`.

### 5.1 Holdout performance (test set)

| Model | Test R² | 5-fold CV R² (train) | RMSE | MAE |
|-------|---------|------------------------|------|-----|
| **Gradient Boosting** | **0.439** | 0.416 | 1.059 | 0.783 |
| **Random Forest** | **0.434** | 0.406 | 1.064 | 0.780 |
| MLP | 0.351 | 0.330 | 1.138 | 0.849 |
| KNN | 0.332 | 0.322 | 1.155 | 0.829 |
| OLS | 0.331 | 0.308 | 1.156 | 0.867 |
| Ridge | 0.330 | 0.308 | 1.157 | 0.868 |
| Lasso | 0.329 | 0.308 | 1.158 | 0.867 |

**Primary metric:** test **R²** (share of variance in log owners explained on holdout data). **RMSE/MAE** measure typical error on the log scale (lower is better).

### 5.2 Interpretation

1. **Tree ensembles win** — Gradient Boosting and Random Forest improve test R² by roughly **+0.10–0.11** over linear models (~0.44 vs. ~0.33). Nonlinear **interactions** among price, genre, and tags matter for this proxy target.
2. **Linear models are tied** — OLS, Ridge, and Lasso perform similarly once genre + tag dummies are included; regularization does not materially change rankings here.
3. **MLP is middle tier** — Beats linear models slightly but trails trees; may need more tuning/data to justify complexity.
4. **KNN ≈ linear baseline** — Local similarity in feature space adds little beyond global linear structure for this feature matrix.
5. **CV vs. test** — CV R² tracks test R² without large gaps, suggesting modest overfitting for tree models at the chosen hyperparameters.

Even the best model explains **less than half** of the variance in log owners. A large share of success is **unobserved** (quality, marketing, timing, franchise, visibility).

**Charts:**

- `visualizations/model_comparison_test_r2.png`
- `visualizations/model_comparison_rmse_mae.png`
- `visualizations/model_comparison_train_vs_test_r2.png`
- `visualizations/model_comparison_cv_vs_test_r2.png`
- `visualizations/best_model_actual_vs_predicted.png`
- `visualizations/best_model_feature_importance.png`

### 5.3 Feature importance (best tree model)

The winning model’s importance plot highlights which metadata fields the ensemble uses most. Typically **price**, select **genre/tag** flags, and **age** rank highly; exact ordering should be read from the regenerated plot after running §10. Importance reflects **predictive contribution**, not causal effect.

---

## 6. Synthesis: what we can and cannot claim

### What the analysis supports

- **Typical Steam list price** for this segment is about **$6**; most games sit below **$13**.
- **Price alone** is a weak signal; **genre, tags, and unmeasured quality** dominate.
- **Nonlinear models** predict the ownership proxy more accurately than linear baselines when rich metadata is available.
- **Transparent linear models** are still useful for scenario framing, with clear caveats about confounding.

### What the analysis does not support

- “Set your price to $X and maximize revenue.”
- “Higher price causes more owners.”
- “SteamSpy midpoint equals true sales.”
- Causal **price elasticity** from a single cross-section.

---

## 7. Recommendations

### For product / publishing stakeholders

1. **Anchor on market comps** — Same genre, tag profile, and price band as your title; median catalog price (~$6) is a starting point, not a formula output.
2. **Use models for discussion, not decree** — Compare scenarios (“at $9.99 vs. $14.99, what does the model expect for similar metadata?”) while naming assumptions.
3. **Validate before launch** — Wishlists, demos, playtests, and regional pricing experiments outweigh retrospective catalog regression.
4. **Match model to question** — Use **§9 OLS** when explaining trade-offs; use **§10 tree model** when prioritizing forecast accuracy on similar metadata.

### For analytics / data team

1. Refit on **title-specific comp sets** rather than the full catalog.
2. Add **review scores**, **Metacritic**, or **Steam review %** if available.
3. Build a **longitudinal panel** (price changes, sales events) for elasticity.
4. Replace or blend SteamSpy with **first-party sales** where possible.

---

## 8. Next steps

| Priority | Action |
|----------|--------|
| High | Curate a **comp universe** per upcoming title and refit |
| High | Collect **wishlist / demo conversion** data for launch titles |
| Medium | Ingest **review sentiment** and update features |
| Medium | Track **price history** and promo windows for causal work |
| Low | Hyperparameter tuning for MLP / deeper ensembles (diminishing returns vs. data quality) |

---

## 9. Reproducing results

1. Follow setup in [`README.md`](README.md).
2. Run all cells in [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb).
3. Generated artifacts:
   - `data/single-player-games-cleaned.parquet`
   - `visualizations/*.png`

Section numbers in this document map to notebook sections **§8–§11**. If you change `TAG_TOP_K`, genre counts, or filters, re-run the notebook and refresh the metrics above.

---

## 10. Quick reference — executive summary

| Topic | Headline |
|-------|----------|
| Dataset | ~**10,736** paid single-player games |
| Typical price | Median **$5.99** |
| Price vs. owners | Correlation **~0.29**; weak alone |
| §9 linear “optimum” | Often **top of price grid** → confounding, not advice |
| Best predictors | **Gradient Boosting / Random Forest**, test R² **~0.44** |
| Linear baseline | Test R² **~0.33** with full genre + tags |
| Bottom line | Use for **exploration and comps**, not causal launch pricing |
