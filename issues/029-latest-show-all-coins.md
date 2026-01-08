# Enhancement: /latest should show latest price of all coins

## Description
The `/latest` command currently shows only the top 10 coins by market cap (or all if less than 10). Users need to see the latest price of ALL coins, not just a subset.

## Current Behavior
- `/latest` shows top 10 coins by market cap if there are more than 10 coins
- Shows message: "... and X more coins"
- Users cannot see prices for all coins

## Expected Behavior
- `/latest` should show latest price of ALL coins
- If message is too long, split into multiple messages
- Display all coins with their latest prices
- Maintain pagination or message splitting if needed

## Location
- `telegram_bot.py`:
  - `latest_command()` function (lines ~1895-2020)
  - Currently limits to top 10: `symbols_to_show = sorted(...)[:10]`

## Priority
Medium - User Experience

## Implementation Notes
- Remove the top 10 limitation
- Show all coins from `dm.symbols_all`
- Ensure message splitting works correctly for large lists
- Consider pagination if needed

