"""Configuration settings for the dashboard."""
import os
from pathlib import Path
from typing import Optional

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# API Configuration
VS_CURRENCY = "usd"
DAYS_HISTORY = 365

# Retry Configuration
BASE_SLEEP = 1.2  # Base sleep time between requests
WAIT_TIME = 60  # Wait time on rate limit errors
BACKOFF_MULTIPLIER = 1
MAX_RETRIES = 3

# Correlation Configuration
MIN_CORR_DAYS = int(os.getenv("MIN_CORR_DAYS", "10"))

# Cache Configuration
CACHE_DIR = PROJECT_ROOT / "cg_cache"
CACHE_EXPIRY_HOURS = 24
CACHE_DIR.mkdir(exist_ok=True)

# Logging Configuration
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Export Configuration
EXPORT_DIR = PROJECT_ROOT / "market_caps Data"
EXPORT_DIR.mkdir(exist_ok=True)

# CoinGecko API Configuration
COINGECKO_API_KEY: Optional[str] = os.getenv("COINGECKO_API_KEY", None)
COINGECKO_API_BASE = "https://pro-api.coingecko.com/api/v3" if COINGECKO_API_KEY else "https://api.coingecko.com/api/v3"

# Async Configuration
USE_ASYNC = os.getenv("USE_ASYNC_FETCH", "true").lower() == "true"
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))

# Dash App Configuration
DASH_PORT = int(os.getenv("PORT", "8052"))  # Use PORT env var for cloud deployment
DASH_DEBUG = os.getenv("DASH_DEBUG", "False").lower() == "true"  # Disable debug in production

# Telegram Bot Configuration
BOT_MAX_DASHBOARD_WAIT = 480  # Maximum wait time for dashboard startup (seconds)
BOT_WAIT_INTERVAL = 2  # Interval between dashboard readiness checks (seconds)
BOT_PROCESSED_UPDATES_MAX = 100  # Maximum number of processed update IDs to track
BOT_PROCESSED_UPDATES_CLEANUP = 50  # Number of entries to keep after cleanup
BOT_MAX_MESSAGE_LENGTH = 4096  # Telegram message length limit
BOT_COINS_PER_PAGE = 20  # Number of coins to show per page in /coins command

