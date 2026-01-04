# Feature: 1 year chart image of coins in Telegram bot

## Description
Add a command to generate and send a 1-year price/market cap chart image for any coin.

## Command Format
```
/chart <SYMBOL>
/chart <SYMBOL> price
/chart <SYMBOL> marketcap
```

## Example Output
- Chart image showing 1 year of data
- Price chart or Market Cap chart (user choice)
- Similar styling to dashboard charts
- Include smoothing options if possible

## Implementation Details
- Generate chart using Plotly
- Export as PNG/JPEG image
- Use existing data from cache or fetch if needed
- Support both price and market cap views
- Include date range, coin symbol, and key metrics

## Chart Features
- 1 year of daily data
- Optional smoothing (7D SMA, 14D EMA, 30D SMA)
- Price or Market Cap view
- Include latest value and change indicators
- Professional styling matching dashboard

## Technical Requirements
- Use `kaleido` for image export
- Chart size: Optimized for Telegram
- Use existing chart building functions
- Cache generated images (optional, to save computation)

## Dependencies
- `kaleido>=0.2.1` (already in requirements.txt)
- Plotly chart generation
- Data from cache or API

## Priority
Medium

## Labels
enhancement, feature, telegram-bot, visualization

