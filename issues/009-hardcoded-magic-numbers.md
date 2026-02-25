# Code Quality: Hardcoded magic numbers

## Description
Several magic numbers are hardcoded throughout the code instead of being defined as constants.

## Locations
- `telegram_bot.py`, line 509: `max_wait = 480`
- `telegram_bot.py`, line 510: `wait_interval = 2`
- `telegram_bot.py`, line 916: `if len(_processed_updates) > 100:`
- `telegram_bot.py`, line 917: `_processed_updates = set(list(_processed_updates)[-50:])`

## Impact
- Low severity
- Code maintainability
- Hard to adjust values

## Suggested Fix
Move to constants in `src/config.py`:
```python
# Telegram Bot Configuration
BOT_MAX_DASHBOARD_WAIT = 480  # seconds
BOT_WAIT_INTERVAL = 2  # seconds
BOT_PROCESSED_UPDATES_MAX = 100
BOT_PROCESSED_UPDATES_CLEANUP = 50
```

## Priority
Low


