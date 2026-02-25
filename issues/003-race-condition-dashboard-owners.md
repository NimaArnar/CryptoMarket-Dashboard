# Bug: Race condition in dashboard_owners dictionary

## Description
Multiple users could potentially start dashboards simultaneously before the ownership check completes, leading to conflicts.

## Location
`telegram_bot.py`, `run_command` function, lines 428-461

## Current Code
```python
# Check if this user already has a dashboard running
if user_id in dashboard_owners:
    # ... check logic
    return

# Check if any dashboard is running (port check)
if _check_dashboard_running():
    # ... conflict handling
    return

# Start dashboard (no locking mechanism)
dashboard_process = subprocess.Popen(...)
dashboard_owners[user_id] = {...}
```

## Impact
- Medium severity
- Could allow multiple dashboards to start
- Port conflicts possible

## Suggested Fix
Add a lock mechanism using `asyncio.Lock()`:
```python
dashboard_lock = asyncio.Lock()

async def run_command(...):
    async with dashboard_lock:
        # Check and start dashboard atomically
```

## Priority
Medium


