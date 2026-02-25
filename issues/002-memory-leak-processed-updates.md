# Bug: Potential memory leak in _processed_updates set

## Description
The `_processed_updates` set in `status_command` can grow indefinitely. While there's cleanup logic when it exceeds 100 entries, this could still cause issues with high-frequency usage.

## Location
`telegram_bot.py`, lines 882-917

## Current Code
```python
_processed_updates = set()

# Clean up old entries (keep only last 100)
if len(_processed_updates) > 100:
    _processed_updates = set(list(_processed_updates)[-50:])
```

## Impact
- Medium severity
- Memory usage grows over time
- Could cause performance issues with many users

## Suggested Fix
Use a bounded data structure like `collections.deque` with `maxlen`:
```python
from collections import deque
_processed_updates = deque(maxlen=100)
```

## Priority
Medium


