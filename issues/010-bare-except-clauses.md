# Code Quality: Bare except clauses hide errors

## Description
Several functions use bare `except:` clauses which catch all exceptions including system exits, making debugging difficult.

## Locations
Multiple locations in `telegram_bot.py`:
- Line 540: `except: pass`
- Line 595: `except Exception as e:`
- Line 667: `except: pass`

## Impact
- Medium severity
- Errors are silently ignored
- Difficult to debug issues

## Suggested Fix
Catch specific exceptions:
```python
except (KeyError, ValueError) as e:
    logger.warning(f"Expected error: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

## Priority
Medium


