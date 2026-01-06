# Enhancement: Add bot bio information and "What's this bot for?" button

## Description
Add a bio/description for the bot that users can see, and add a button to explain what the bot does.

## Current Behavior
- Bot has no bio/description visible to users
- No easy way for new users to understand what the bot does
- Users must explore commands to understand bot functionality

## Expected Behavior

### 1. Bot Bio Information
Set bot description that appears in:
- Bot profile page
- Bot info section
- When users first interact with the bot

### 2. "What's this bot for?" Button
Add a button in the main menu that shows:
- Bot purpose and description
- Key features
- How to get started
- Links to dashboard (if running)

## Implementation Details

### Bot Bio/Description
Use `set_my_description()` and `set_my_short_description()` API methods:

```python
# In main_async() after creating application
await application.bot.set_my_description(
    "🤖 Control your Crypto Market Dashboard remotely via Telegram. "
    "Start/stop dashboard, get real-time prices, market caps, and detailed coin information. "
    "Access your dashboard from anywhere on your network."
)

await application.bot.set_my_short_description(
    "Control Crypto Market Dashboard & get crypto data"
)
```

### "What's this bot for?" Button
1. Add button to main keyboard: `InlineKeyboardButton("ℹ️ What's this bot for?", callback_data="about")`
2. Create `about_command()` handler that shows:
   ```
   🤖 Crypto Market Dashboard Bot
   
   This bot allows you to:
   • Control your dashboard server remotely
   • Get real-time cryptocurrency prices
   • View market cap data
   • Access detailed coin information
   • Monitor dashboard status
   
   📊 Dashboard Control:
   Start, stop, restart, and check status of your dashboard server.
   
   💰 Data Queries:
   Get prices, market caps, and information for 25+ cryptocurrencies.
   
   🌐 Network Access:
   Access your dashboard from any device on your network.
   
   💡 Getting Started:
   Use /start to see the main menu, or /help for command list.
   ```

## Location
- `telegram_bot.py`, `main_async()` function - for bot description
- `telegram_bot.py`, `create_main_keyboard()` - for about button
- `telegram_bot.py`, `button_callback()` - for about handler

## Priority
Medium - User Experience

## Related
- Telegram Bot API: https://core.telegram.org/bots/api#setmydescription
- Telegram Bot API: https://core.telegram.org/bots/api#setmyshortdescription

