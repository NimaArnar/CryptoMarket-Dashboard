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
# Default: 10 for free API, 30 for Pro API (can be overridden via env var)
# Higher concurrency = faster fetching, but must respect rate limits
# Pro API has higher rate limits, so we can use more concurrent requests
_has_pro_api = COINGECKO_API_KEY is not None
DEFAULT_MAX_CONCURRENT = 30 if _has_pro_api else 10
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_REQUESTS", str(DEFAULT_MAX_CONCURRENT)))

# Dash App Configuration
DASH_PORT = int(os.getenv("PORT", "8052"))  # Use PORT env var for cloud deployment
DASH_DEBUG = os.getenv("DASH_DEBUG", "False").lower() == "true"  # Disable debug in production

