# Feature: When using correlation, also send a 1-year chart of the two selected coins

## Description

When the user runs correlation between two coins (via `/corr` or the Correlation menu), the bot should send not only the correlation analysis and scatter plot but also a **1-year chart** showing both selected coins (e.g. price or indexed series for both on the same chart). This gives a visual timeline of how the two coins moved over the past year alongside the correlation metrics.

## Current Behavior

- User requests correlation (e.g. BTC vs ETH) → bot sends correlation text (overall/positive/negative) and scatter plot image.
- No combined 1-year price/index chart for the two coins is sent.

## Expected Behavior

- After sending the correlation result and scatter plot, the bot also sends a **1-year chart image** with both selected coins (e.g. dual series: Coin A and Coin B over the last year, same style as existing `/chart` or dashboard normalized view).
- Chart can show price or indexed (100 = start) for both coins on one image for easy comparison.

## Implementation Notes

- Reuse existing chart generation (e.g. dual-series or multi-trace plot) and dashboard/DataManager data.
- Same data source and timeframe (1y) as correlation (market cap / price from dashboard).
- Consider sending: 1) correlation text, 2) scatter image, 3) 1y comparison chart (or combine into a clear order).

## Location

- `telegram_bot.py`: correlation flow (`corr_command`, `corr_default`, `corr_coin_*` callback); add step to generate and send 1y chart for the two symbols.
- May need a helper to build a two-coin 1y chart (similar to existing single-coin chart with optional second series).

## Priority

Medium - User Experience / Feature

## Labels

feature, telegram-bot, correlation, chart, visualization
