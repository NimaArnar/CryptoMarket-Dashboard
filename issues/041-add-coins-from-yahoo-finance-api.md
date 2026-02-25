# Feature: Add coins not in program and load data from Yahoo Finance (or similar) API

## Description

Allow users to request data for **coins/symbols that are not in the built-in list** (e.g. not in `COINS`). Fetch price (and optionally other data) from an external source such as **Yahoo Finance API** (or another free, available API) so the bot can support arbitrary tickers (e.g. stocks, other crypto tickers not on CoinGecko in the app).

## Current Behavior

- Only coins defined in `src/constants.py` (COINS) are supported for price, info, chart, correlation, etc.
- Unknown symbols get an error like "Coin 'XYZ' not found."

## Expected Behavior

- If user requests a symbol not in the program's list, the bot attempts to **resolve and load it from an external API** (e.g. Yahoo Finance).
- For resolved symbols: show at least **price** (and optionally simple stats); chart/summary could be supported if the API provides history.
- Clear indication when data comes from "external" source (e.g. "Data from Yahoo Finance") so users know it's not from the dashboard's CoinGecko data.

## Implementation Notes

- **Yahoo Finance**: e.g. `yfinance` (Python library) or Yahoo Finance API; supports many tickers (crypto and stocks). Validate availability and rate limits.
- **Fallback**: Keep current behavior for symbols in COINS; only call external API when symbol not in COINS.
- **Caching**: Consider short TTL cache for external symbols to avoid repeated API calls.
- **Security/validation**: Sanitize user input (symbol format); limit length and character set to avoid abuse.

## Location

- New module or functions for "external" symbol resolution and price fetch (e.g. Yahoo Finance).
- `telegram_bot.py`: In `price_command` (and optionally `/info`, `/chart`, `/summary`), if symbol not in COINS, call external fetcher and format response.

## Priority

Medium - Feature / Data source

## Labels

feature, telegram-bot, external-api, yahoo-finance, price
