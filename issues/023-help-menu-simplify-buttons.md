# Bug: Help menu should only show 2 buttons

## Description
The help menu currently shows too many buttons. It should only show "What's this bot for?" and "Back to Main Menu" buttons.

## Current Behavior
Help menu shows:
- Dashboard Control
- Data Queries
- Quick Actions
- What's this bot for?
- Back to Main Menu

## Expected Behavior
Help menu should only show:
- What's this bot for?
- Back to Main Menu

## Location
`telegram_bot.py`, `create_help_keyboard()` function

## Priority
Medium - User Experience

## Status
✅ Fixed

