# How to Check Bot Logs

The Telegram bot logs are stored in the `logs/` directory and are also displayed in the console when the bot is running.

## Method 1: View Logs in Real-Time (Console)

When the bot is running, logs are automatically printed to the console/terminal:

```bash
python telegram_bot.py
```

You'll see logs like:
```
2026-01-01 12:00:00 - telegram_bot - INFO - Starting Telegram bot...
2026-01-01 12:00:01 - telegram_bot - INFO - Bot started successfully
```

## Method 2: View Log Files

Log files are stored in the `logs/` directory with the format: `dashboard_YYYYMMDD.log`

### Windows PowerShell:
```powershell
# View today's log file
Get-Content logs\dashboard_20260101.log -Tail 50

# View last 100 lines
Get-Content logs\dashboard_20260101.log -Tail 100

# Follow logs in real-time (like tail -f)
Get-Content logs\dashboard_20260101.log -Wait -Tail 20
```

### Windows CMD:
```cmd
# View last 50 lines
powershell -Command "Get-Content logs\dashboard_20260101.log -Tail 50"
```

### Linux/Mac:
```bash
# View last 50 lines
tail -n 50 logs/dashboard_20260101.log

# Follow logs in real-time
tail -f logs/dashboard_20260101.log

# View entire log file
cat logs/dashboard_20260101.log
```

## Method 3: Find Today's Log File

The log file name includes today's date. For example:
- January 1, 2026 → `dashboard_20260101.log`
- January 2, 2026 → `dashboard_20260102.log`

### Quick Command (PowerShell):
```powershell
# Get today's log file automatically
$today = Get-Date -Format "yyyyMMdd"
Get-Content "logs\dashboard_$today.log" -Tail 50
```

### Quick Command (Linux/Mac):
```bash
# Get today's log file automatically
tail -n 50 logs/dashboard_$(date +%Y%m%d).log
```

## Method 4: Search for Errors

### Windows PowerShell:
```powershell
# Search for errors in today's log
$today = Get-Date -Format "yyyyMMdd"
Select-String -Path "logs\dashboard_$today.log" -Pattern "ERROR|error|Error" -Context 2,2
```

### Linux/Mac:
```bash
# Search for errors
grep -i error logs/dashboard_$(date +%Y%m%d).log
```

## Method 5: View All Recent Log Files

### Windows PowerShell:
```powershell
# List all log files, sorted by date
Get-ChildItem logs\dashboard_*.log | Sort-Object LastWriteTime -Descending
```

### Linux/Mac:
```bash
# List all log files, sorted by date
ls -lt logs/dashboard_*.log
```

## Log File Location

- **Directory**: `logs/`
- **Format**: `dashboard_YYYYMMDD.log`
- **Example**: `logs/dashboard_20260101.log`

## What Gets Logged

The bot logs:
- ✅ Bot startup and shutdown
- ✅ Command executions (`/start`, `/run`, `/stop`, etc.)
- ✅ Button callback events
- ❌ Errors and exceptions
- ⚠️ Warnings (duplicate commands, etc.)
- 🔍 Debug information (if enabled)

## Common Log Messages

- `Starting Telegram bot...` - Bot is starting
- `Error starting dashboard: ...` - Dashboard failed to start
- `button_callback called without callback_query` - Button callback issue
- `TELEGRAM_BOT_TOKEN environment variable is not set!` - Missing token

## Tips

1. **Real-time monitoring**: Use `Get-Content -Wait` (PowerShell) or `tail -f` (Linux/Mac) to watch logs as they're written
2. **Filter by level**: Search for "ERROR", "WARNING", or "INFO" to filter log levels
3. **Check recent logs**: Always check today's log file first
4. **Multiple files**: Each day gets a new log file, so check the most recent one

