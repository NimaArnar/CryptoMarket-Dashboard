# Bug: Fix "What's this bot for?" button behavior

## Description
The "What's this bot for?" button currently sends a new message instead of editing the existing one. Also, it should be moved from the main menu to the help menu.

## Current Behavior
1. Button is in the main menu
2. When clicked, it sends a new message instead of editing the existing one
3. Creates multiple messages in the chat

## Expected Behavior
1. Button should be in the help menu (not main menu)
2. When clicked, it should edit the existing message (not send new one)
3. Should work consistently with other menu navigation buttons

## Location
- `telegram_bot.py`, `create_main_keyboard()` - Remove button from here
- `telegram_bot.py`, `create_help_keyboard()` - Add button here
- `telegram_bot.py`, `button_callback()` - Fix to edit message instead of sending new

## Priority
Medium - User Experience

## Related
- Similar to fix for help button (issue #18)
- Should use `query.edit_message_text()` instead of `context.bot.send_message()`

