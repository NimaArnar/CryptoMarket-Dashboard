# Security: Missing input validation for user commands

## Description
User-provided symbols and commands aren't sanitized before use, which could lead to injection attacks or unexpected behavior.

## Location
Multiple command handlers in `telegram_bot.py`:
- `price_command` (line 1188)
- `marketcap_command` (line 1279)
- `info_command` (line 1452)

## Current Code
```python
symbol = context.args[0].upper()  # No validation
```

## Impact
- Medium severity
- Potential security risk
- Could cause errors with malicious input

## Suggested Fix
Add validation:
```python
import re

def validate_symbol(symbol: str) -> bool:
    """Validate coin symbol format."""
    return bool(re.match(r'^[A-Z0-9]{1,10}$', symbol.upper()))

# In commands:
if not validate_symbol(symbol):
    await update.message.reply_text("❌ Invalid symbol format.")
    return
```

## Priority
Medium


