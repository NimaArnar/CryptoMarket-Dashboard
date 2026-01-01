# Quick Start Guide - Telegram Bot

## Start the Bot

### Option 1: Using PowerShell Script (Recommended)
```powershell
.\start_bot.ps1
```

### Option 2: Manual Start
```powershell
$env:TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
python telegram_bot.py
```

## Verify Bot is Running

After starting, you should see:
```
INFO - Starting Telegram bot...
INFO - Bot is running. Press Ctrl+C to stop.
```

## Test in Telegram

1. Open Telegram
2. Find your bot: `@CryptoMarketDashboard_bot`
3. Send `/start`
4. You should see buttons appear

## Stop the Bot

Press `Ctrl+C` in the terminal where the bot is running.

## Troubleshooting

### Bot Not Responding?

1. **Check if bot is running:**
   ```powershell
   Get-Process python | Where-Object {
       $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
       $cmdline -like "*telegram_bot*"
   }
   ```

2. **If not running, start it:**
   ```powershell
   .\start_bot.ps1
   ```

3. **Check logs:**
   ```powershell
   Get-Content logs\dashboard_$(Get-Date -Format 'yyyyMMdd').log -Tail 20
   ```

### "Another instance is running" Error?

1. **Stop all bot processes:**
   ```powershell
   Get-Process python | Where-Object {
       $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
       $cmdline -like "*telegram_bot*"
   } | Stop-Process -Force
   ```

2. **Remove lock file (if needed):**
   ```powershell
   Remove-Item .telegram_bot.lock -ErrorAction SilentlyContinue
   ```

3. **Start again:**
   ```powershell
   .\start_bot.ps1
   ```

## Important Notes

- **The bot must be running** to respond to Telegram commands
- Commands like `/start`, `/stop`, `/run` only work when the bot process is active
- Keep the terminal window open while the bot is running
- Use `Ctrl+C` to stop the bot gracefully

