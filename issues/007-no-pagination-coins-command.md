# Enhancement: Add pagination to /coins command

## Description
The `/coins` command lists all coins in one message, which can be overwhelming and hard to read.

## Location
`telegram_bot.py`, `coins_command` function, lines 1343-1370

## Impact
- Low severity
- UX improvement
- Better readability

## Suggested Fix
Add pagination:
- `/coins` or `/coins 1` - shows first 20 coins
- `/coins 2` - shows next 20 coins
- Add navigation buttons (Next/Previous)

## Priority
Low


