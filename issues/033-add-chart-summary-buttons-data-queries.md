# Enhancement: Add Chart and Summary buttons to Data Queries menu

## Description

Add Chart and Summary buttons to the Data Queries section of the main menu (shown when using `/start` command). Both buttons should default to showing data for BTC.

## Current Behavior

- Data Queries section may not have Chart and Summary buttons
- Users must use commands directly (`/chart BTC`, `/summary BTC`) to access these features

## Expected Behavior

- Data Queries section includes a **Chart** button
- Data Queries section includes a **Summary** button
- Both buttons default to BTC when clicked
- Clicking Chart button shows chart for BTC (e.g., `/chart BTC`)
- Clicking Summary button shows summary for BTC (e.g., `/summary BTC`)

## Location

- `telegram_bot.py`:
  - Menu/keyboard creation functions (Data Queries section)
  - Button callback handlers for Chart and Summary

## Priority

Medium - User Experience

## Labels

enhancement, telegram-bot, menu, data-queries
