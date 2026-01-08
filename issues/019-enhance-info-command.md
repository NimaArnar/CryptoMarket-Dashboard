# Enhancement: Show full coin details in /info command

## Description
The `/info` command currently shows basic information about a coin. Users need more comprehensive details including circulating supply and price indexing from the start date.

## Current Behavior
The `/info` command shows:
- Category and Group
- Latest Market Cap
- Latest Price (if available)
- Latest Date
- Data Points count
- First Date
- Last Date

## Expected Behavior
The `/info` command should show additional information:
- **Circulating Supply** (quantity supply) - Total circulating supply of the coin
- **Current Indexed Price from Start Date** - Show price indexed to 100 (or percentage change) from the first available date
- **Price Change from Start** - Percentage change from first date to current
- **All-time High/Low** - Maximum and minimum prices in the dataset
- **Market Cap Change** - Percentage change in market cap from start date

## Example Output
```
📊 BTC Information

📂 Category: Layer 1
🏷️ Group: Bitcoin

💎 Latest Market Cap: $850,234,567,890
💵 Latest Price: $43,250.00
📅 Date: 2026-01-06

📊 Supply Information:
🪙 Circulating Supply: 19,654,321 BTC
📈 Total Supply: 21,000,000 BTC

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

## Impact
- **High** user experience improvement
- Provides comprehensive coin analysis
- Helps users understand coin performance over time
- Standard feature in crypto analysis tools

## Suggested Implementation

### 1. Get Circulating Supply
Use CoinGecko API to fetch circulating supply:
```python
# In _load_single_coin_data or new function
from src.data.fetcher import fetch_coin_data  # May need to create this

coin_data = fetch_coin_data(coin_id)
circulating_supply = coin_data.get('circulating_supply', 0)
total_supply = coin_data.get('total_supply', 0)
```

### 2. Calculate Indexed Price
```python
# Get first price and current price
first_price = price_series.iloc[0]
current_price = price_series.iloc[-1]

# Calculate indexed price (first = 100)
indexed_price = (current_price / first_price) * 100
price_change_pct = ((current_price - first_price) / first_price) * 100

# All-time high/low
all_time_high = price_series.max()
all_time_high_date = price_series.idxmax()
all_time_low = price_series.min()
all_time_low_date = price_series.idxmin()
```

### 3. Calculate Market Cap Change
```python
# Get first and current market cap
first_mc = series.iloc[0]
current_mc = series.iloc[-1]

mc_change_pct = ((current_mc - first_mc) / first_mc) * 100
```

## Location
`telegram_bot.py`, `info_command` function, lines 1911-2015

## Priority
High - User Experience

## Related
- CoinGecko API: https://www.coingecko.com/en/api/documentation
- May need to add new API endpoint for coin details
- Consider caching supply data to avoid rate limits

