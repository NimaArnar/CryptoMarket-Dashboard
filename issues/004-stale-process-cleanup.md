# Bug: Stale process cleanup in dashboard_owners

## Description
If the bot crashes or restarts, `dashboard_owners` dictionary entries become stale. Dead processes aren't automatically cleaned up on bot startup.

## Location
`telegram_bot.py`, `dashboard_owners` dictionary usage throughout

## Impact
- Medium severity
- Stale entries prevent users from starting new dashboards
- False "already running" messages

## Suggested Fix
Add cleanup logic in `main_async()` to check and remove dead processes:
```python
async def main_async():
    # Clean up stale dashboard owners on startup
    for user_id, info in list(dashboard_owners.items()):
        if info["process"] and info["process"].poll() is not None:
            del dashboard_owners[user_id]
```

## Priority
Medium


