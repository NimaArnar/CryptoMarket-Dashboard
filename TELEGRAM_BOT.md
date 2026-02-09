# Telegram Bot - Complete Guide

A comprehensive Telegram bot for controlling your Crypto Market Dashboard remotely and querying real-time cryptocurrency data.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Setup](#setup)
- [Commands](#commands)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)

## Features

### Dashboard Control
- **Start/Stop Dashboard**: Control your dashboard server remotely
- **Per-User Ownership**: Each user can start their own dashboard instance (only one can run at a time)
- **Status Check**: Monitor dashboard status with ownership information
- **Network Access**: Dashboard accessible from other devices on your network
- **Real-Time Progress**: Live progress updates during dashboard startup
- **Automatic Cleanup**: Stale processes automatically detected and cleaned up

### Data Queries
- **Price Lookup**: Get latest price for any supported coin
- **Market Cap**: Query market capitalization data
- **Coin List**: View all available cryptocurrencies
- **Latest Prices**: Get top coins by market cap
- **Detailed Info**: Comprehensive coin information

### Interactive Interface
- **Inline Keyboards**: Navigate commands with interactive buttons
- **Quick Actions**: Fast access to popular coins (BTC, ETH, etc.)
- **Menu Navigation**: Organized command menus
- **Smart Message Management**: Button messages automatically cleaned up to avoid chat clutter

### User Management
- **Action Tracking**: All user interactions logged to `logs/bot_users_YYYYMMDD.log`
- **Ownership Tracking**: Dashboard ownership tracked per user
- **Multi-User Support**: Multiple users can interact with the bot simultaneously
- **User Identification**: Correct user identification from buttons and commands

## Prerequisites

1. **Python 3.8+** installed
2. **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
3. **Dependencies** installed (`pip install -r requirements.txt`)

## Quick Start

### 1. Get Your Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow instructions
3. Copy the token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Set Environment Variable

**Windows PowerShell:**
```powershell
$env:TELEGRAM_BOT_TOKEN="your-token-here"
```

**Windows CMD:**
```cmd
set TELEGRAM_BOT_TOKEN=your-token-here
```

**Linux/Mac:**
```bash
export TELEGRAM_BOT_TOKEN="your-token-here"
```

### 3. Start the Bot

**Option A: Using Scripts (Recommended)**
```powershell
# Windows PowerShell
.\start_bot.ps1

# Windows CMD
start_bot.bat

# Linux/Mac (create start_bot.sh)
./start_bot.sh
```

**Option B: Manual Start**
```bash
python telegram_bot.py
```

### 4. Test in Telegram

1. Find your bot in Telegram
2. Send `/start`
3. You should see interactive buttons appear

## Setup

### Using Start Scripts

Copy the example files and add your token:

```powershell
# Copy example file
Copy-Item start_bot.ps1.example start_bot.ps1

# Edit start_bot.ps1 and replace YOUR_BOT_TOKEN_HERE with your actual token
```

**Note**: The actual `start_bot.ps1` and `start_bot.bat` files are in `.gitignore` and won't be committed.

### Setting Bot Description (Optional)

Use the provided script:

```bash
# Set environment variable first
$env:TELEGRAM_BOT_TOKEN="your-token"

# Run the script
python scripts/set_bot_description.py
```

Or manually via BotFather:
1. Open [@BotFather](https://t.me/botfather)
2. Send `/mybots`
3. Select your bot → "Bot Settings" → "Edit Description"
4. Paste your description

### Setting Bot Profile Picture (Optional)

1. Generate or prepare a square image (640x640+ pixels, PNG or JPG)
2. Open [@BotFather](https://t.me/botfather)
3. Send `/mybots` → Select your bot
4. Choose "Bot Settings" → "Edit Botpic"
5. Upload your image

## Commands

### Dashboard Control

| Command | Description | Example |
|---------|-------------|---------|
| `/run` | Start the dashboard server | `/run` |
| `/stop` | Stop the dashboard server | `/stop` |
| `/status` | Check dashboard status | `/status` |

### Data Queries

| Command | Description | Example |
|---------|-------------|---------|
| `/price <SYMBOL>` | **Instant live price** from CoinGecko (no dashboard needed) | `/price BTC` |
| `/coins` | List all available coins | `/coins` |
| `/latest` | **Live prices for all coins** | `/latest` |
| `/info <SYMBOL>` | Detailed coin info using dashboard history | `/info DOGE` |
| `/summary <SYMBOL> [1d\|1w\|1m\|1y]` | 1d/1w/1m/1y price & market cap summary | `/summary BTC`, `/summary ETH 1m` |

### Navigation

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and main menu |
| `/help` | Display help information |

## Usage Examples

### Starting the Dashboard

```
User: /run
Bot: 🔄 Starting dashboard...
     ⏳ Waiting for dashboard to load data...
     ✅ Dashboard started successfully!
     🌐 Local: http://127.0.0.1:8052/
     🌐 Network: http://192.168.1.100:8052/
```

### Querying Instant Prices

```
User: /price BTC
Bot: 💰 BTC Price
     Price: $43,250.00
     Market Cap: $850.23B
     24h Volume: $35.10B
     📈 24h Change: +2.45%
     
     Last updated: 2026-01-01 12:34:56 UTC
```

### Timeframe Summary (1d, 1w, 1m, 1y)

```
User: /summary BTC
Bot: 📊 BTC Summary

     Latest Price/Market Cap as of 2026-02-09:
     Price: $70,000.00
     Market Cap: $1.39T

     ⏱ 1 Month
     📉 Price: -23.62%  ($-21,378.17, 2026-01-10 → 2026-02-09)
        $91,378.17 → $70,000.00
     📉 Market Cap: -23.37%  ($-422,433,874,365, 2026-01-10 → 2026-02-09)
        $1.81T → $1.39T

     ⏱ 1 Year
     📈 Price: +89.67%  ($+32,000.00, 2025-02-09 → 2026-02-09)
        $38,000.00 → $70,000.00
        Low (1y): $28,500.00  |  High (1y): $48,900.00
     📈 Market Cap: +92.10%  ($+667,000,000,000, 2025-02-09 → 2026-02-09)
        $0.72T → $1.39T

     Last updated: 2026-02-09 12:34:56
```

### Checking Status

**When you own the dashboard:**
```
User: /status
Bot: ✅ Dashboard Status: RUNNING
     🌐 Local: http://127.0.0.1:8052/
     🌐 Network: http://192.168.1.100:8052/
     📊 Process ID: 12345
     ✅ Started by you
     🕐 Started at: 2026-01-01 22:49:19
```

**When another user owns the dashboard:**
```
User: /status
Bot: ✅ Dashboard Status: RUNNING
     🌐 Local: http://127.0.0.1:8052/
     🌐 Network: http://192.168.1.100:8052/
     👤 Started by: @username
     🕐 Started at: 2026-01-01 22:49:19
     ⚠️ You don't own this dashboard
     💡 Only the owner can stop it with /stop
     📊 Process ID: 12345
```

## Troubleshooting

### Bot Not Responding

**Check if bot is running:**
```powershell
# Windows PowerShell
Get-Process python | Where-Object {
    $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
    $cmdline -like "*telegram_bot*"
}
```

**Start the bot if not running:**
```powershell
.\start_bot.ps1
```

### "Another instance is running" Error

The bot uses a lock file to prevent multiple instances. If you see this error:

1. **Stop all bot processes:**
```powershell
Get-Process python | Where-Object {
    $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
    $cmdline -like "*telegram_bot*"
} | Stop-Process -Force
```

2. **Remove lock file (if stale):**
```powershell
Remove-Item .telegram_bot.lock -ErrorAction SilentlyContinue
```

3. **Start again:**
```powershell
.\start_bot.ps1
```

### Dashboard Offline Error

If you get "Dashboard is offline" when querying data:

1. **Check dashboard status:**
```
/status
```

2. **Start the dashboard:**
```
/run
```

3. **Wait for data to load** (can take 6-7 minutes on first run)

### Token Not Set

**Error:** `TELEGRAM_BOT_TOKEN environment variable is not set!`

**Solution:** Set the environment variable before starting:
```powershell
$env:TELEGRAM_BOT_TOKEN="your-token"
python telegram_bot.py
```

### Conflict Errors

**Error:** `Conflict: terminated by other getUpdates request`

**Cause:** Multiple bot instances running (same token on different machines/processes)

**Solution:**
- Ensure only ONE instance is running
- Check all machines/devices using the same token
- Use the lock file mechanism (automatic)
- The bot automatically prevents multiple instances with lock file protection

### Network Timeout Errors

**Error:** `Timed out` or `ConnectTimeout` during bot startup

**Cause:** Network connectivity issues or Telegram API temporarily unavailable

**Solution:**
- Check your internet connection
- Verify firewall/proxy settings aren't blocking Telegram API
- The bot automatically retries with exponential backoff (up to 3 attempts)
- Wait a few seconds and try again

### Checking Logs

**View today's log:**
```powershell
# Windows PowerShell
$today = Get-Date -Format "yyyyMMdd"
Get-Content "logs\dashboard_$today.log" -Tail 50
```

**Follow logs in real-time:**
```powershell
Get-Content "logs\dashboard_$today.log" -Wait -Tail 20
```

**Search for errors:**
```powershell
Select-String -Path "logs\dashboard_$today.log" -Pattern "ERROR" -Context 2,2
```

## Advanced Topics

### Network Access

The bot automatically configures the dashboard for network access:
- **Local**: `http://127.0.0.1:8052/`
- **Network**: `http://<your-local-ip>:8052/`

Other devices on your network can access the dashboard using the network URL.

### Single Instance Protection

The bot automatically prevents multiple instances using a lock file:
- **Location**: `.telegram_bot.lock` (project root)
- **Automatic**: Lock created on start, removed on exit
- **Stale Detection**: Automatically detects and removes stale locks

### Data Loading

- **First Run**: Can take 6-7 minutes to fetch all data from API
- **Cached Data**: Subsequent runs use cached data (24-hour cache)
- **Progress Updates**: Bot shows real-time progress during data loading

### Performance Optimization

- **Single Coin Queries**: `/price` and `/marketcap` load only the requested coin (faster)
- **Cached Data**: Uses 24-hour cache to minimize API calls
- **Lazy Loading**: Data loaded only when needed
- **Fast Coin List**: `/coins` command reads directly from constants (instant response)

### User Action Tracking

All user interactions are logged to `logs/bot_users_YYYYMMDD.log`:
- **Commands**: All commands with user ID, username, and details
- **Button Clicks**: All button interactions tracked
- **Format**: Structured log entries for easy analysis

**View user activity:**
```powershell
# View today's user log
$today = Get-Date -Format "yyyyMMdd"
Get-Content "logs\bot_users_$today.log"

# Search for specific user
Select-String -Path "logs\bot_users_$today.log" -Pattern "UserID:123456789"
```

### Multi-User Dashboard Ownership

The bot supports multiple users with per-user dashboard ownership:
- **One Dashboard at a Time**: Only one dashboard can run (shared port)
- **Ownership Tracking**: Each dashboard instance is tracked with its owner
- **Owner-Only Control**: Only the owner can stop their dashboard
- **Status Visibility**: All users can see who started the dashboard
- **Automatic Cleanup**: Dead processes automatically removed from tracking

## Security Notes

- ✅ **Token Security**: Never commit your bot token to Git
- ✅ **Environment Variables**: Always use environment variables for tokens
- ✅ **Lock Files**: Lock file mechanism prevents accidental multiple instances
- ✅ **Network Access**: Dashboard accessible on local network (configure firewall as needed)
- ✅ **User Tracking**: User actions logged for audit purposes
- ✅ **Ownership Protection**: Only dashboard owners can stop their instances
- ✅ **Error Handling**: Robust error handling with retry logic for network issues

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review bot logs in `logs/` directory
3. Verify your bot token is correct
4. Ensure dependencies are installed: `pip install -r requirements.txt`

## Additional Resources

- **Telegram Bot API**: [https://core.telegram.org/bots/api](https://core.telegram.org/bots/api)
- **BotFather**: [@BotFather](https://t.me/botfather)
- **python-telegram-bot**: [https://python-telegram-bot.org/](https://python-telegram-bot.org/)
