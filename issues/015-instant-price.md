# Feature: Instant price of coins in Telegram bot

## Description
Add a command to get instant/real-time price of coins without requiring the dashboard to be running.

## Command Format
```
/price <SYMBOL>
/price <SYMBOL> now
```

## Current Behavior
- `/price` command requires dashboard to be running
- Loads data from DataManager (cached data)

## Proposed Behavior
- Add option to fetch fresh price from CoinGecko API
- Show instant price without dashboard dependency
- Optionally show cached price vs fresh price

## Example Usage
```
User: /price BTC now
Bot: 💰 BTC Instant Price
     💵 Current Price: $43,250.00
     📊 Market Cap: $850,234,567,890
     📈 24h Change: +2.45%
     🕐 Updated: 2026-01-05 02:51:00 UTC
```

## Implementation Details
- Add API call to CoinGecko `/simple/price` endpoint
- Cache result for 1-5 minutes to avoid rate limits
- Show both price and market cap
- Calculate 24h change if available
- Fallback to cached data if API fails

## Technical Notes
- Use existing `src/data/fetcher.py` infrastructure
- Add new function: `fetch_instant_price(symbol: str)`
- Cache in memory with TTL
- Handle rate limits gracefully

## Priority
High

## Labels
enhancement, feature, telegram-bot, high-priority

