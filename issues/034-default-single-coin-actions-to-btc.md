# Enhancement: Default all single-coin actions to BTC instead of ETH

## Description

Change the default coin for all single-coin actions (Price, Info, Chart, Summary) from ETH to BTC. When users click buttons or use commands without specifying a coin, BTC should be used as the default.

## Current Behavior

- Some single-coin actions may default to ETH
- Quick action buttons may be set to ETH

## Expected Behavior

- All single-coin actions default to **BTC**
- Price button → shows BTC price
- Info button → shows BTC info
- Chart button → shows BTC chart
- Summary button → shows BTC summary
- Commands without coin specified (e.g., `/price`) → use BTC

## Location

- `telegram_bot.py`:
  - Button callback handlers for Price, Info, Chart, Summary
  - Command handlers that have default coin logic
  - Quick Actions section (if exists)

## Priority

Medium - User Experience

## Labels

enhancement, telegram-bot, menu, default-values
