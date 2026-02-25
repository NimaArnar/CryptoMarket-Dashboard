# Enhancement: Delete the Data Queries menu message after button click for cleaner conversation

## Description

When the user taps a button in the Data Queries section (e.g. Price, Info, Summary, Chart, List All Coins, Latest Prices, Correlation), the bot sends the response (section description + data, or another screen) and then **resends** the Data Queries menu as the latest message (per issue #38). However, the **original message** that contained the buttons the user clicked on is **not deleted**. So the chat shows: (1) the old Data Queries message with buttons, (2) the response(s), (3) the new Data Queries message. The old message should be **deleted** so only the new Data Queries menu remains at the bottom, keeping the conversation cleaner.

## Current Behavior

- User sees "💰 Data Queries" message with buttons.
- User taps e.g. "Price" → bot sends section description + price data, then sends a new "💰 Data Queries" message (resend).
- The **first** "💰 Data Queries" message (the one they clicked on) is still in the chat above the new messages.
- Result: two Data Queries menu messages in the thread.

## Expected Behavior

- When the user taps any Data Queries button, **delete the message** that contained that button (the message the callback query came from) before or after sending the response and resending the Data Queries menu.
- After the flow: only one "💰 Data Queries" message at the bottom (the newly sent one); the previous one is removed.
- Cleaner conversation with no duplicate menu messages.

## Implementation Notes

- In `button_callback()`, for Data Queries actions (e.g. `cmd_coins`, `cmd_latest`, `price_*`, `info_*`, `summary_*`, `chartbtn_*`, `menu_corr`, `corr_default`, `corr_coin_*`), call `await query.message.delete()` (or equivalent) to remove the message that contained the clicked button.
- Do this either at the start of handling (so the menu message is removed before sending the response) or after sending the resend menu. At the start is usually better so the user sees the old message disappear and then the new content + new menu.
- Handle delete failures gracefully (e.g. message already deleted, or bot without permission); log and continue.

## Location

- `telegram_bot.py`: `button_callback()` — add `query.message.delete()` for the relevant Data Queries callback branches (where we currently resend the Data Queries menu via `_send_data_menu`).

## Priority

Low - User Experience / Cleanup

## Labels

enhancement, telegram-bot, menu, data-queries, ux
