# Deployment Guide

## Option 1: GitHub Pages (Web Version - Recommended for Quick Demo)

A simplified JavaScript version of the dashboard is deployed on GitHub Pages:

- **URL**: [https://nimaarnar.github.io/CryptoMarket-Dashboard/](https://nimaarnar.github.io/CryptoMarket-Dashboard/)
- **Branch**: `gh-pages`
- **Location**: `docs/index.html`
- **Features**: 
  - BTC/ETH interactive charts
  - Market cap table with sorting
  - Smoothing controls (No smoothing, 7D SMA, 14D EMA, 30D SMA)
  - View options (Normalized Linear/Log, Market Cap Log)
  - Correlation analysis with scatter plots
  - Client-side caching (1 hour)
- **No Setup Required**: Works directly in browser, no server needed

**Note**: This is a simplified sample version. For the full-featured application with 25+ coins, use one of the Python hosting options below.

## Full Interactive Dashboard (Python Hosting)

The complete Dash application requires Python hosting. Use one of these platforms:

## Option 2: Render (Recommended - Free Tier)

1. **Sign up** at [render.com](https://render.com) (free account)
2. **Create a New Web Service**
3. **Connect your GitHub repository**
4. **Configure:**
   - **Name**: `crypto-market-dashboard`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Environment Variables** (optional):
     - `COINGECKO_API_KEY`: Your API key (if you have one)
     - `USE_ASYNC_FETCH`: `true`
     - `MAX_CONCURRENT_REQUESTS`: `5`

5. **Deploy** - Render will automatically deploy your app

Your app will be available at: `https://crypto-market-dashboard.onrender.com`

## Option 3: Railway

1. **Sign up** at [railway.app](https://railway.app)
2. **New Project** → **Deploy from GitHub repo**
3. **Select your repository**
4. Railway auto-detects Python and deploys

## Option 4: Heroku

1. **Sign up** at [heroku.com](https://heroku.com)
2. **Install Heroku CLI**
3. **Run:**
   ```bash
   heroku create crypto-market-dashboard
   git push heroku main
   ```

## Environment Variables

For cloud deployment, you may want to set:
- `PORT`: Automatically set by hosting platform
- `DASH_DEBUG`: Set to `false` in production
- `COINGECKO_API_KEY`: Your CoinGecko Pro API key (optional)
- `USE_ASYNC_FETCH`: `true` (default)
- `MAX_CONCURRENT_REQUESTS`: `5` (default)

## Telegram Bot Deployment

The Telegram bot can be deployed alongside the dashboard or separately:

### Option 1: Deploy Bot Separately (Recommended)

1. **Create a separate service** on your hosting platform
2. **Configure:**
   - **Start Command**: `python telegram_bot.py`
   - **Environment Variables**:
     - `TELEGRAM_BOT_TOKEN`: Your bot token (required)
     - `COINGECKO_API_KEY`: Optional, for faster API access
3. **Note**: The bot needs to be able to start the dashboard locally or via SSH

### Option 2: Run Bot Locally

For development or personal use, run the bot on your local machine:
```powershell
$env:TELEGRAM_BOT_TOKEN="your-token"
python telegram_bot.py
```

### Bot Requirements

- **Python 3.8+**
- **Dependencies**: `pip install -r requirements.txt`
- **Network Access**: Bot needs internet access for Telegram API
- **Local Dashboard**: Bot can start dashboard on same machine

## Notes

- The app uses port 8052 locally, but cloud platforms will set the `PORT` environment variable
- Debug mode is disabled in production for security
- Cache files (`cg_cache/`) will be recreated on each deployment
- Logs are saved to `logs/` directory
- Telegram bot logs are saved to `logs/bot_users_YYYYMMDD.log`

