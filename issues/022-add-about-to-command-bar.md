# Enhancement: Add "What's this bot for?" to Telegram command bar

## Description
Add a command for "What's this bot for?" to the Telegram command bar so users can access it via `/about` command.

## Current Behavior
- "What's this bot for?" is only available as a button
- No command to access bot information directly

## Expected Behavior
- Add `/about` command to command bar
- When users press "/" in Telegram, they should see `/about` command
- Command should show the same information as the button

## Implementation Details
Add to bot commands registration:
```python
BotCommand("about", "Learn what this bot does and its features")
```

Add command handler:
```python
application.add_handler(CommandHandler("about", about_command))
```

Create `about_command()` function that shows the same content as the button.

## Location
- `telegram_bot.py`, `main_async()` - Add to commands list
- `telegram_bot.py` - Create `about_command()` function

## Priority
Low - User Experience

## Related
- Issue #18: Command bar registration
- Issue #20: Bot bio and about button

