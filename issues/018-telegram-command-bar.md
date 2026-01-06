# Enhancement: Show command bar in Telegram using "/" button

## Description
Currently, users need to remember or type commands manually. Telegram bots can register commands that appear in the command bar when users press "/" in the chat input box. This would make the bot more user-friendly by showing all available commands.

## Current Behavior
- Users must remember command names
- No visual list of available commands in the chat input
- Commands are only discoverable through /help or documentation

## Expected Behavior
When users press "/" in the Telegram chat input box, they should see a list of available commands like:
- /start
- /help
- /run
- /stop
- /restart
- /status
- /price
- /marketcap
- /coins
- /latest
- /info

## Impact
- **High** user experience improvement
- Makes bot more discoverable
- Reduces need to remember command names
- Standard Telegram bot feature

## Suggested Implementation
Use Telegram Bot API's `set_my_commands` or `set_commands` method to register bot commands:

```python
from telegram import BotCommand

# In main_async() after creating application
commands = [
    BotCommand("start", "Start the bot and show main menu"),
    BotCommand("help", "Show help and available commands"),
    BotCommand("run", "Start the dashboard server"),
    BotCommand("stop", "Stop the dashboard server"),
    BotCommand("restart", "Restart the dashboard server"),
    BotCommand("status", "Check if dashboard is running"),
    BotCommand("price", "Get latest price for a coin (e.g., /price BTC)"),
    BotCommand("marketcap", "Get market cap for a coin (e.g., /marketcap ETH)"),
    BotCommand("coins", "List all available coins"),
    BotCommand("latest", "Get latest prices for all coins"),
    BotCommand("info", "Get detailed information for a coin (e.g., /info BTC)"),
]

await application.bot.set_my_commands(commands)
```

## Priority
High - User Experience

## Related
- Telegram Bot API: https://core.telegram.org/bots/api#setmycommands
- BotCommand documentation: https://python-telegram-bot.readthedocs.io/en/stable/telegram.botcommand.html

