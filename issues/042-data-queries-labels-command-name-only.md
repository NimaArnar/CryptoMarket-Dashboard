# Enhancement: In Data Queries show only command name (no "BTC"); use BTC as default when selected

## Description

In the Data Queries menu, the single-coin action buttons currently show the coin in the label (e.g. "💵 Price (BTC)", "📊 Info (BTC)", "📊 Summary (BTC)", "📈 Chart (BTC)"). Change the labels to show only the command name (e.g. "💵 Price", "📊 Info", "📊 Summary", "📈 Chart"). When the user taps such a button, the bot should still use **BTC as the default** coin (unchanged behavior).

## Current Behavior

- Data Queries menu shows: "Price (BTC)", "Info (BTC)", "Summary (BTC)", "Chart (BTC)".
- Tapping any of these runs the action for BTC.

## Expected Behavior

- Data Queries menu shows: "Price", "Info", "Summary", "Chart" (no "(BTC)" in the label).
- Tapping any of these still runs the action for BTC (default). No change in behavior, only in button text.

## Rationale

- Cleaner, shorter labels.
- Avoids implying that only BTC is available; the default is BTC, and users can use commands for other coins.

## Location

- `telegram_bot.py`: `create_data_keyboard()` — change button text for the four single-coin actions. Keep `callback_data` as `price_BTC`, `info_BTC`, `summary_BTC`, `chartbtn_BTC` so behavior stays the same.

## Priority

Low - UI / UX

## Labels

enhancement, telegram-bot, menu, data-queries, ux
