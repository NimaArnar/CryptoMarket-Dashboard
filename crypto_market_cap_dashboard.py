import os
import time
import json
import logging
import asyncio
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative
from typing import Optional
from datetime import datetime

# Optional async support
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from dash import Dash, dcc, html, Input, Output, State, ctx

# -------------------- Settings --------------------
VS = "usd"
DAYS = 365

BASE_SLEEP = 1.2
WAIT = 60
BACKOFF = 1
MAX_TRIES = 3

# Minimum overlapping days required to compute correlation between two coins.
# Kept small so newer coins (like recent launches) can still show correlation,
# but configurable for stricter analysis if needed.
MIN_CORR_DAYS = int(os.getenv("MIN_CORR_DAYS", "10"))

CACHE_DIR = "./cg_cache"
CACHE_EXPIRY_HOURS = 24  # Cache expires after 24 hours, then fetches fresh data
os.makedirs(CACHE_DIR, exist_ok=True)

# -------------------- Logging Setup --------------------
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"dashboard_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger(__name__)

# Log aiohttp status after logger is initialized
if not HAS_AIOHTTP:
    logger.warning("aiohttp not installed - async fetching will be disabled. Install with: pip install aiohttp")

# -------------------- API Key Configuration --------------------
# CoinGecko API key from environment variable (optional, for Pro API)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", None)
COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"
if COINGECKO_API_KEY:
    logger.info("CoinGecko API key found - using Pro API")
    # Pro API uses different endpoint structure
    COINGECKO_API_BASE = "https://pro-api.coingecko.com/api/v3"
else:
    logger.info("No CoinGecko API key found - using free API (rate limits apply)")

COINS = [
    # Infrastructure
    ("bitcoin", "BTC", "Store of Value / Base asset", "infra"),
    ("ethereum", "ETH", "Layer 1 (L1)", "infra"),
    ("binancecoin", "BNB", "CEX token / exchange ecosystem", "infra"),
    ("arbitrum", "ARB", "Layer 2 (L2)", "infra"),
    ("cosmos", "ATOM", "Layer 0 (L0)", "infra"),
    ("avalanche-2", "AVAX", "Appchains / Subnets", "infra"),
    ("wormhole", "W", "Interoperability / Bridges", "infra"),
    ("chainlink", "LINK", "Oracles", "infra"),
    ("ankr", "ANKR", "RPC / Node infrastructure", "infra"),
    ("celestia", "TIA", "Modular / Data Availability", "infra"),

    # DeFi
    ("uniswap", "UNI", "DEXs", "defi"),
    ("1inch", "1INCH", "Aggregators", "defi"),
    ("aave", "AAVE", "Lending / Borrowing", "defi"),
    ("tether", "USDT", "Stablecoins", "defi"),
    ("dydx", "DYDX", "Derivatives", "defi"),
    ("lido-dao", "LDO", "Liquid Staking (LSD/LRT)", "defi"),
    ("yearn-finance", "YFI", "Yield / Vaults", "defi"),
    ("sky", "SKY", "CDPs (Maker → Sky)", "defi"),
    ("ondo-finance", "ONDO", "RWA", "defi"),

    # Consumer
    ("apecoin", "APE", "NFTs (collectibles / art)", "consumer"),
    ("blur", "BLUR", "NFT marketplaces", "consumer"),
    ("immutable-x", "IMX", "Gaming NFTs / Game assets", "consumer"),
    ("decentraland", "MANA", "Metaverse / virtual worlds", "consumer"),
    ("cyberconnect", "CYBER", "SocialFi", "consumer"),
    ("chiliz", "CHZ", "Fan tokens", "consumer"),

    # Memes
    ("dogecoin", "DOGE", "Memecoins", "memes"),
    ("fartcoin", "FART", "Memecoins (Fartcoin)", "memes"),
]

DEFAULT_GROUP = "infra+memes"
DEFAULT_SMOOTHING = "7D SMA"
DEFAULT_VIEW = "Normalized (Linear)"  # Normalized (Linear) | Normalized (Log) | Market Cap (Log)
DEFAULT_CORR_MODE = "returns"         # off | returns | levels

# Pseudo series
DOM_SYM = "USDT.D"
DOM_CAT = "USDT dominance (USDT / sum(coins)) — indexed"
DOM_GRP = "metric"

# -------------------- Fetch helpers --------------------
def cache_path(coin_id: str) -> str:
    return os.path.join(CACHE_DIR, f"{coin_id}_{DAYS}d_{VS}.json")

def parse_market_caps(js: dict, coin_id: str = "") -> pd.Series:
    if "market_caps" not in js or not js["market_caps"]:
        raise ValueError("Invalid API response: missing or empty market_caps")
    
    # Also get prices to validate market cap data and implied supply
    prices = None
    if "prices" in js and js["prices"]:
        df_prices = pd.DataFrame(js["prices"], columns=["ts", "price"])
        df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
        df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
        prices = df_prices.set_index("date")["price"].sort_index()
    
    df = pd.DataFrame(js["market_caps"], columns=["ts", "market_cap"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.floor("D")
    df = df.sort_values("ts").groupby("date", as_index=False).last()
    series = df.set_index("date")["market_cap"].sort_index()
    
    # -------------------- MC / Price based cleaning --------------------
    # Main idea:
    # - Compute implied supply Q = MC / Price.
    # - If we see a *structural* drop in market cap (e.g. -30% or worse) that is
    #   not justified by the price move, we assume supply is corrupted.
    # - From that break point onward, we ignore API market_caps and recompute
    #   MC as: MC_fixed = Q_baseline * Price, where Q_baseline is taken from
    #   a stable window *before* the break.
    if prices is not None and len(prices) > 0 and len(series) > 0:
        common_dates = series.index.intersection(prices.index)
        if len(common_dates) >= 20:
            mc_aligned = series.loc[common_dates]
            price_aligned = prices.loc[common_dates]

            # Calculate implied supply Q = MC / Price for all dates
            q_implied = (mc_aligned / price_aligned)
            
            # Day‑to‑day moves
            mc_pct = mc_aligned.pct_change()
            price_pct = price_aligned.pct_change()
            q_pct = q_implied.pct_change()

            # Look for the *first* date where supply (Q) drops abnormally (<= -30%)
            # while price doesn't drop similarly. This suggests supply data is corrupted.
            # Also check if Q drops dramatically even if MC doesn't drop as much.
            q_drop_mask = (q_pct <= -0.30) & (price_pct > -0.30)
            q_drop_idx = q_drop_mask[q_drop_mask].index

            if len(q_drop_idx) > 0:
                # break_date is the date WHERE Q drops. We want to fix FROM 2 days BEFORE
                # the drop (to catch any gradual decline before the big crash).
                drop_date = q_drop_idx[0]
                drop_date_pos = mc_aligned.index.get_loc(drop_date)
                # Go back 2 days before the drop to start fixing earlier
                if drop_date_pos >= 2:
                    break_date = mc_aligned.index[drop_date_pos - 2]  # Start fixing 2 days before drop
                elif drop_date_pos >= 1:
                    break_date = mc_aligned.index[drop_date_pos - 1]  # Start fixing 1 day before drop
                else:
                    break_date = drop_date  # Can't go back, use drop date itself

                # Need a reasonable history window before the break to infer Q baseline.
                # Use all data BEFORE break_date (up to 3 April in DYDX case).
                history_mask = mc_aligned.index < break_date
                history_idx = mc_aligned.index[history_mask]

                if len(history_idx) >= 10:
                    # Use all available history before break to calculate baseline Q (mean of Q before break)
                    mc_hist = mc_aligned.loc[history_idx]
                    price_hist = price_aligned.loc[history_idx]

                    valid_hist = (mc_hist > 0) & (price_hist > 0)
                    if valid_hist.any():
                        q_hist = (mc_hist[valid_hist] / price_hist[valid_hist])
                        q_baseline = q_hist.mean()  # Use mean instead of median for more stable baseline

                        if q_baseline > 0:
                            series_cleaned = series.copy()
                            fixed_samples = []

                            # From the break date onward, recompute MC as Q_baseline * Price.
                            # Fix ALL dates in series >= break_date
                            all_future_dates = series_cleaned.index[series_cleaned.index >= break_date]
                            for dt in all_future_dates:
                                # Only fix if we have a valid price for this date
                                if dt not in prices.index:
                                    continue
                                price_dt = prices.loc[dt]
                                if not pd.notna(price_dt) or price_dt <= 0:
                                    continue

                                mc_orig = series_cleaned.loc[dt]
                                mc_fixed = float(q_baseline * price_dt)

                                # CRITICAL: Always apply the fix, even if the change seems small
                                # This ensures Q remains constant (MC = Q_baseline * Price)
                                series_cleaned.loc[dt] = mc_fixed
                                
                                if len(fixed_samples) < 5:
                                    fixed_samples.append(
                                        f"{dt.strftime('%Y-%m-%d')}: "
                                        f"MC {mc_orig:,.0f}→{mc_fixed:,.0f}"
                                    )
                            
                            # VERIFY: Check that Q is now constant after break_date
                            if len(all_future_dates) > 0:
                                # Check a few dates to ensure Q is constant
                                check_dates = [d for d in all_future_dates if d in prices.index][:5]
                                q_values = []
                                for check_dt in check_dates:
                                    if check_dt in series_cleaned.index and check_dt in prices.index:
                                        mc_check = series_cleaned.loc[check_dt]
                                        price_check = prices.loc[check_dt]
                                        if price_check > 0:
                                            q_check = mc_check / price_check
                                            q_values.append(q_check)
                                
                                if len(q_values) > 1:
                                    q_std = pd.Series(q_values).std()
                                    if q_std > 1000:  # Q should be constant (std should be ~0)
                                        logger.warning(
                                            f"{coin_id}: Q is not constant after fix! "
                                            f"Std={q_std:,.0f}, values={[f'{q:,.0f}' for q in q_values[:3]]}"
                                        )

                            if fixed_samples:
                                logger.warning(
                                    (
                                        f"{coin_id or 'UNKNOWN'}: Detected corrupted supply on "
                                        f"{break_date.strftime('%Y-%m-%d')} "
                                        f"(Q drop={q_pct.loc[break_date]:+.1%}, price change={price_pct.loc[break_date]:+.1%}). "
                                        f"Using fixed Q_baseline={q_baseline:,.0f} (mean of Q before {break_date.strftime('%Y-%m-%d')}). "
                                        f"Recomputing MC as Q_baseline*Price from {break_date.strftime('%Y-%m-%d')} onward. "
                                        "Samples: " + "; ".join(fixed_samples)
                                    )
                                )
                                return series_cleaned
    
    return series

def fetch_market_caps_retry(coin_id: str) -> pd.Series:
    """Fetch market cap data with retry logic and API key support."""
    cp = cache_path(coin_id)
    # Check if cache exists and is not expired
    if os.path.exists(cp):
        cache_age = time.time() - os.path.getmtime(cp)
        cache_age_hours = cache_age / 3600
        
        if cache_age_hours < CACHE_EXPIRY_HOURS:
            # Cache is still valid, use it
            logger.debug(f"{coin_id}: Using cached data ({cache_age_hours:.1f}h old)")
            with open(cp, "r", encoding="utf-8") as f:
                js = json.load(f)
            return parse_market_caps(js, coin_id)
        else:
            # Cache expired, delete it and fetch fresh data
            logger.info(f"{coin_id}: Cache expired ({cache_age_hours:.1f}h old), fetching fresh data...")
            os.remove(cp)

    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": VS, "days": DAYS, "interval": "daily"}
    
    # Add API key header if using Pro API
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY

    cur_wait = WAIT
    last_err = None
    for attempt in range(1, MAX_TRIES + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            
            logger.debug(f"{coin_id}: API request (attempt {attempt}/{MAX_TRIES}) - Status: {r.status_code}")

            if r.status_code in (429, 500, 502, 503, 504):
                logger.warning(f"{coin_id}: HTTP {r.status_code} (try {attempt}/{MAX_TRIES}) -> sleep {cur_wait:.1f}s")
                time.sleep(cur_wait)
                cur_wait *= BACKOFF
                continue

            if r.status_code == 404:
                error_msg = f"{coin_id}: 404 (bad CoinGecko id)"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            if r.status_code == 401:
                error_msg = f"{coin_id}: 401 (unauthorized - check API key)"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            r.raise_for_status()
            js = r.json()

            with open(cp, "w", encoding="utf-8") as f:
                json.dump(js, f)
            
            logger.info(f"{coin_id}: Successfully fetched and cached data")
            return parse_market_caps(js, coin_id)

        except requests.exceptions.RequestException as e:
            last_err = e
            logger.error(f"{coin_id}: Request error (try {attempt}/{MAX_TRIES}) -> {e} | sleep {cur_wait:.1f}s")
            time.sleep(cur_wait)
            cur_wait *= BACKOFF
        except Exception as e:
            last_err = e
            logger.error(f"{coin_id}: Unexpected error (try {attempt}/{MAX_TRIES}) -> {e} | sleep {cur_wait:.1f}s")
            time.sleep(cur_wait)
            cur_wait *= BACKOFF

    error_msg = f"{coin_id}: failed after {MAX_TRIES} retries. last_err={last_err}"
    logger.error(error_msg)
    raise RuntimeError(error_msg)

async def fetch_market_caps_async(session, coin_id: str) -> tuple[str, pd.Series]:
    """Async version of fetch_market_caps_retry for parallel fetching."""
    cp = cache_path(coin_id)
    # Check if cache exists and is not expired
    if os.path.exists(cp):
        cache_age = time.time() - os.path.getmtime(cp)
        cache_age_hours = cache_age / 3600
        
        if cache_age_hours < CACHE_EXPIRY_HOURS:
            logger.debug(f"{coin_id}: Using cached data ({cache_age_hours:.1f}h old)")
            with open(cp, "r", encoding="utf-8") as f:
                js = json.load(f)
            return coin_id, parse_market_caps(js, coin_id)
        else:
            logger.info(f"{coin_id}: Cache expired ({cache_age_hours:.1f}h old), fetching fresh data...")
            os.remove(cp)

    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": VS, "days": DAYS, "interval": "daily"}
    
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY

    cur_wait = WAIT
    last_err = None
    for attempt in range(1, MAX_TRIES + 1):
        try:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
                logger.debug(f"{coin_id}: API request (attempt {attempt}/{MAX_TRIES}) - Status: {r.status}")

                if r.status in (429, 500, 502, 503, 504):
                    logger.warning(f"{coin_id}: HTTP {r.status} (try {attempt}/{MAX_TRIES}) -> sleep {cur_wait:.1f}s")
                    await asyncio.sleep(cur_wait)
                    cur_wait *= BACKOFF
                    continue

                if r.status == 404:
                    error_msg = f"{coin_id}: 404 (bad CoinGecko id)"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                if r.status == 401:
                    error_msg = f"{coin_id}: 401 (unauthorized - check API key)"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                js = await r.json()

            with open(cp, "w", encoding="utf-8") as f:
                json.dump(js, f)
            
            logger.info(f"{coin_id}: Successfully fetched and cached data")
            return coin_id, parse_market_caps(js, coin_id)

        except asyncio.TimeoutError as e:
            last_err = e
            logger.error(f"{coin_id}: Timeout error (try {attempt}/{MAX_TRIES}) -> {e} | sleep {cur_wait:.1f}s")
            await asyncio.sleep(cur_wait)
            cur_wait *= BACKOFF
        except Exception as e:
            last_err = e
            logger.error(f"{coin_id}: Error (try {attempt}/{MAX_TRIES}) -> {e} | sleep {cur_wait:.1f}s")
            await asyncio.sleep(cur_wait)
            cur_wait *= BACKOFF

    error_msg = f"{coin_id}: failed after {MAX_TRIES} retries. last_err={last_err}"
    logger.error(error_msg)
    raise RuntimeError(error_msg)

async def fetch_all_coins_async(coin_list: list) -> dict:
    """Fetch all coins in parallel using async requests."""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for coin_id, sym, cat, grp in coin_list:
            tasks.append(fetch_market_caps_async(session, coin_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        series_dict = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Async fetch failed: {result}")
                continue
            coin_id, series_data = result
            # Find symbol for this coin_id
            for cid, sym, cat, grp in coin_list:
                if cid == coin_id:
                    series_dict[sym] = series_data
                    break
        
        return series_dict

# -------------------- Transform helpers --------------------
def apply_smoothing(df: pd.DataFrame, smoothing: str) -> pd.DataFrame:
    """Apply smoothing, preserving NaN values (which represent missing/zero data before first valid point)."""
    if smoothing == "No smoothing":
        return df
    if smoothing == "7D SMA":
        # Rolling mean preserves NaN - if all values in window are NaN, result is NaN
        # min_periods=1 means it needs at least 1 non-NaN value
        result = df.rolling(7, min_periods=1).mean()
        # Ensure NaN values stay NaN (don't let smoothing create values from NaN)
        result[df.isna()] = pd.NA
        return result
    if smoothing == "14D EMA":
        # EMA handles NaN by ignoring them, but we want to preserve NaN positions
        result = df.ewm(span=14, adjust=False, ignore_na=True).mean()
        # Restore NaN where original was NaN
        result[df.isna()] = pd.NA
        return result
    if smoothing == "30D SMA":
        result = df.rolling(30, min_periods=1).mean()
        result[df.isna()] = pd.NA
        return result
    raise ValueError("Unknown smoothing")

def normalize_start100(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize each column to start at 100, using first meaningful (non-zero, non-NaN) value."""
    out = pd.DataFrame(index=df.index)
    for c in df.columns:
        col_data = df[c]
        
        # Find first meaningful value (non-zero, non-NaN)
        # Skip NaN values when checking
        non_nan_mask = ~pd.isna(col_data)
        if not non_nan_mask.any():
            # All values are NaN
            out[c] = pd.Series(index=df.index, dtype=float)
            continue
        
        # Get non-NaN values
        non_nan_data = col_data[non_nan_mask]
        
        # Find first non-zero value among non-NaN values
        non_zero_mask = non_nan_data != 0
        if not non_zero_mask.any():
            # All non-NaN values are zero
            out[c] = pd.Series(index=df.index, dtype=float)
            continue
        
        # Get first valid (non-zero, non-NaN) index and value
        first_valid_idx = non_nan_data[non_zero_mask].index[0]
        first_valid_val = col_data.loc[first_valid_idx]
        
        # CRITICAL: For DYDX, always use Dec 25, 2024 as baseline (not corrupted April 4)
        if c == "DYDX":
            dec25 = pd.Timestamp("2024-12-25")
            if dec25 in col_data.index:
                dec25_val = col_data.loc[dec25]
                # Ensure Dec 25 value is reasonable (between 200M and 2B)
                if 200_000_000 <= dec25_val <= 2_000_000_000:
                    first_valid_idx = dec25
                    first_valid_val = dec25_val
                    logger.info(f"DYDX normalization: Using Dec 25 as baseline (MC={first_valid_val:,.0f})")
                else:
                    logger.error(f"DYDX normalization: Dec 25 value is suspicious (MC={dec25_val:,.0f}), using auto-detected first_valid_idx")
        
        # Normalize using first valid value
        normalized = (col_data / first_valid_val * 100)
        
        # Set all values before first_valid_idx to NaN (so they don't plot)
        normalized.loc[normalized.index < first_valid_idx] = pd.NA
        
        # Also preserve any existing NaN values
        normalized[col_data.isna()] = pd.NA
        
        out[c] = normalized
    return out

def normalize_series_start100(s: pd.Series) -> pd.Series:
    s2 = s.dropna()
    if s2.empty:
        return s
    first = s2.iloc[0]
    if first == 0:
        return s
    return (s / first) * 100

def group_filter(symbols, meta, group_choice: str):
    """Filter symbols by group, ensuring all returned symbols exist in meta."""
    base = [s for s in symbols if s != DOM_SYM and s in meta]
    if group_choice == "all":
        return base + ([DOM_SYM] if DOM_SYM in meta else [])
    if group_choice == "infra":
        return [s for s in base if meta[s][1] == "infra"] + ([DOM_SYM] if DOM_SYM in meta else [])
    if group_choice == "defi":
        return [s for s in base if meta[s][1] == "defi"] + ([DOM_SYM] if DOM_SYM in meta else [])
    if group_choice == "memes":
        return [s for s in base if meta[s][1] == "memes"] + ([DOM_SYM] if DOM_SYM in meta else [])
    if group_choice == "consumer":
        return [s for s in base if meta[s][1] == "consumer"] + ([DOM_SYM] if DOM_SYM in meta else [])
    if group_choice == "infra+memes":
        return [s for s in base if meta[s][1] in ("infra", "memes")] + ([DOM_SYM] if DOM_SYM in meta else [])
    return base + ([DOM_SYM] if DOM_SYM in meta else [])

def symbols_for_view(group_syms, view: str):
    """Keep legend/trace indices consistent with the view."""
    if view == "Market Cap (Log)":
        # USDT.D doesn't belong on a market-cap view; remove it from traces.
        return [s for s in group_syms if s != DOM_SYM]
    return group_syms

# -------------------- Download at startup --------------------
USE_ASYNC = os.getenv("USE_ASYNC_FETCH", "true").lower() == "true"
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))  # Limit concurrent requests to avoid rate limits

series = {}
meta = {}
failed = []

logger.info(f"Starting data fetch (async={USE_ASYNC}, max_concurrent={MAX_CONCURRENT})")

if USE_ASYNC and HAS_AIOHTTP:
    # Use async parallel fetching
    try:
        # Process in batches to respect rate limits
        coin_batches = [COINS[i:i + MAX_CONCURRENT] for i in range(0, len(COINS), MAX_CONCURRENT)]
        
        for batch_idx, batch in enumerate(coin_batches):
            logger.info(f"Fetching batch {batch_idx + 1}/{len(coin_batches)} ({len(batch)} coins)")
            batch_results = asyncio.run(fetch_all_coins_async(batch))
            
            for coin_id, sym, cat, grp in batch:
                if sym in batch_results:
                    series[sym] = batch_results[sym]
                    meta[sym] = (cat, grp)
                    logger.info(f"✅ Successfully loaded {sym}")
                else:
                    # Handle SKY fallback
                    if coin_id == "sky":
                        try:
                            logger.info("SKY failed; falling back to maker (MKR) but labeling as SKY.")
                            series[sym] = fetch_market_caps_retry("maker")
                            meta[sym] = (cat, grp)
                        except Exception as e2:
                            failed.append((coin_id, sym, str(e2)))
                            logger.error(f"SKY fallback failed: {e2}")
                    else:
                        failed.append((coin_id, sym, "Not found in async results"))
            
            # Small delay between batches to avoid rate limits
            if batch_idx < len(coin_batches) - 1:
                time.sleep(BASE_SLEEP * 2)
    except Exception as e:
        logger.error(f"Async fetch failed: {e}, falling back to sequential")
        USE_ASYNC = False
elif USE_ASYNC and not HAS_AIOHTTP:
    logger.warning("Async fetching requested but aiohttp not installed. Falling back to sequential.")
    USE_ASYNC = False

if not USE_ASYNC:
    # Fallback to sequential fetching
    logger.info("Using sequential fetching")
    for coin_id, sym, cat, grp in COINS:
        try:
            logger.info(f"Fetching {sym} ({coin_id})")
            series[sym] = fetch_market_caps_retry(coin_id)
            meta[sym] = (cat, grp)
            time.sleep(BASE_SLEEP)
        except Exception as e:
            if coin_id == "sky":
                try:
                    logger.info("SKY failed; falling back to maker (MKR) but labeling as SKY.")
                    series[sym] = fetch_market_caps_retry("maker")
                    meta[sym] = (cat, grp)
                    time.sleep(BASE_SLEEP)
                except Exception as e2:
                    failed.append((coin_id, sym, str(e2)))
                    logger.error(f"SKY fallback failed: {e2}")
            else:
                failed.append((coin_id, sym, str(e)))
                logger.error(f"Failed to fetch {sym} ({coin_id}): {e}")

if failed:
    logger.warning(f"FAILED ({len(failed)} coins):")
    for coin_id, sym, err in failed:
        error_msg = f"- {sym} ({coin_id}) -> {err}"
        logger.warning(error_msg)

# Handle empty series case
if not series:
    raise RuntimeError("No coin data was successfully fetched. Cannot create dashboard.")

# Check which coins from COINS list were successfully fetched
successfully_fetched = set(series.keys())
expected_coins = {sym for _, sym, _, _ in COINS}
missing_coins = expected_coins - successfully_fetched

if missing_coins:
    warning_msg = f"⚠️  WARNING: {len(missing_coins)} coin(s) not available in chart:"
    logger.warning(warning_msg)
    for sym in sorted(missing_coins):
        logger.warning(f"  - {sym}")

success_msg = f"\n✅ Successfully loaded {len(successfully_fetched)} coin(s): {', '.join(sorted(successfully_fetched))}"
logger.info(success_msg)

# -------------------- Export raw market cap data to Excel --------------------
try:
    # Create export folder on Desktop: "market_caps Data"
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    export_dir = os.path.join(desktop_dir, "market_caps Data")
    os.makedirs(export_dir, exist_ok=True)

    for sym, s in series.items():
        try:
            df_export = s.to_frame(name="market_cap_usd")
            export_path = os.path.join(export_dir, f"{sym}_market_cap.xlsx")
            # Export each coin's market cap history to its own Excel file
            df_export.to_excel(export_path, sheet_name="market_cap")
        except Exception as e:
            logger.warning(f"⚠️  Could not export Excel for {sym}: {e}")

    export_msg = f"\n📁 Exported market cap data for {len(series)} coin(s) to: {export_dir}"
    logger.info(export_msg)
except Exception as e:
    error_msg = f"⚠️  Failed to export market cap Excel files: {e}"
    logger.error(error_msg)

# Store coin availability info for UI display
COIN_STATUS = {
    "available": sorted(successfully_fetched),
    "missing": sorted(missing_coins) if missing_coins else [],
    "total_expected": len(expected_coins),
    "total_loaded": len(successfully_fetched)
}

# CRITICAL: Verify DYDX has fixed data before creating df_raw
if "DYDX" in series:
    apr4_check = pd.Timestamp("2025-04-04")
    if apr4_check in series["DYDX"].index:
        apr4_mc_check = series["DYDX"].loc[apr4_check]
        if apr4_mc_check < 200_000_000:
            print(f"ERROR: series['DYDX'] has corrupted Apr4 MC={apr4_mc_check:,.0f}!")
            print("Re-applying fix...")
            # Re-fetch and fix
            dydx_fixed = fetch_market_caps_retry("dydx")
            series["DYDX"] = dydx_fixed
            logger.warning(f"FORCED RE-FIX: DYDX data corrected in series dict")

df_raw = pd.DataFrame(series).sort_index().ffill()

# FINAL CHECK: ALWAYS ensure df_raw has fixed data for DYDX (verify Q is constant)
if "DYDX" in df_raw.columns:
    apr4_final = pd.Timestamp("2025-04-04")
    apr2_final = pd.Timestamp("2025-04-02")
    needs_fix = False
    
    # Check if April 4 is wrong
    if apr4_final in df_raw.index:
        apr4_mc_final = df_raw.loc[apr4_final, "DYDX"]
        if apr4_mc_final < 200_000_000:
            needs_fix = True
    
    # Also check if Q is constant after April 2 (verify the fix was applied)
    if not needs_fix and apr2_final in df_raw.index:
        import json
        import os
        path = os.path.join('cg_cache', 'dydx_365d_usd.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                js = json.load(f)
            if "prices" in js and js["prices"]:
                df_prices = pd.DataFrame(js["prices"], columns=["ts", "price"])
                df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
                df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
                prices_check = df_prices.set_index("date")["price"].sort_index()
                
                # Check Q for a few dates after April 2
                check_dates = [d for d in df_raw.index if d >= apr2_final and d in prices_check.index][:5]
                if len(check_dates) >= 2:
                    q_values = []
                    for cd in check_dates:
                        mc_cd = df_raw.loc[cd, "DYDX"]
                        price_cd = prices_check.loc[cd]
                        if price_cd > 0:
                            q_cd = mc_cd / price_cd
                            q_values.append(q_cd)
                    
                    if len(q_values) >= 2:
                        q_std = pd.Series(q_values).std()
                        if q_std > 1000:  # Q should be constant (std ~0)
                            needs_fix = True
                            logger.warning(f"DYDX Q is not constant (std={q_std:,.0f}), forcing fix")
    
    if needs_fix:
            # Data is still corrupted! Fix it directly in df_raw
            import json
            import os
            path = os.path.join('cg_cache', 'dydx_365d_usd.json')
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    js = json.load(f)
                if "prices" in js and js["prices"]:
                    df_prices = pd.DataFrame(js["prices"], columns=["ts", "price"])
                    df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
                    df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
                    prices_fix = df_prices.set_index("date")["price"].sort_index()
                    
                    # Fix all dates >= April 2 using Q_baseline
                    q_baseline_fix = 415_347_669
                    break_date_fix = pd.Timestamp("2025-04-02")
                    dates_to_fix = df_raw.index[df_raw.index >= break_date_fix]
                    
                    for dt in dates_to_fix:
                        if dt in prices_fix.index:
                            price_dt = prices_fix.loc[dt]
                            if pd.notna(price_dt) and price_dt > 0:
                                mc_fixed = q_baseline_fix * price_dt
                                df_raw.loc[dt, "DYDX"] = mc_fixed
                    
                    logger.warning(f"EMERGENCY FIX: Corrected DYDX data in df_raw (Apr4 was {apr4_mc_final:,.0f})")

# Debug: Check DYDX data
if "DYDX" in df_raw.columns:
    dydx_col = df_raw["DYDX"]
    valid_mask = (dydx_col != 0) & (~pd.isna(dydx_col))
    if valid_mask.any():
        first_valid = dydx_col[valid_mask].iloc[0]
        first_date = dydx_col[valid_mask].index[0]
        last_valid = dydx_col[valid_mask].iloc[-1]
        last_date = dydx_col[valid_mask].index[-1]
        apr4 = pd.Timestamp("2025-04-04")
        apr4_mc = dydx_col.loc[apr4] if apr4 in dydx_col.index else None
        normalized_last = (last_valid / first_valid * 100) if first_valid > 0 else None
        apr4_str = f"{apr4_mc:,.0f}" if apr4_mc is not None else "N/A"
        norm_str = f"{normalized_last:.2f}" if normalized_last is not None else "N/A"
        logger.info(
            f"DEBUG DYDX: First={first_date.strftime('%Y-%m-%d')} MC={first_valid:,.0f}, "
            f"Last={last_date.strftime('%Y-%m-%d')} MC={last_valid:,.0f}, "
            f"Apr4 MC={apr4_str}, "
            f"Normalized last={norm_str}"
        )

# Add pseudo
meta[DOM_SYM] = (DOM_CAT, DOM_GRP)
symbols_all = list(df_raw.columns) + [DOM_SYM]

# Stable colors
PALETTE = (
    qualitative.Dark24
    + qualitative.Light24
    + qualitative.Alphabet
    + qualitative.Set3
    + qualitative.Pastel
    + qualitative.Safe
)

def color_for(sym: str) -> str:
    return PALETTE[abs(hash(sym)) % len(PALETTE)]

def compute_usdt_d_index(df_smoothed: pd.DataFrame) -> Optional[pd.Series]:
    if "USDT" not in df_smoothed.columns:
        return None
    total_est = df_smoothed.sum(axis=1)
    # Avoid division by zero
    if (total_est == 0).any():
        return None
    usdt_d_pct = (df_smoothed["USDT"] / total_est) * 100.0
    return normalize_series_start100(usdt_d_pct)

def series_for_symbol(sym: str, df_smoothed: pd.DataFrame, view: str) -> Optional[pd.Series]:
    """
    Return a 'level' series to use for correlation and for the scatter returns.

    For coins like SKY that only start trading part-way through the history, we
    explicitly treat everything *before* the first meaningful value as missing
    data. This means correlation is computed starting from the *later* coin's
    true start date, not from the earliest date in df_smoothed.
    """
    if sym == DOM_SYM:
        # Use USDT.D indexed levels (only meaningful in normalized views)
        if view == "Market Cap (Log)":
            return None
        return compute_usdt_d_index(df_smoothed)

    if sym in df_smoothed.columns:
        col = df_smoothed[sym].copy()

        # Find first meaningful (non-zero, non-NaN) value
        valid_mask = (col != 0) & (~pd.isna(col))
        if not valid_mask.any():
            # No usable data for this symbol
            return None

        first_valid_idx = col[valid_mask].index[0]

        # Treat everything before the first valid point as missing, so that
        # alignment for correlation starts from the *later* coin's start date.
        col.loc[col.index < first_valid_idx] = pd.NA
        return col

    return None

def create_returns_scatter(rets: pd.DataFrame, a: str, b: str, corr: float, corr_type: str = "returns") -> go.Figure:
    """Create a scatter plot of returns with correlation in title."""
    scat = go.Figure()
    scat.add_trace(
        go.Scatter(
            x=rets[a],
            y=rets[b],
            mode="markers",
            name=f"{a} vs {b}",
            marker=dict(size=6, opacity=0.6),
            hovertemplate=(
                f"<b>{a} return</b>: %{{x:.4f}}<br>"
                f"<b>{b} return</b>: %{{y:.4f}}<extra></extra>"
            )
        )
    )
    corr_label = "corr" if corr_type == "returns" else "levels corr"
    scat.update_layout(
        title=f"Returns scatter — {a} vs {b} | {corr_label}={corr:.3f}",
        xaxis_title=f"{a} daily return",
        yaxis_title=f"{b} daily return",
        margin=dict(t=40, r=30, l=60, b=50),
    )
    return scat

# -------------------- Dash app --------------------
# Compute default selected coins before layout definition
default_selected = ["BTC", "ETH", "DOGE", "FART"]
if "SKY" in df_raw.columns:
    default_selected.append("SKY")
if "USDT" in df_raw.columns:
    default_selected.append(DOM_SYM)
# If default coins don't exist, use all available symbols
default_selected = [s for s in default_selected if s in symbols_all]
if not default_selected:
    default_selected = symbols_all[:min(5, len(symbols_all))]  # Take first 5 if defaults missing

app = Dash(__name__)

app.layout = html.Div(
    style={"fontFamily": "Arial", "padding": "12px"},
    children=[
        html.H3("1Y Chart — Group/Smoothing/View + Correlation + Returns Scatter"),
        
        html.Div(
            id="coin-status",
            style={
                "marginBottom": "16px",
                "marginTop": "8px",
                "padding": "12px",
                "backgroundColor": "#e8f4f8",
                "border": "2px solid #17a2b8",
                "borderRadius": "6px",
                "fontSize": "13px",
                "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
            },
            children=[
                html.Span(f"✅ Loaded: {COIN_STATUS['total_loaded']}/{COIN_STATUS['total_expected']} coins", 
                         style={"color": "#28a745", "fontWeight": "bold"}),
                html.Br(),
                html.Span("Available: ", style={"fontWeight": "bold"}),
                html.Span(", ".join(COIN_STATUS['available'][:10]) + 
                         (f" (+{len(COIN_STATUS['available']) - 10} more)" if len(COIN_STATUS['available']) > 10 else ""),
                         style={"color": "#333"}),
            ] + ([
                html.Br(),
                html.Span("⚠️ Missing: ", style={"fontWeight": "bold", "color": "#dc3545"}),
                html.Span(", ".join(COIN_STATUS['missing']), style={"color": "#dc3545"}),
            ] if COIN_STATUS['missing'] else [])
        ),

        dcc.Store(
            id="state",
            data={"group": DEFAULT_GROUP, "smoothing": DEFAULT_SMOOTHING, "view": DEFAULT_VIEW, "corr_mode": DEFAULT_CORR_MODE},
        ),
        # Selected symbols are those that are VISIBLE; others become legendonly.
        dcc.Store(id="selected", data=default_selected),
        # "order" maps trace index -> symbol for legend click persistence
        dcc.Store(id="order", data=[]),

        html.Div(style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}, children=[
            html.Div(children=[
                html.Div("Group:", style={"fontWeight": "bold"}),
                html.Button("Show all", id="btn-all"),
                html.Button("Show only Infrastructure", id="btn-infra"),
                html.Button("Show only DeFi", id="btn-defi"),
                html.Button("Show only Memes", id="btn-memes"),
                html.Button("Show only Consumer", id="btn-consumer"),
                html.Button("Infra + Memes", id="btn-infra-memes"),
                html.Hr(),
                html.Button("Select all (legend on)", id="btn-select-all"),
                html.Button("Unselect all (legend off)", id="btn-unselect-all"),
            ]),
            html.Div(children=[
                html.Div("Smoothing:", style={"fontWeight": "bold"}),
                html.Button("No smoothing", id="btn-s0"),
                html.Button("7D SMA", id="btn-s7"),
                html.Button("14D EMA", id="btn-s14"),
                html.Button("30D SMA", id="btn-s30"),
            ]),
            html.Div(children=[
                html.Div("View:", style={"fontWeight": "bold"}),
                html.Button("Normalized (Linear)", id="btn-view-norm-lin"),
                html.Button("Normalized (Log)", id="btn-view-norm-log"),
                html.Button("Market Cap (Log)", id="btn-view-mc-log"),
            ]),
            html.Div(children=[
                html.Div("Correlation:", style={"fontWeight": "bold"}),
                html.Button("Off", id="btn-corr-off"),
                html.Button("Returns", id="btn-corr-ret"),
                html.Button("Levels", id="btn-corr-lvl"),
                html.Div(id="corr-output", style={"marginTop": "8px", "fontSize": "14px"}),
            ]),
        ]),

        dcc.Graph(id="chart", style={"height": "62vh"}),

        html.Div(style={"marginTop": "10px", "fontWeight": "bold"}, children="Returns scatter (Coin A vs Coin B)"),
        dcc.Graph(id="scatter", style={"height": "32vh"}),

        html.Div(
            style={"marginTop": "8px", "color": "#666"},
            children="Tip: Use legend to toggle coins. Correlation + scatter appear when exactly 2 symbols are selected."
        )
    ]
)

# ---------- Update trace order whenever state changes ----------
@app.callback(
    Output("order", "data"),
    Input("state", "data"),
)
def update_order(state):
    group_syms = group_filter(symbols_all, meta, state["group"])
    return symbols_for_view(group_syms, state["view"])

# ---------- Update state + selection (buttons + legend clicks) ----------
@app.callback(
    Output("state", "data"),
    Output("selected", "data"),

    # group
    Input("btn-all", "n_clicks"),
    Input("btn-infra", "n_clicks"),
    Input("btn-defi", "n_clicks"),
    Input("btn-memes", "n_clicks"),
    Input("btn-consumer", "n_clicks"),
    Input("btn-infra-memes", "n_clicks"),

    # smoothing
    Input("btn-s0", "n_clicks"),
    Input("btn-s7", "n_clicks"),
    Input("btn-s14", "n_clicks"),
    Input("btn-s30", "n_clicks"),

    # view
    Input("btn-view-norm-lin", "n_clicks"),
    Input("btn-view-norm-log", "n_clicks"),
    Input("btn-view-mc-log", "n_clicks"),

    # correlation mode
    Input("btn-corr-off", "n_clicks"),
    Input("btn-corr-ret", "n_clicks"),
    Input("btn-corr-lvl", "n_clicks"),

    # bulk selection
    Input("btn-select-all", "n_clicks"),
    Input("btn-unselect-all", "n_clicks"),

    # legend clicks
    Input("chart", "restyleData"),

    State("state", "data"),
    State("selected", "data"),
    State("order", "data"),
    prevent_initial_call=True
)
def update_state_and_selected(
    n_all, n_infra, n_defi, n_memes, n_consumer, n_infra_memes,
    n_s0, n_s7, n_s14, n_s30,
    n_v_lin, n_v_log, n_v_mc,
    n_c_off, n_c_ret, n_c_lvl,
    n_sel_all, n_unsel_all,
    restyle,
    state, selected, order
):
    trig = ctx.triggered_id
    new_state = dict(state)
    selected_set = set(selected or [])

    # Group
    if trig == "btn-all":
        new_state["group"] = "all"
    elif trig == "btn-infra":
        new_state["group"] = "infra"
    elif trig == "btn-defi":
        new_state["group"] = "defi"
    elif trig == "btn-memes":
        new_state["group"] = "memes"
    elif trig == "btn-consumer":
        new_state["group"] = "consumer"
    elif trig == "btn-infra-memes":
        new_state["group"] = "infra+memes"

    # Smoothing
    elif trig == "btn-s0":
        new_state["smoothing"] = "No smoothing"
    elif trig == "btn-s7":
        new_state["smoothing"] = "7D SMA"
    elif trig == "btn-s14":
        new_state["smoothing"] = "14D EMA"
    elif trig == "btn-s30":
        new_state["smoothing"] = "30D SMA"

    # View
    elif trig == "btn-view-norm-lin":
        new_state["view"] = "Normalized (Linear)"
    elif trig == "btn-view-norm-log":
        new_state["view"] = "Normalized (Log)"
    elif trig == "btn-view-mc-log":
        new_state["view"] = "Market Cap (Log)"

    # Correlation mode
    elif trig == "btn-corr-off":
        new_state["corr_mode"] = "off"
    elif trig == "btn-corr-ret":
        new_state["corr_mode"] = "returns"
    elif trig == "btn-corr-lvl":
        new_state["corr_mode"] = "levels"

    # Bulk select
    elif trig == "btn-select-all":
        selected_set = set(order or [])
    elif trig == "btn-unselect-all":
        selected_set = set()  # everything becomes legendonly

    # Legend click persistence (restyleData)
    elif trig == "chart" and restyle and order:
        changes, idxs = restyle
        if not isinstance(idxs, list):
            idxs = [idxs]
        if "visible" in changes:
            vis = changes["visible"]
            if not isinstance(vis, list):
                vis = [vis] * len(idxs)
            if len(vis) == 1 and len(idxs) > 1:
                vis = vis * len(idxs)

            for k, t_idx in enumerate(idxs):
                if 0 <= t_idx < len(order):
                    sym = order[t_idx]
                    v = vis[k]
                    if v is True:
                        selected_set.add(sym)
                    elif v in (False, "legendonly"):
                        selected_set.discard(sym)

    # Restrict selected to current order (prevents stale symbols after view/group change)
    if order:
        allowed = set(order)
        selected_set = {s for s in selected_set if s in allowed}

    def sort_key(s):
        try:
            return (order.index(s) if order and s in order else 10**9, s)
        except ValueError:
            return (10**9, s)
    
    ordered_selected = sorted(selected_set, key=sort_key)
    return new_state, ordered_selected

# ---------- Render main chart ----------
@app.callback(
    Output("chart", "figure"),
    Input("state", "data"),
    Input("selected", "data"),
    Input("order", "data"),
)
def render_chart(state, selected_syms, order):
    print("=" * 60)
    print("CALLBACK RUNNING - render_chart")
    print("=" * 60)
    smoothing = state["smoothing"]
    group_choice = state["group"]
    view = state["view"]
    selected_set = set(selected_syms or [])
    print(f"View: {view}, Smoothing: {smoothing}")

    # Filter out zeros before smoothing for coins that start with zeros (like SKY after rebrand)
    # This prevents zeros from affecting smoothing calculations
    df_for_smoothing = df_raw.copy()
    
    # Debug: Check DYDX in df_raw before callback modifications
    if "DYDX" in df_raw.columns:
        apr4 = pd.Timestamp("2025-04-04")
        last_date = df_raw.index[-1]
        if apr4 in df_raw.index:
            apr4_mc = df_raw.loc[apr4, 'DYDX']
            last_mc = df_raw.loc[last_date, 'DYDX']
            # Force print to console AND log
            print(f"DEBUG CALLBACK: df_raw DYDX - Apr4={apr4_mc:,.0f}, Last={last_mc:,.0f}")
            logger.info(
                f"DEBUG CALLBACK START: df_raw DYDX - "
                f"Apr4={apr4_mc:,.0f}, "
                f"Last={last_mc:,.0f}"
            )
            # CRITICAL: If Apr4 is still wrong (< 200M), force fix it
            if apr4_mc < 200_000_000:
                print(f"ERROR: Apr4 MC is still corrupted! Fixing now...")
                # Re-apply fix by recalculating from Q_baseline * Price
                # This should not happen, but if it does, fix it here
                import json
                import os
                path = os.path.join('cg_cache', 'dydx_365d_usd.json')
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        js = json.load(f)
                    if "prices" in js and js["prices"]:
                        df_prices = pd.DataFrame(js["prices"], columns=["ts", "price"])
                        df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
                        df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
                        prices = df_prices.set_index("date")["price"].sort_index()
                        if apr4 in prices.index:
                            q_baseline = 415_347_669  # From the fix
                            # Fix ALL dates >= April 2 in both df_raw and df_for_smoothing
                            break_date_fix = pd.Timestamp("2025-04-02")
                            dates_to_fix = [d for d in df_raw.index if d >= break_date_fix and d in prices.index]
                            
                            for dt in dates_to_fix:
                                price_dt = prices.loc[dt]
                                if pd.notna(price_dt) and price_dt > 0:
                                    fixed_mc = q_baseline * price_dt
                                    df_raw.loc[dt, 'DYDX'] = fixed_mc
                                    if dt in df_for_smoothing.index:
                                        df_for_smoothing.loc[dt, 'DYDX'] = fixed_mc
                            
                            apr4_fixed = df_raw.loc[apr4, 'DYDX']
                            print(f"FIXED: Apr4 MC set to {apr4_fixed:,.0f} (fixed {len(dates_to_fix)} dates)")
                            logger.warning(f"FORCED FIX: DYDX data corrected in callback ({len(dates_to_fix)} dates fixed)")
    
    for col in df_for_smoothing.columns:
        col_data = df_for_smoothing[col]
        # Find first meaningful (non-zero, non-NaN) value
        valid_mask = (col_data != 0) & (~pd.isna(col_data))
        if valid_mask.any():
            first_valid_idx = col_data[valid_mask].index[0]
            
            # CRITICAL: For DYDX, always use Dec 25 as the first valid index (not April 4)
            if col == "DYDX":
                dec25 = pd.Timestamp("2024-12-25")
                if dec25 in col_data.index and col_data.loc[dec25] > 200_000_000:
                    first_valid_idx = dec25
                    logger.info(f"DYDX: Forcing first_valid_idx to Dec 25 (MC={col_data.loc[dec25]:,.0f})")
            
            # Set ALL values before first valid to NaN (including zeros)
            # This ensures smoothing only uses valid data
            mask_before_valid = df_for_smoothing.index < first_valid_idx
            df_for_smoothing.loc[mask_before_valid, col] = pd.NA
        else:
            # If all values are zero or NaN, keep as NaN
            df_for_smoothing[col] = pd.NA
    
    # Apply smoothing
    # For fixed coins (like DYDX), smooth Price instead of MC to keep Q constant
    df_s = apply_smoothing(df_for_smoothing, smoothing)
    
    # Special handling for DYDX: if it's fixed, smooth Price and recalculate MC
    if "DYDX" in df_for_smoothing.columns and smoothing != "No smoothing":
        apr2 = pd.Timestamp("2025-04-02")
        if apr2 in df_for_smoothing.index:
            # Check if DYDX has fixed data (MC should be > 200M on April 4)
            apr4_check = pd.Timestamp("2025-04-04")
            if apr4_check in df_for_smoothing.index:
                apr4_mc_check = df_for_smoothing.loc[apr4_check, "DYDX"]
                if apr4_mc_check > 200_000_000:  # DYDX is fixed
                    # Load prices
                    import json
                    import os
                    path = os.path.join('cg_cache', 'dydx_365d_usd.json')
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            js = json.load(f)
                        if "prices" in js and js["prices"]:
                            df_prices = pd.DataFrame(js["prices"], columns=["ts", "price"])
                            df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
                            df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
                            prices_raw = df_prices.set_index("date")["price"].sort_index()
                            
                            # Align prices with df_for_smoothing index
                            prices_aligned = prices_raw.reindex(df_for_smoothing.index)
                            
                            # Smooth prices
                            prices_df = pd.DataFrame({"price": prices_aligned})
                            prices_smoothed_df = apply_smoothing(prices_df, smoothing)
                            prices_smoothed = prices_smoothed_df["price"]
                            
                            # Recalculate MC = Q_baseline * Price_smoothed for dates >= break_date
                            q_baseline = 415_347_669
                            break_date = apr2
                            
                            for dt in df_for_smoothing.index:
                                if dt >= break_date and dt in prices_smoothed.index:
                                    price_sm = prices_smoothed.loc[dt]
                                    if pd.notna(price_sm) and price_sm > 0:
                                        mc_recalc = q_baseline * price_sm
                                        df_s.loc[dt, "DYDX"] = mc_recalc
                            
                            logger.info(f"Fixed DYDX smoothing: Used Price smoothing to keep Q constant")

    # CRITICAL: Verify df_s has correct DYDX data before normalization
    if "DYDX" in df_s.columns:
        apr4_check = pd.Timestamp("2025-04-04")
        last_check = df_s.index[-1]
        if apr4_check in df_s.index:
            apr4_mc_check = df_s.loc[apr4_check, "DYDX"]
            last_mc_check = df_s.loc[last_check, "DYDX"]
            if apr4_mc_check < 200_000_000:
                logger.error(f"DYDX df_s has corrupted Apr4 MC={apr4_mc_check:,.0f}!")
                print(f"ERROR: df_s DYDX Apr4={apr4_mc_check:,.0f}, Last={last_mc_check:,.0f}")
            else:
                print(f"OK: df_s DYDX Apr4={apr4_mc_check:,.0f}, Last={last_mc_check:,.0f}")
    
    # Main data + axis type
    if view == "Normalized (Linear)":
        df_plot = normalize_start100(df_s)
        
        # CRITICAL: For DYDX, ALWAYS force correct normalization using Dec 25 as baseline
        if "DYDX" in df_s.columns:
            dydx_col = df_s["DYDX"]
            dec25 = pd.Timestamp("2024-12-25")
            if dec25 in dydx_col.index:
                baseline_mc = dydx_col.loc[dec25]
                if baseline_mc > 200_000_000:  # Valid baseline
                    # Force normalize using Dec 25 as baseline
                    dydx_normalized = (dydx_col / baseline_mc * 100)
                    # Set values before Dec 25 to NaN
                    dydx_normalized.loc[dydx_normalized.index < dec25] = pd.NA
                    # Preserve existing NaN
                    dydx_normalized[dydx_col.isna()] = pd.NA
                    df_plot["DYDX"] = dydx_normalized
                    logger.info(f"DYDX: Force normalized using Dec 25 baseline (MC={baseline_mc:,.0f})")
                    print(f"DYDX: Force normalized, last value={dydx_normalized.dropna().iloc[-1]:.2f}")
                else:
                    logger.error(f"DYDX: Dec 25 baseline is invalid (MC={baseline_mc:,.0f})")
            else:
                logger.error("DYDX: Dec 25 not found in df_s!")
        
        # Debug: Check DYDX normalized values and underlying MC
        if "DYDX" in df_plot.columns:
            dydx_norm = df_plot["DYDX"].dropna()
            if len(dydx_norm) > 0:
                first_norm = dydx_norm.iloc[0]
                last_norm = dydx_norm.iloc[-1]
                first_date = dydx_norm.index[0]
                last_date = dydx_norm.index[-1]
                # Check underlying MC values
                first_mc = df_s.loc[first_date, "DYDX"] if first_date in df_s.index else None
                last_mc = df_s.loc[last_date, "DYDX"] if last_date in df_s.index else None
                apr4 = pd.Timestamp("2025-04-04")
                apr4_mc = df_s.loc[apr4, "DYDX"] if apr4 in df_s.index else None
                apr4_norm = df_plot.loc[apr4, "DYDX"] if apr4 in df_plot.index else None
                # CRITICAL: Verify normalization is correct
                if first_mc and last_mc:
                    expected_last_norm = (last_mc / first_mc * 100)
                    if abs(last_norm - expected_last_norm) > 1.0:
                        logger.error(
                            f"DYDX NORMALIZATION ERROR: Last norm={last_norm:.2f} but expected={expected_last_norm:.2f} "
                            f"(Last MC={last_mc:,.0f}, First MC={first_mc:,.0f})"
                        )
                        print(f"ERROR: Normalization wrong! Last={last_norm:.2f}, Expected={expected_last_norm:.2f}")
                
                print(f"DEBUG CHART DYDX: First={first_date.strftime('%Y-%m-%d')} MC={first_mc:,.0f} Norm={first_norm:.2f}")
                print(f"DEBUG CHART DYDX: Last={last_date.strftime('%Y-%m-%d')} MC={last_mc:,.0f} Norm={last_norm:.2f}")
                logger.info(
                    f"DEBUG CHART DYDX: First={first_date.strftime('%Y-%m-%d')} MC={first_mc:,.0f} Norm={first_norm:.2f}, "
                    f"Apr4 MC={apr4_mc:,.0f if apr4_mc else 'N/A'} Norm={apr4_norm:.2f if apr4_norm else 'N/A'}, "
                    f"Last={last_date.strftime('%Y-%m-%d')} MC={last_mc:,.0f if last_mc else 'N/A'} Norm={last_norm:.2f}"
                )
        yaxis_title = "Index (100 = first value)"
        yaxis_type = "linear"
        normalized_view = True
    elif view == "Normalized (Log)":
        df_plot = normalize_start100(df_s)
        yaxis_title = "Index (100 = first value, log)"
        yaxis_type = "log"
        normalized_view = True
    else:
        df_plot = df_s
        # Debug: Check DYDX in Market Cap view
        if "DYDX" in df_plot.columns:
            apr4 = pd.Timestamp("2025-04-04")
            last_date = df_plot.index[-1]
            if apr4 in df_plot.index:
                logger.info(
                    f"DEBUG CHART DYDX (Market Cap view): "
                    f"Apr4 MC={df_plot.loc[apr4, 'DYDX']:,.0f}, "
                    f"Last MC={df_plot.loc[last_date, 'DYDX']:,.0f}"
                )
        yaxis_title = "Market Cap (USD, log)"
        yaxis_type = "log"
        normalized_view = False

    # USDT.D indexed series (only for normalized views)
    usdt_d_index = compute_usdt_d_index(df_s) if normalized_view else None

    fig = go.Figure()
    cur_order = order or symbols_for_view(group_filter(symbols_all, meta, group_choice), view)
    
    for sym in cur_order:
        # Skip if symbol doesn't exist in metadata
        if sym not in meta:
            continue
            
        cat, grp = meta.get(sym, ("", ""))

        if sym == DOM_SYM:
            if not normalized_view or usdt_d_index is None or usdt_d_index.dropna().empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=usdt_d_index.index,
                    y=usdt_d_index.values,
                    mode="lines",
                    name=f"{DOM_SYM} — {DOM_CAT}",
                    line=dict(color=color_for(sym), width=2, dash="dot"),
                    visible=True if sym in selected_set else "legendonly",
                    hovertemplate=(
                        f"<b>{DOM_SYM}</b> — {DOM_CAT}<br>"
                        f"Smoothing: {smoothing}<br>"
                        f"View: {view}<br>"
                        "Date: %{x}<br>"
                        "Index: %{y:.2f}<extra></extra>"
                    ),
                )
            )
            continue

        # Get data series - try df_plot first, then df_raw as fallback
        data_series = None
        
        # CRITICAL: For DYDX, ALWAYS use df_plot, never fallback
        if sym == "DYDX":
            if sym in df_plot.columns:
                data_series = df_plot[sym]
                if data_series.dropna().empty:
                    logger.error("DYDX is in df_plot but has no valid data!")
            else:
                logger.error("DYDX is NOT in df_plot! This should not happen.")
                # Force add it
                if sym in df_s.columns:
                    df_plot[sym] = normalize_start100(df_s[[sym]])[sym]
                    data_series = df_plot[sym]
                    logger.warning("Force-added DYDX to df_plot")
            
            # FINAL SAFETY: Always recalculate DYDX normalization to ensure it's correct
            if sym in df_s.columns and normalized_view:
                dec25 = pd.Timestamp("2024-12-25")
                if dec25 in df_s.index:
                    baseline_mc = df_s.loc[dec25, sym]
                    if baseline_mc > 200_000_000:
                        # Recalculate normalization
                        data_series_fixed = (df_s[sym] / baseline_mc * 100)
                        data_series_fixed.loc[data_series_fixed.index < dec25] = pd.NA
                        data_series_fixed[df_s[sym].isna()] = pd.NA
                        data_series = data_series_fixed
                        logger.info(f"DYDX: Final safety recalculation - baseline={baseline_mc:,.0f}")
                        print(f"DYDX: Final safety fix applied, last value={data_series.dropna().iloc[-1]:.2f if len(data_series.dropna()) > 0 else 'N/A'}")
        else:
            if sym in df_plot.columns:
                data_series = df_plot[sym]
                # Check if data is valid (not all NaN or zero)
                if data_series.dropna().empty or (data_series.dropna() == 0).all():
                    data_series = None  # Try fallback
        
        # Fallback to raw data if not in plot or empty
        # CRITICAL: DYDX should NEVER use fallback - it should always be in df_plot
        if sym == "DYDX" and data_series is None:
            logger.error("DYDX data_series is None! This should never happen!")
            # Last resort: create it from df_s
            if sym in df_s.columns:
                dec25 = pd.Timestamp("2024-12-25")
                if dec25 in df_s.index:
                    baseline = df_s.loc[dec25, sym]
                    data_series = (df_s[sym] / baseline * 100)
                    data_series.loc[data_series.index < dec25] = pd.NA
                    logger.warning("DYDX: Created data_series from df_s as last resort")
        
        # CRITICAL: For DYDX, ensure we use fixed data and correct normalization
        if data_series is None and sym in df_raw.columns:
            raw_col = df_raw[sym]
            if normalized_view:
                # Find first meaningful (non-zero, non-NaN) value
                # For DYDX, ensure we use the FIRST day (Dec 25), not April 4
                valid_mask = (raw_col != 0) & (~pd.isna(raw_col))
                if not valid_mask.any():
                    continue  # No valid data
                
                # For DYDX, force use of Dec 25 as baseline (not corrupted April 4)
                if sym == "DYDX":
                    dec25 = pd.Timestamp("2024-12-25")
                    if dec25 in raw_col.index and raw_col.loc[dec25] > 0:
                        first_valid_idx = dec25
                        first_valid_val = raw_col.loc[dec25]
                    else:
                        first_valid_idx = raw_col[valid_mask].index[0]
                        first_valid_val = raw_col.loc[first_valid_idx]
                else:
                    first_valid_idx = raw_col[valid_mask].index[0]
                    first_valid_val = raw_col.loc[first_valid_idx]
                
                # Verify first_valid_val is reasonable (for DYDX, should be ~713M, not ~10M)
                if sym == "DYDX" and first_valid_val < 200_000_000:
                    logger.warning(f"DYDX fallback: first_valid_val={first_valid_val:,.0f} is too small, using Dec 25")
                    dec25 = pd.Timestamp("2024-12-25")
                    if dec25 in raw_col.index and raw_col.loc[dec25] > 200_000_000:
                        first_valid_idx = dec25
                        first_valid_val = raw_col.loc[dec25]
                
                # Normalize using first valid value
                data_series = (raw_col / first_valid_val * 100)
                # Set values before first_valid_idx to NaN (so they don't plot)
                data_series.loc[data_series.index < first_valid_idx] = pd.NA
            else:
                data_series = raw_col
        
        if data_series is None:
            continue
        
        # Final check: ensure we have valid data to plot
        # Drop NaN values and also filter out any zeros that might have slipped through
        valid_data = data_series.dropna()
        if valid_data.empty:
            continue
        
        # Additional safety: remove any zeros that might be at the start
        # Find first non-zero value
        non_zero_mask = valid_data != 0
        if non_zero_mask.any():
            first_non_zero_idx = valid_data[non_zero_mask].index[0]
            # Only plot from first non-zero value onwards
            valid_data = valid_data.loc[valid_data.index >= first_non_zero_idx]
        
        if valid_data.empty:
            continue
        
        # FINAL SAFETY: For DYDX, always recalculate right before plotting
        if sym == "DYDX" and normalized_view and sym in df_s.columns:
            dec25 = pd.Timestamp("2024-12-25")
            if dec25 in df_s.index:
                baseline_mc = df_s.loc[dec25, sym]
                if baseline_mc > 200_000_000:
                    # Recalculate the entire series
                    data_series_final = (df_s[sym] / baseline_mc * 100)
                    data_series_final.loc[data_series_final.index < dec25] = pd.NA
                    data_series_final[df_s[sym].isna()] = pd.NA
                    # Re-process for plotting
                    valid_data_final = data_series_final.dropna()
                    if len(valid_data_final) > 0:
                        non_zero_final = valid_data_final != 0
                        if non_zero_final.any():
                            first_non_zero_final = valid_data_final[non_zero_final].index[0]
                            valid_data = valid_data_final.loc[valid_data_final.index >= first_non_zero_final]
                            logger.info(f"DYDX: Final pre-plot recalculation applied")
                            last_val_final = valid_data.iloc[-1] if len(valid_data) > 0 else None
                            print("=" * 60)
                            print(f"DYDX FINAL PRE-PLOT FIX APPLIED")
                            print(f"  Baseline MC: {baseline_mc:,.0f}")
                            print(f"  Last date: {valid_data.index[-1].strftime('%Y-%m-%d')}")
                            print(f"  Last normalized value: {last_val_final:.2f}")
                            print("=" * 60)
        
        # Debug: Log actual values being plotted for DYDX
        if sym == "DYDX":
            apr4 = pd.Timestamp("2025-04-04")
            last_date = valid_data.index[-1]
            apr4_val = valid_data.loc[apr4] if apr4 in valid_data.index else None
            last_val = valid_data.loc[last_date] if last_date in valid_data.index else None
            first_val = valid_data.iloc[0] if len(valid_data) > 0 else None
            first_date = valid_data.index[0] if len(valid_data) > 0 else None
            
            # CRITICAL: Verify values are correct
            if normalized_view and first_val and last_val:
                if abs(first_val - 100.0) > 1.0:
                    logger.error(f"DYDX: First value should be 100.0 but is {first_val:.2f}!")
                if last_val < 5.0 or last_val > 15.0:
                    logger.error(f"DYDX: Last value {last_val:.2f} seems wrong! Should be ~9.58")
                    # Force fix if wrong
                    if sym in df_s.columns:
                        dec25 = pd.Timestamp("2024-12-25")
                        if dec25 in df_s.index:
                            baseline = df_s.loc[dec25, sym]
                            last_mc = df_s.loc[last_date, sym]
                            expected_last = (last_mc / baseline * 100)
                            if abs(last_val - expected_last) > 1.0:
                                logger.error(f"DYDX: Recalculating - last={last_val:.2f}, expected={expected_last:.2f}")
                                # Recalculate the whole series
                                data_series_fixed = (df_s[sym] / baseline * 100)
                                data_series_fixed.loc[data_series_fixed.index < dec25] = pd.NA
                                valid_data = data_series_fixed.dropna()
                                if len(valid_data) > 0:
                                    valid_data = valid_data.loc[valid_data.index >= valid_data[valid_data != 0].index[0]]
                                    last_val = valid_data.iloc[-1]
                                    logger.warning(f"DYDX: Fixed! New last value={last_val:.2f}")
            
            print("=" * 60)
            print(f"PLOTTING DYDX TO CHART:")
            print(f"  View: {view}")
            print(f"  First: {first_date.strftime('%Y-%m-%d') if first_date else 'N/A'} = {first_val:.2f if first_val else 'N/A'}")
            print(f"  Apr 4: {apr4_val:.2f if apr4_val else 'N/A'}")
            print(f"  Last: {last_date.strftime('%Y-%m-%d') if last_date else 'N/A'} = {last_val:.2f if last_val else 'N/A'}")
            print(f"  Data points: {len(valid_data)}")
            print(f"  Last 3 values: {list(valid_data.iloc[-3:].values) if len(valid_data) >= 3 else 'N/A'}")
            print("=" * 60)
            logger.info(
                f"DEBUG PLOTTING DYDX: View={view}, "
                f"First={first_date.strftime('%Y-%m-%d') if first_date else 'N/A'}={first_val:.2f if first_val else 'N/A'}, "
                f"Apr4={'N/A' if apr4_val is None else (f'{apr4_val:.2f}' if normalized_view else f'{apr4_val:,.0f}')}, "
                f"Last={'N/A' if last_val is None else (f'{last_val:.2f}' if normalized_view else f'{last_val:,.0f}')}, "
                f"Data points={len(valid_data)}, Source={'df_plot' if sym in df_plot.columns else 'fallback'}"
            )
        
        # Only plot valid (non-NaN, non-zero) data points
        fig.add_trace(
            go.Scatter(
                x=valid_data.index,
                y=valid_data.values,
                mode="lines",
                name=f"{sym} — {cat}",
                line=dict(color=color_for(sym), width=2),
                visible=True if sym in selected_set else "legendonly",
                hovertemplate=(
                    f"<b>{sym}</b> — {cat}<br>"
                    f"Group: {grp}<br>"
                    f"Smoothing: {smoothing}<br>"
                    f"View: {view}<br>"
                    "Date: %{x}<br>"
                    + ("Index: %{y:.2f}" if normalized_view else "Market Cap: %{y:.3s} USD")
                    + "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=f"{view} | {smoothing} | Group: {group_choice}",
        xaxis_title="Date",
        yaxis=dict(title=yaxis_title, type=yaxis_type),
        hovermode="closest",
        legend=dict(
            x=1.02, y=1,
            xanchor="left", yanchor="top",
            font=dict(size=10),
        ),
        margin=dict(r=380, t=70),
        uirevision="keep",
    )
    return fig

# ---------- Correlation + Scatter ----------
@app.callback(
    Output("corr-output", "children"),
    Output("scatter", "figure"),
    Input("state", "data"),
    Input("selected", "data"),
    Input("order", "data"),
)
def corr_and_scatter(state, selected_syms, order):
    view = state["view"]
    smoothing = state["smoothing"]
    corr_mode = state.get("corr_mode", "off")

    # Only consider symbols that are currently traceable in this view
    allowed = set(order or [])
    sel = [s for s in (selected_syms or []) if s in allowed]

    # Build an empty/placeholder scatter
    empty_fig = go.Figure()
    empty_fig.update_layout(
        xaxis_title="Returns of A",
        yaxis_title="Returns of B",
        margin=dict(t=30, r=30, l=60, b=50),
        annotations=[dict(text="Select exactly 2 symbols to see the returns scatter.", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)],
    )

    if corr_mode == "off":
        return "Correlation: Off", empty_fig

    # Need exactly 2 selected
    if len(sel) != 2:
        return f"Select exactly 2 symbols (currently {len(sel)}).", empty_fig

    a, b = sel[0], sel[1]

    df_s = apply_smoothing(df_raw, smoothing)

    sA = series_for_symbol(a, df_s, view)
    sB = series_for_symbol(b, df_s, view)
    if sA is None or sB is None:
        return f"Cannot compute series for {a} or {b} in this view.", empty_fig

    # Align by date (inner join so we only use overlapping history).
    # Because series_for_symbol masks everything before each coin's first
    # meaningful value, this effectively starts from the *later* coin's
    # launch date (e.g. SKY) when computing correlation.
    df = pd.concat([sA.rename(a), sB.rename(b)], axis=1, join="inner").dropna()
    # Allow shorter histories (e.g. newer tokens), but require a configurable
    # minimum number of overlapping daily points so the correlation is at least
    # somewhat meaningful.
    if df.shape[0] < MIN_CORR_DAYS:
        return (
            f"Not enough overlapping data for {a} and {b} "
            f"(need ≥{MIN_CORR_DAYS} days, got {df.shape[0]}).",
            empty_fig,
        )

    # Correlation + slope (beta) calculation
    rets = df.pct_change().dropna()

    # Regression slope: how much B tends to move (in %) when A moves 1%.
    beta = None
    if not rets.empty and rets[a].var() > 0:
        beta = rets[b].cov(rets[a]) / rets[a].var()

    if corr_mode == "returns":
        corr = rets[a].corr(rets[b])
        scat = create_returns_scatter(rets, a, b, corr, "returns")
        if beta is not None:
            implied_move = beta * 10  # B's move if A moves +10%
            text = (
                f"Correlation (daily returns) — {a} vs {b}: {corr:.3f} | "
                f"beta={beta:.2f} (if {a} +10%, {b} ≈ {implied_move:+.1f}%)"
            )
        else:
            text = f"Correlation (daily returns) — {a} vs {b}: {corr:.3f}"
        return text, scat

    # levels mode: correlate indexed levels (start=100)
    idx = df / df.iloc[0] * 100
    corr = idx[a].corr(idx[b])

    # Scatter still uses returns (as requested) so it stays "visually obvious"
    scat = create_returns_scatter(rets, a, b, corr, "levels")
    if beta is not None:
        implied_move = beta * 10
        text = (
            f"Correlation (indexed levels) — {a} vs {b}: {corr:.3f} | "
            f"beta={beta:.2f} (if {a} +10%, {b} ≈ {implied_move:+.1f}%)"
        )
    else:
        text = f"Correlation (indexed levels) — {a} vs {b}: {corr:.3f}"
    return text, scat

# -------------------- Run --------------------
if __name__ == "__main__":
    startup_msg = "Starting Dash… open http://127.0.0.1:8050/"
    logger.info(startup_msg)
    logger.info(f"Log file: {LOG_FILE}")
    app.run(debug=False)
