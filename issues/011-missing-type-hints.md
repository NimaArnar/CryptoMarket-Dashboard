# Code Quality: Missing type hints

## Description
Several functions lack return type annotations, reducing code clarity and IDE support.

## Locations
Multiple functions throughout the codebase:
- `_get_local_ip()` - returns `str` or `None`
- `_check_dashboard_running()` - returns `bool`
- Various helper functions

## Impact
- Low severity
- Code maintainability
- Reduced IDE support

## Suggested Fix
Add type hints:
```python
def _get_local_ip() -> Optional[str]:
    """Get the local IP address for network access."""
    ...

def _check_dashboard_running() -> bool:
    """Check if dashboard is running."""
    ...
```

## Priority
Low


