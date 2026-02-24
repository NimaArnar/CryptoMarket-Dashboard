# Enhancement: Remove ETH-specific Price and Info buttons from menus

## Description

Remove any Price and Info buttons that are specifically tied to ETH from the menus. These should be replaced with generic single-coin buttons that default to BTC (see issue #034).

## Current Behavior

- There may be separate Price button for ETH
- There may be separate Info button for ETH
- These buttons are coin-specific rather than generic

## Expected Behavior

- No separate Price button for ETH
- No separate Info button for ETH
- Only generic Price and Info buttons that default to BTC (handled by issue #034)

## Location

- `telegram_bot.py`:
  - Menu/keyboard creation functions
  - Quick Actions section (if exists)
  - Any ETH-specific button definitions

## Priority

Medium - User Experience

## Labels

enhancement, telegram-bot, menu, cleanup
