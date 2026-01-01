# How to Ensure Only One Bot Instance is Running

The bot now automatically prevents multiple instances from running on the same machine using a lock file mechanism.

## Automatic Protection

When you start the bot, it will:

1. **Check for existing lock file** - If found, it checks if the process is still running
2. **Verify the process** - Uses the PID in the lock file to check if it's actually a bot instance
3. **Create lock file** - If no other instance is running, creates a lock file with the current PID
4. **Remove lock on exit** - Automatically removes the lock file when the bot stops

## What Happens if Another Instance is Running?

If you try to start the bot when another instance is already running, you'll see:

```
ERROR - Another bot instance is already running (PID: 12345)
ERROR - Command: python telegram_bot.py
ERROR - Cannot start bot: Another instance is already running!
ERROR - To start anyway, stop the other instance first or delete the lock file:
ERROR -   Remove: C:\Users\Nima\Desktop\CryptoMarket-Dashboard\.telegram_bot.lock
```

## Manual Methods to Ensure Single Instance

### Method 1: Check Running Processes (PowerShell)

```powershell
# Check if bot is running
Get-Process python | Where-Object {
    $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
    $cmdline -like "*telegram_bot*"
} | Select-Object Id, ProcessName, @{Name='CommandLine';Expression={(Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine}}
```

### Method 2: Stop All Bot Processes

```powershell
# Stop all bot processes
Get-Process python | Where-Object {
    $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
    $cmdline -like "*telegram_bot*"
} | Stop-Process -Force
```

### Method 3: Remove Lock File (if stale)

If the bot crashed and left a stale lock file:

```powershell
# Remove the lock file
Remove-Item .telegram_bot.lock -ErrorAction SilentlyContinue
```

### Method 4: Check Task Manager

1. Open Task Manager (Ctrl+Shift+Esc)
2. Go to "Details" tab
3. Look for `python.exe` processes
4. Check the "Command line" column for `telegram_bot.py`
5. End any duplicate processes

## Lock File Location

The lock file is created at:
- **Path**: `.telegram_bot.lock` (in the project root)
- **Full path**: `C:\Users\Nima\Desktop\CryptoMarket-Dashboard\.telegram_bot.lock`
- **Contents**: The PID (Process ID) of the running bot instance

## Troubleshooting

### Stale Lock File

If the bot crashed and left a lock file, the next start will:
- Detect the stale lock (process no longer exists)
- Automatically remove it
- Start normally

### Permission Issues

If you can't create/remove the lock file:
- Check file permissions
- Make sure you have write access to the project directory
- Try running as administrator if needed

### Multiple Machines

**Important**: The lock file only prevents multiple instances on the **same machine**. 

If you run the bot on multiple machines with the same token:
- Each machine can run one instance
- You'll still get "Conflict" errors from Telegram
- Only one instance will receive updates at a time

To avoid conflicts:
- Run the bot on only **one machine** at a time
- Or use webhooks instead of polling (for server deployments)

## Best Practices

1. **Always stop the bot properly** - Use Ctrl+C to stop, don't just close the terminal
2. **Check before starting** - If unsure, check for running processes first
3. **One machine only** - Don't run the bot on multiple machines simultaneously
4. **Clean shutdown** - The lock file is automatically removed on proper shutdown

