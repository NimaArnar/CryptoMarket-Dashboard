# Performance: Synchronous data loading blocks event loop

## Description
`_load_data_manager()` is called from async context but uses synchronous operations, blocking the event loop.

## Location
`telegram_bot.py`, multiple command handlers using `_load_data_manager()`

## Current Code
```python
loop = asyncio.get_event_loop()
dm = await loop.run_in_executor(None, _load_data_manager)
```

## Impact
- Medium severity
- Bot becomes unresponsive during data loading
- Poor user experience

## Suggested Fix
1. Make data loading truly async
2. Add progress updates during loading
3. Cache data manager instance more effectively

## Priority
Medium


