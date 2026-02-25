# Enhancement: Add "Back to Data Queries" button when viewing List All Coins

## Description

When the user selects "List All Coins" from the Data Queries section, the coins list is shown but there is no button to go back to the Data Queries menu. The user can only go "Back to Main Menu", which loses the Data Queries context.

## Current Behavior

- User taps "💰 Data Queries" → sees Data Queries menu with buttons (List All Coins, Latest Prices, Price (BTC), etc.).
- User taps "📋 List All Coins" → sees paginated list of coins.
- The coins view has a "Back to Main Menu" button but no "Back to Data Queries" (or similar) button.
- To return to Data Queries, the user must go to Main Menu and open Data Queries again.

## Expected Behavior

- When viewing the List All Coins screen (from Data Queries), include a button such as:
  - **"🔙 Back to Data Queries"** (callback e.g. `menu_data`), so the user can return to the Data Queries menu in one tap.
- Optionally keep "Back to Main Menu" as well, or replace it with "Back to Data Queries" when the flow originated from Data Queries.

## Location

- `telegram_bot.py`:
  - `coins_command_edit()` or the keyboard used when displaying the coins list (pagination).
  - Ensure the inline keyboard for the coins list includes a "Back to Data Queries" button that sends the user back to the Data Queries menu (same content as when tapping "💰 Data Queries").

## Priority

Medium - User Experience / Navigation

## Labels

enhancement, telegram-bot, menu, data-queries, navigation
