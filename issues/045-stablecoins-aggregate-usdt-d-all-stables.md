# Feature: Use aggregate stablecoin supply instead of only USDT / USDT.D

## Description

Currently the dashboard and bot use **USDT** and the synthetic **USDT.D** dominance metric as the primary stablecoin reference. This issue proposes replacing that with an **aggregate stablecoin metric** that uses **all major stablecoins in crypto**, not just USDT.

Where possible, use an external API such as **DefiLlama stablecoin charts**:

- DefiLlama docs: [`/stablecoincharts/all`](https://api-docs.defillama.com/#tag/stablecoins/get/stablecoincharts/all)

If that API is not free or practical to integrate, approximate the aggregate by summing the **largest N stablecoins** (e.g. top 5) from existing data.

## Current Behavior

- `DOM_SYM = "USDT.D"` and related logic derive a **USDT dominance** metric from market caps.
- Only **USDT** (and USDT.D) are used as the stablecoin reference in charts/correlations.
- Other stablecoins (USDC, DAI, etc.) are not included in the dominance metric.

## Expected Behavior

- Introduce an **aggregate stablecoin metric** that represents the sum of all significant stablecoins:
  - Either sourced directly from **DefiLlama stablecoin API**, or
  - Computed locally by summing MC data for the **largest stablecoins** present in our dataset (e.g. USDT, USDC, DAI, BUSD, TUSD).
- Replace (or add alongside) `USDT.D` with an **aggregate stablecoin dominance** metric:
  - e.g. `STABLES.D = (sum of stablecoin MC) / (sum of all tracked MC)`.
- Use this aggregate stablecoin metric wherever USDT.D is currently used (charts, correlation, etc.), or expose both for comparison.

## Implementation Notes

### Data Source

- **Preferred:** Use DefiLlama stablecoin charts:
  - Endpoint: [`/stablecoincharts/all`](https://api-docs.defillama.com/#tag/stablecoins/get/stablecoincharts/all)
  - Fetch historical total stablecoin market cap, and optionally per-coin breakdown.
  - Map the DefiLlama time series into our internal format (date-indexed Series).
  - Confirm rate limits and whether the API is free for this use.

- **Fallback (if DefiLlama not available or not free):**
  - Identify the **top 5 stablecoins** (e.g. USDT, USDC, DAI, BUSD, TUSD) already tracked or accessible via CoinGecko / our existing pipeline.
  - Compute `STABLES = USDT + USDC + DAI + ...` using their market cap series.
  - Use this sum everywhere the aggregate stablecoin metric is needed.

### Code Changes

- `src/constants.py`:
  - Consider adding a new symbol (e.g. `STABLES.D`) and metadata for aggregate stables.

- `src/data_manager.py` / `src/data/*`:
  - Integrate stablecoin data:
    - Either via a new fetcher for DefiLlama, or
    - By summing selected stablecoins from existing CoinGecko data.

- `src/app/callbacks.py`:
  - Where `DOM_SYM` (USDT.D) is used for dominance/correlation, allow using the new aggregate stablecoin metric instead (or in addition).
  - Ensure correlation logic and views handle the new metric correctly.

- `telegram_bot.py`:
  - If USDT.D is surfaced anywhere (e.g. in coins list or charts), consider updating text to mention aggregate stablecoins instead of just USDT.

## Priority

Medium – Improves data quality and representativeness of stablecoin metrics.

## Labels

feature, data, stablecoins, defi, telegram-bot, dashboard

