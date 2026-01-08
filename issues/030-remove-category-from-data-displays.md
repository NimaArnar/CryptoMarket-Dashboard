# Enhancement: Remove category from data displays - only show in /info

## Description
Category information is shown in multiple places (price, marketcap commands), but it's not essential for quick data queries. Category should only be shown in the detailed `/info` section. Removing it from other sections will make data displays cleaner and more focused.

## Current Behavior
- `/price` command shows: Price, Market Cap, Date, Category
- `/marketcap` command shows: Market Cap, Date, Category
- Category is redundant in quick data queries

## Expected Behavior
- Remove category from `/price` command output
- Remove category from `/marketcap` command output
- Keep category only in `/info` command (detailed view)
- Cleaner, more focused data displays

## Location
- `telegram_bot.py`:
  - `price_command()` function - Remove category line
  - `marketcap_command()` function - Remove category line
  - `info_command()` function - Keep category (detailed view)

## Priority
Low - Code Cleanup / UX Improvement

## Related
- Issue #27: Reduced emojis in data display
- Issue #19: Enhanced `/info` command

