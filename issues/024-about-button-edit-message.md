# Bug: About button should edit message, not send new

## Description
When clicking "What's this bot for?" button, it should edit the existing message instead of sending a new one.

## Current Behavior
- Clicking "What's this bot for?" sends a new message
- Creates multiple messages in the chat

## Expected Behavior
- Clicking "What's this bot for?" should edit the existing message
- No new messages should be sent

## Location
`telegram_bot.py`, `about_command_edit()` function

## Priority
Medium - User Experience

## Status
✅ Fixed

