# Bug: Telegram message length limit exceeded

## Description
The `/latest` command can exceed Telegram's 4096 character limit when listing many coins, causing the message to fail.

## Location
`telegram_bot.py`, `latest_command` function, lines 1373-1449

## Impact
- Medium severity
- Command fails silently for large coin lists
- Poor user experience

## Suggested Fix
1. Split message into multiple parts if too long
2. Add pagination (e.g., `/latest 1`, `/latest 2`)
3. Limit to top N coins by default

## Priority
Medium


