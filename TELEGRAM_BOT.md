# Telegram Bot Setup Guide

This Telegram bot allows you to control your Crypto Market Dashboard remotely.

## Prerequisites

1. **Telegram Bot Token**: You need to create a bot and get a token from [@BotFather](https://t.me/botfather)

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the instructions to name your bot
4. Copy the token you receive (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

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

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Bot

```bash
python telegram_bot.py
```

## Commands

- `/start` - Show welcome message
- `/help` - Show help message
- `/run` - Start the dashboard server
- `/stop` - Stop the dashboard server
- `/status` - Check if dashboard is running

## Usage

1. Start the bot: `python telegram_bot.py`
2. Open Telegram and find your bot
3. Send `/start` to begin
4. Use `/run` to start the dashboard
5. Access dashboard at: `http://127.0.0.1:8052/`
6. Use `/stop` to stop the dashboard when done

## Notes

- The bot runs locally on your machine
- The dashboard will be accessible at `http://127.0.0.1:8052/`
- Make sure port 8052 is not in use by another application
- The bot will keep running until you stop it (Ctrl+C)

