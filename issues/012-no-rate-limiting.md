# Enhancement: Add rate limiting for bot commands

## Description
Users can spam commands without any rate limiting, which could:
- Overwhelm the bot
- Hit API rate limits
- Cause performance issues

## Impact
- Medium severity
- Security/performance concern
- Could abuse the system

## Suggested Fix
Implement rate limiting using decorator:
```python
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta

user_command_times = defaultdict(list)

def rate_limit(max_calls=10, period=60):
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context):
            user_id = update.effective_user.id
            now = datetime.now()
            # Clean old entries
            user_command_times[user_id] = [
                t for t in user_command_times[user_id]
                if now - t < timedelta(seconds=period)
            ]
            # Check rate limit
            if len(user_command_times[user_id]) >= max_calls:
                await update.message.reply_text(
                    f"⏳ Rate limit exceeded. Please wait {period} seconds."
                )
                return
            user_command_times[user_id].append(now)
            return await func(update, context)
        return wrapper
    return decorator
```

## Priority
Medium


