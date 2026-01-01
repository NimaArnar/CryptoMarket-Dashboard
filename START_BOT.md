# How to Start the Telegram Bot

## Option 1: Bypass Execution Policy (One-time)

Run this command in PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File .\start_bot.ps1
```

## Option 2: Change Execution Policy (Permanent)

Run PowerShell as Administrator, then:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then you can run:
```powershell
.\start_bot.ps1
```

## Option 3: Manual Start (No Script Needed)

Just run these commands directly:
```powershell
$env:TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
python telegram_bot.py
```

## Option 4: Use Batch File Instead

I've created `start_bot.bat` which doesn't require execution policy changes.

