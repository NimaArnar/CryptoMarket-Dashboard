# Enhancement: Add timestamp for latest update in relevant sections

## Description
Users need to know when the data was last updated. Add timestamps showing the latest update time for sections that display data (price, marketcap, latest, info).

## Current Behavior
- Commands show date but not time
- No indication of when data was last updated/refreshed
- Users don't know if data is fresh or stale

## Expected Behavior
- Add timestamp (date + time) to data displays
- Show "Last updated: YYYY-MM-DD HH:MM:SS" or similar
- Include in:
  - `/price` command
  - `/marketcap` command
  - `/latest` command
  - `/info` command

## Example Format
```
💰 BTC Price

Price: $43,250.00
Market Cap: $850,234,567,890
Date: 2026-01-06
Last updated: 2026-01-06 14:30:45
📈 24h Change: +2.5%
```

## Location
- `telegram_bot.py`:
  - `price_command()` function
  - `marketcap_command()` function
  - `latest_command()` function
  - `info_command()` function

## Implementation Notes
- Get timestamp from the latest data point in the series
- Format as: `YYYY-MM-DD HH:MM:SS` or `YYYY-MM-DD HH:MM`
- Use the index of the latest data point (datetime)
- If only date is available, show date with time from cache file modification time or current time

## Priority
Medium - User Experience / Data Transparency

## Related
- Issue #27: Reduced emojis in data display

