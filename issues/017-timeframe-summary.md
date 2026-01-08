# Feature: 1d, 1w, 1m and 1y summary for coins in Telegram bot

## Description
Add a command to get price/market cap summaries for different timeframes (1 day, 1 week, 1 month, 1 year).

## Command Format
```
/summary <SYMBOL>
/summary <SYMBOL> 1d
/summary <SYMBOL> 1w
/summary <SYMBOL> 1m
/summary <SYMBOL> 1y
```

## Example Output
```
User: /summary BTC
Bot: 📊 BTC Summary (1 Year)
     💵 Current Price: $43,250.00
     📈 1d Change: +2.45%
     📈 1w Change: +5.12%
     📈 1m Change: +12.34%
     📈 1y Change: +89.67%
     
     💎 Market Cap: $850,234,567,890
     📊 1d MC Change: +2.45%
     📊 1w MC Change: +5.12%
     📊 1m MC Change: +12.34%
     📊 1y MC Change: +89.67%
     
     📉 Low (1y): $28,500.00
     📈 High (1y): $48,900.00
```

## Implementation Details
- Calculate percentage changes for each timeframe
- Show both price and market cap changes
- Include high/low values for the period
- Format numbers nicely (commas, 2 decimal places)
- Handle cases where data doesn't go back 1 year

## Timeframe Calculations
- **1d**: Change from 24 hours ago
- **1w**: Change from 7 days ago
- **1m**: Change from 30 days ago
- **1y**: Change from 365 days ago (or available data)

## Additional Features
- Show all timeframes at once (default)
- Allow filtering to specific timeframe
- Include volume data if available
- Show percentage and absolute change

## Technical Notes
- Use existing data from DataManager
- Calculate changes from historical data
- Handle missing data gracefully
- Cache calculations if needed

## Priority
High

## Labels
enhancement, feature, telegram-bot, high-priority

