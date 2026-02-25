# Enhancement: Resend Data Queries menu as latest message when selecting Data Queries buttons

## Description

When the user selects any button in the Data Queries section (e.g. List All Coins, Latest Prices, Price (BTC), Info (BTC), Summary (BTC), Chart (BTC)), the bot should send the Data Queries menu message again so that it becomes the latest message in the chat. This keeps the menu visible and on top after the bot replies with data or another screen.

## Current Behavior

- User opens Data Queries → sees "💰 Data Queries" message with buttons.
- User taps e.g. "💵 Price (BTC)" → bot sends section description, then price data. The Data Queries menu message is now above the new messages and no longer the latest.
- Same for other buttons: the menu scrolls up and is not re-presented as the current/latest message.

## Expected Behavior

- When the user triggers any action from the Data Queries menu (List All Coins, Latest Prices, Price, Info, Summary, Chart), after sending the response (or after the section description + data), the bot should **resend the Data Queries menu** (same text and keyboard as "💰 Data Queries") so that:
  - The Data Queries menu is again the **latest message** in the chat.
  - The user can immediately tap another Data Queries option without scrolling up or going back to Main Menu first.

Implementation options (pick one or combine):

- After sending the result of the button action, send a new message with the Data Queries header and `create_data_keyboard()`.
- Or edit a designated "current menu" message to the Data Queries menu after each action.

Goal: the message showing the Data Queries menu (and its buttons) should be the most recent message after using any Data Queries button.

## Location

- `telegram_bot.py`:
  - `button_callback()`: for `menu_data`, `cmd_coins`, `cmd_latest`, `price_*`, `info_*`, `summary_*`, `chartbtn_*`.
  - After handling each of these from the Data Queries flow, send (or update to) the Data Queries menu message so it is the latest.

## Priority

Medium - User Experience

## Labels

enhancement, telegram-bot, menu, data-queries, ux
