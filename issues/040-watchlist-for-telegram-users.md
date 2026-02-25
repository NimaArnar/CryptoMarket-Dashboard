# Feature: Create watchlist for Telegram users

## Description

Allow each Telegram user to maintain a **personal watchlist** of coins. Users can add/remove coins from their watchlist and quickly view prices or data for their watched coins (e.g. a single command or menu that shows all watchlist coins).

## Current Behavior

- No persistent watchlist; users must type symbols or use the full coins list each time.

## Expected Behavior

- **Add/remove coins**: Commands or buttons to add a coin to watchlist (e.g. "Add to watchlist" from price/info or a dedicated "Watchlist" menu where user picks coins) and remove from watchlist.
- **View watchlist**: A command or menu (e.g. `/watchlist` or "My Watchlist" in Data Queries) that shows the user's watchlist (e.g. list of symbols with latest price or a compact summary).
- **Persistence**: Watchlist stored per user (e.g. by `user_id`). Options: in-memory (lost on bot restart), or persisted (e.g. JSON file, SQLite, or context/bot persistence if available).

## Implementation Notes

- Use `context.user_data` for in-memory per-user storage, or a simple file/DB (e.g. `watchlists.json` keyed by `user_id`) for persistence.
- Watchlist should only contain symbols that exist in the bot (from COINS / dashboard). Validate on add.
- Consider max size (e.g. 10–20 coins per user) to avoid abuse and long messages.

## Location

- `telegram_bot.py`: New handlers for watchlist (e.g. `watchlist_command`, callback for "Add to watchlist" / "Remove from watchlist", keyboard for choosing coins). Optional: small module or dict for persistence.

## Priority

Medium - User Experience / Feature

## Labels

feature, telegram-bot, watchlist, user-data, ux
