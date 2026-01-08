# Enhancement: Reduce emojis in data display - too crowded

## Description
The bot uses too many emojis in data display messages, making the output visually crowded and harder to read. Each line has an emoji prefix, which creates visual clutter and reduces readability.

## Current Behavior
Almost every line in data displays has an emoji:
- `/info` command example:
  ```
  📊 BTC Information
  
  📂 Category: Layer 1
  🏷️ Group: Bitcoin
  
  💎 Latest Market Cap: $850,234,567,890
  📅 Date: 2026-01-06
  
  💵 Latest Price: $43,250.00
  
  📊 Supply Information:
  🪙 Circulating Supply: 19.65B BTC
  📈 Total Supply: 21.00B BTC
  
  📈 Price Performance:
  💰 Current Price: $43,250.00
  📊 Indexed Price (Start = 100): 1,234.56
  📈 Change from Start: +1,134.56%
  📈 All-time High: $69,000.00 (2021-11-10)
  📉 All-time Low: $3,122.00 (2018-12-15)
  
  💎 Market Cap Performance:
  📊 Current Market Cap: $850,234,567,890
  📈 Change from Start: +2,345.67%
  
  📅 Data Range:
  📅 First Date: 2017-01-01
  📅 Last Date: 2026-01-06
  📈 Data Points: 3,287
  ```

- `/price` command example:
  ```
  💰 BTC Price
  
  💵 Price: $43,250.00
  💎 Market Cap: $850,234,567,890
  📅 Date: 2026-01-06
  📈 24h Change: +2.5%
  ```

## Expected Behavior
Reduce emoji usage to make data more readable:
- Use emojis only for section headers (not every line)
- Use emojis sparingly for key metrics only
- Consider using simple text labels or separators instead

### Suggested Format:
```
📊 BTC Information

Category: Layer 1
Group: Bitcoin

Latest Market Cap: $850,234,567,890
Date: 2026-01-06
Latest Price: $43,250.00

📊 Supply Information
Circulating Supply: 19.65B BTC
Total Supply: 21.00B BTC

📈 Price Performance
Current Price: $43,250.00
Indexed Price (Start = 100): 1,234.56
Change from Start: +1,134.56%
All-time High: $69,000.00 (2021-11-10)
All-time Low: $3,122.00 (2018-12-15)

💎 Market Cap Performance
Current Market Cap: $850,234,567,890
Change from Start: +2,345.67%

📅 Data Range
First Date: 2017-01-01
Last Date: 2026-01-06
Data Points: 3,287
```

## Impact
- **High** user experience improvement
- Better readability and cleaner appearance
- More professional look
- Easier to scan and find information

## Suggested Implementation

### Option 1: Remove emojis from data lines, keep only section headers
- Keep emojis for main sections (📊, 📈, 💎, 📅)
- Remove emojis from individual data points
- Use consistent formatting with colons

### Option 2: Use minimal emojis
- Keep only 1-2 emojis per section
- Use emojis only for the most important metrics
- Use text labels for everything else

### Option 3: Use emojis only for visual indicators
- Keep emojis for directional indicators (📈 up, 📉 down)
- Remove emojis from static labels
- Use emojis only when they add meaning (not decoration)

## Location
- `telegram_bot.py`:
  - `info_command()` function (lines ~2018-2182)
  - `price_command()` function (lines ~1684-1765)
  - `marketcap_command()` function
  - `latest_command()` function
  - `_format_latest_prices()` function
  - Any other data display functions

## Priority
Medium - User Experience

## Related
- Issue #19: Enhanced `/info` command (this issue makes the enhanced info even more crowded)

