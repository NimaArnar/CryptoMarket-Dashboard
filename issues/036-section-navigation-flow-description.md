# Enhancement: Add section navigation flow - show description before data

## Description

When a user clicks a single-coin button (e.g., "Price BTC" or "Info BTC"), the bot should first navigate to the relevant section, show a description of how that section works, and then send the actual data.

## Current Behavior

- Clicking a button (e.g., Price BTC) immediately sends the data
- No section context or description is shown
- User may not understand what the section does

## Expected Behavior

When user clicks a single-coin button (e.g., "Price BTC"):

1. **Navigate to section**: Menu switches to the relevant section (e.g., Price section)
2. **Show description**: Display a brief description explaining:
   - What the section/command does
   - What data is shown
   - How to use it
3. **Send data**: After showing the description, send the actual data for the coin (e.g., BTC price data)

**Example flow:**
```
User clicks "Price BTC" button
→ Bot shows: "📊 Price Section - Get instant price data for any coin..."
→ Bot shows: "💡 Use /price <SYMBOL> to get live prices from CoinGecko API"
→ Bot then sends: BTC price data
```

## Location

- `telegram_bot.py`:
  - Button callback handlers for Price, Info, Chart, Summary
  - Menu navigation logic
  - Section description text/messages

## Priority

Medium - User Experience

## Labels

enhancement, telegram-bot, menu, user-flow
