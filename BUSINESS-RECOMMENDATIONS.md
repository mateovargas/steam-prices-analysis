# Business recommendations — Steam single-player pricing

Based on analysis of **~10,700 paid single-player Steam games** ([`FINDINGS.md`](FINDINGS.md)). These recommendations are for publishing, product, and marketing leaders—not data scientists.

---

## What we learned in plain terms

Most games in this segment list around **$6** (median **$5.99**; 75% are below **$13**). Price correlates only modestly with estimated sales (~**0.29**). Genre, Steam tags, and factors we cannot see in public data—quality, marketing, franchise strength—matter more than list price alone.

Our models explain at best **~44%** of variation in estimated owners. That is useful for comparison and planning, but a large share of success remains unpredictable from catalog metadata.

**Critical caveat:** A linear model’s “revenue-maximizing” price often lands at the **top of the observed range** (~$40). That reflects confounding (hit games tend to be both popular and expensive), not proof that raising price drives sales. Do not treat model output as a launch-price mandate.

---

## Recommendations

### 1. Anchor pricing on comps, not the catalog median alone

Build a **comp set** of 10–20 titles that match your game on genre, tag profile (e.g., Story Rich, Atmospheric), scope, and visual quality—not the entire Steam catalog. Use their price band as the primary reference. The catalog median (~$6) is a floor for many indie titles, not a target for premium or niche experiences.

### 2. Use models to frame scenarios, not to set the final number

Run **what-if** discussions: “If we launch at $9.99 vs. $14.99 with similar metadata, what does the model suggest for relative reach?” Present ranges and assumptions clearly. Prefer the **linear baseline** when explaining trade-offs to non-technical partners; use **tree-based models** when you need the best forecast among similar games.

### 3. Validate with forward-looking signals before commit

Retrospective catalog data cannot replace **wishlists, demo downloads, playtest feedback, influencer previews, and soft-launch experiments**. Weight these heavily in the final pricing decision. If wishlist conversion is weak at a proposed price point, adjust before full launch rather than relying on historical regression.

### 4. Align positioning with tags that correlate with reach

Tags such as **Story Rich**, **Atmospheric**, and **Great Soundtrack** appear alongside higher estimated ownership in our data. Ensure store page positioning (tags, capsule, description) honestly reflects what you deliver. Misaligned positioning hurts conversion regardless of price.

### 5. Plan promos and regional pricing separately from list price

This study uses **snapshot list prices**, not sale events or regional tiers. Set a defensible base list price from comps, then design **discount strategy** and **regional pricing** as distinct decisions supported by sales data after launch.

### 6. Invest in better data for the next decision cycle

Priority upgrades: title-specific comp universes, **Steam review scores**, wishlist metrics, and **price history** across sales events. First-party sales data should replace or blend with SteamSpy estimates when available.

---

## Bottom line

**Do not** read this analysis as “charge $X and succeed.” **Do** use it to benchmark against similar games, stress-test pricing scenarios with explicit assumptions, and invest in pre-launch validation. The evidence supports informed discussion—not a single optimal price from historical noise.

For methodology, metrics, and charts, see [`FINDINGS.md`](FINDINGS.md) and [`steam-price-analysis.ipynb`](steam-price-analysis.ipynb).
