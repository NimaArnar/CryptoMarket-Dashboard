# Deployment Guide

## Option 0: Static HTML Dashboard on GitHub Pages (Auto-Updates Daily) ⭐

**Yes! You can create a static HTML version that updates automatically!**

I've set up a GitHub Actions workflow that:
- Runs daily (or on code changes)
- Generates a static HTML dashboard with the latest data
- Deploys it to GitHub Pages automatically

**To enable:**
1. Go to your repo Settings → Pages
2. Source: Deploy from a branch → Branch: `main` → Folder: `/docs`
3. Save
4. The workflow will run and generate `docs/index.html` automatically
5. Your dashboard will be at: `https://NimaArnar.github.io/CryptoMarket-Dashboard/`

**Note:** This is a static snapshot (not fully interactive), but it shows the latest charts and data, updated daily!

---

## Option 1: Full Interactive Dashboard (Python Hosting)

This Dash application cannot run on GitHub Pages (which only hosts static sites). Use one of these platforms that support Python:

## Option 1: Render (Recommended - Free Tier)

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

## Option 2: Railway

1. **Sign up** at [railway.app](https://railway.app)
2. **New Project** → **Deploy from GitHub repo**
3. **Select your repository**
4. Railway auto-detects Python and deploys

## Option 3: Heroku

1. **Sign up** at [heroku.com](https://heroku.com)
2. **Install Heroku CLI**
3. **Run:**
   ```bash
   heroku create crypto-market-dashboard
   git push heroku main
   ```

## Option 4: Use GitHub Pages for Documentation

While you can't host the Dash app on GitHub Pages, you can:

1. **Create a `docs/` folder** in your repo
2. **Add an `index.html`** that links to your deployed app
3. **Enable GitHub Pages** in repo settings → Pages → Source: `docs/` folder
4. Your docs will be at: `https://NimaArnar.github.io/CryptoMarket-Dashboard/`

## Environment Variables

For cloud deployment, you may want to set:
- `PORT`: Automatically set by hosting platform
- `DASH_DEBUG`: Set to `false` in production
- `COINGECKO_API_KEY`: Your CoinGecko Pro API key (optional)
- `USE_ASYNC_FETCH`: `true` (default)
- `MAX_CONCURRENT_REQUESTS`: `5` (default)

## Notes

- The app uses port 8052 locally, but cloud platforms will set the `PORT` environment variable
- Debug mode is disabled in production for security
- Cache files (`cg_cache/`) will be recreated on each deployment
- Logs are saved to `logs/` directory

