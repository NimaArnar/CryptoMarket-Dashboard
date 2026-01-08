# Enhancement: Remove marketcap button - unessential

## Description
The marketcap button is unessential because market cap data is already available in the `/info` command, which provides comprehensive coin details. Removing it will simplify the menu and reduce redundancy.

## Current Behavior
- Marketcap button exists in Data Queries menu
- Marketcap button shows: Market Cap, Date, Category
- This information is already available in `/info` command

## Expected Behavior
- Remove marketcap button from Data Queries menu
- Users can still access market cap via `/info` command or `/marketcap` command
- Cleaner menu with less redundancy

## Location
- `telegram_bot.py`:
  - `create_data_keyboard()` function - Remove marketcap buttons
  - `button_callback()` function - Remove marketcap button handler (or keep for command compatibility)

## Priority
Low - Code Cleanup / UX Improvement

## Related
- Issue #19: Enhanced `/info` command shows market cap data
- Issue #26: Info buttons added to menus

