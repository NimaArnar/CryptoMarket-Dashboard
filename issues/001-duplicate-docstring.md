# Bug: Duplicate docstring in help_command

## Description
The `help_command` function in `telegram_bot.py` has a duplicate docstring on lines 377-379.

## Location
`telegram_bot.py`, lines 377-379

## Current Code
```python
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    log_user_action(update, "command", "/help")
    """Handle /help command."""  # DUPLICATE!
```

## Impact
- Low severity
- Code quality issue
- No functional impact

## Fix
Remove the duplicate docstring on line 379.

## Priority
Low


