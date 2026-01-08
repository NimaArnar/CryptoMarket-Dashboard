# Feature: Correlation between 2 coins in Telegram bot (Complete with Chart Image)

## Description
Extend the correlation command to include a visual scatter plot chart image showing the correlation between two coins.

## Command Format
```
/corr <COIN1> <COIN2>
```

## Example Output
1. Numerical correlation data (same as issue #13)
2. Chart image showing:
   - Scatter plot of returns
   - Green markers for positive days
   - Red markers for negative days
   - Regression line
   - Correlation and beta displayed on chart

## Implementation Details
- Generate chart using Plotly (same as dashboard)
- Export chart as image (PNG/JPEG)
- Send image via Telegram bot
- Use existing chart generation from `src/visualization/chart_builder.py` or `src/app/callbacks.py`

## Technical Requirements
- Use `kaleido` or similar library for static image export
- Image size: Optimized for Telegram (max 10MB, recommended < 1MB)
- Chart styling: Match dashboard style
- Include legend and labels

## Dependencies
- `kaleido>=0.2.1` (already in requirements.txt)
- Plotly chart generation
- Image optimization

## Priority
Medium

## Labels
enhancement, feature, telegram-bot, visualization

