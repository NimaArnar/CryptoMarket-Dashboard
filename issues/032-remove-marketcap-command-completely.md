# Enhancement: Remove marketcap command and functions completely

## Description
The marketcap command and related functions are unessential because market cap data is already available in the `/info` command, which provides comprehensive coin details. We should remove the marketcap command, button handlers, and all related functionality to simplify the codebase.

## Current Behavior
- `/marketcap` command exists and works
- Marketcap button handlers exist in `button_callback()`
- Marketcap command handler registered in `main_async()`
- Market cap data is redundant since it's in `/info` command

## Expected Behavior
- Remove `/marketcap` command completely
- Remove marketcap button handlers from `button_callback()`
- Remove marketcap command handler registration
- Remove `marketcap_command()` function
- Users can access market cap via `/info` command only

## Location
- `telegram_bot.py`:
  - `marketcap_command()` function - Remove entire function
  - `button_callback()` function - Remove `marketcap_` handler
  - `main_async()` function - Remove command handler registration
  - Any references to marketcap in help/command lists

## Priority
Low - Code Cleanup

## Related
- Issue #19: Enhanced `/info` command shows market cap data
- Issue #28: Removed marketcap button from menu (but command still exists)

