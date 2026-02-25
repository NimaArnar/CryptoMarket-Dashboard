# Feature: Add commodities support (Gold XAU, Silver XAG, Copper XCU) to Telegram bot

## Description

Extend the Telegram bot to support **commodities**, not just cryptocurrencies. At minimum, add:

- **Gold** – XAU
- **Silver** – XAG
- **Copper** – XCU

These should behave like \"coins\" in the bot for price queries (and possibly charts), even though they are commodities/metal codes (ISO 4217).

## Current Behavior

- Only crypto assets defined in `src/constants.py` (`COINS`) are supported.
- `/price`, `/latest`, `/info`, `/summary`, `/chart`, `/corr` work only for the configured coin symbols (e.g. BTC, ETH, etc.).
- XAU, XAG, XCU are not recognized; attempting to query them results in errors or \"coin not found\".

## Expected Behavior

- The bot should **recognize XAU, XAG, XCU** and be able to:
  - Return **current price** (e.g. vs USD).
  - Optionally show **basic info** and/or **simple charts** using daily prices.
- Data source should be a reliable commodities/FX data provider (e.g. Yahoo Finance, another free API, or the same source used for other external assets).
- Commodities should be clearly labeled as such (e.g. \"Gold (XAU)\") so users understand they are not standard crypto coins.

## Implementation Notes

- Decide where to put these symbols:
  - Option A: Add to `COINS` in `src/constants.py` with a special category/group (e.g. `\"commodities\"`).
  - Option B: Treat them as **external symbols** similar to the future Yahoo Finance feature (issue 041) and fetch prices from that API.
- For prices and charts:
  - Use an API that provides **XAU/USD**, **XAG/USD**, **XCU/USD** (or similar).
  - Cache results to avoid hitting rate limits.
- For UX:
  - Allow `/price XAU`, `/price XAG`, `/price XCU`.
  - Optionally add buttons for these under Data Queries (e.g. \"Gold\", \"Silver\", \"Copper\") if it fits the design.

## Location

- `src/constants.py`: Decide if XAU/XAG/XCU belong in `COINS` or a separate structure.
- New module or reuse external API integration (e.g. from issue 041) for fetching commodity prices/history.
- `telegram_bot.py`: Ensure `/price` (and optionally `/chart`, `/info`) can handle XAU/XAG/XCU via the chosen data source.

## Priority

Medium - Feature / Data coverage (commodities)

## Labels

feature, telegram-bot, commodities, external-api, price, chart

