# Bug: About screen should only show back button

## Description
When showing the "What's this bot for?" content, it should only show "Back to Main Menu" button, not the full help keyboard.

## Current Behavior
About screen shows full help keyboard with multiple buttons.

## Expected Behavior
About screen should only show:
- Back to Main Menu button

## Location
`telegram_bot.py`, `create_about_keyboard()` function

## Priority
Medium - User Experience

## Status
✅ Fixed

