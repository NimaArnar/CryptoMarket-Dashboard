"""Data fetching from CoinGecko API with caching and retry logic."""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from src.config import (
    BASE_SLEEP,
    BACKOFF_MULTIPLIER,
    CACHE_DIR,
    CACHE_EXPIRY_HOURS,
    COINGECKO_API_BASE,
    COINGECKO_API_KEY,
    DAYS_HISTORY,
    MAX_RETRIES,
    USE_ASYNC,
    VS_CURRENCY,
    WAIT_TIME,
)
from src.data.cleaner import clean_market_cap_data
from src.utils import setup_logger

logger = setup_logger(__name__)


def cache_path(coin_id: str) -> Path:
    """Get cache file path for a coin."""
    return CACHE_DIR / f"{coin_id}_{DAYS_HISTORY}d_{VS_CURRENCY}.json"


def fetch_market_caps_retry(coin_id: str) -> pd.Series:
    """Fetch market cap data with retry logic and API key support."""
    cp = cache_path(coin_id)
    
    # Check if cache exists and is not expired
    if cp.exists():
        cache_age = time.time() - cp.stat().st_mtime
        cache_age_hours = cache_age / 3600
        
        if cache_age_hours < CACHE_EXPIRY_HOURS:
            logger.debug(f"{coin_id}: Using cached data ({cache_age_hours:.1f}h old)")
            with open(cp, "r", encoding="utf-8") as f:
                js = json.load(f)
            return clean_market_cap_data(js, coin_id)
        else:
            logger.info(f"{coin_id}: Cache expired ({cache_age_hours:.1f}h old), fetching fresh data...")
            cp.unlink()

    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": VS_CURRENCY, "days": DAYS_HISTORY, "interval": "daily"}
    
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY

    cur_wait = WAIT_TIME
    last_err = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            
            logger.debug(f"{coin_id}: API request (attempt {attempt}/{MAX_RETRIES}) - Status: {r.status_code}")

            if r.status_code in (429, 500, 502, 503, 504):
                logger.warning(f"{coin_id}: HTTP {r.status_code} (try {attempt}/{MAX_RETRIES}) -> sleep {cur_wait:.1f}s")
                time.sleep(cur_wait)
                cur_wait *= BACKOFF_MULTIPLIER
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
            return clean_market_cap_data(js, coin_id)

        except requests.exceptions.RequestException as e:
            last_err = e
            logger.error(f"{coin_id}: Request error (try {attempt}/{MAX_RETRIES}) -> {e} | sleep {cur_wait:.1f}s")
            time.sleep(cur_wait)
            cur_wait *= BACKOFF_MULTIPLIER
        except Exception as e:
            last_err = e
            logger.error(f"{coin_id}: Unexpected error (try {attempt}/{MAX_RETRIES}) -> {e} | sleep {cur_wait:.1f}s")
            time.sleep(cur_wait)
            cur_wait *= BACKOFF_MULTIPLIER

    error_msg = f"{coin_id}: failed after {MAX_RETRIES} retries. last_err={last_err}"
    logger.error(error_msg)
    raise RuntimeError(error_msg)


async def fetch_market_caps_async(session: aiohttp.ClientSession, coin_id: str) -> Tuple[str, pd.Series]:
    """Async version of fetch_market_caps_retry for parallel fetching."""
    cp = cache_path(coin_id)
    
    # Check if cache exists and is not expired
    if cp.exists():
        cache_age = time.time() - cp.stat().st_mtime
        cache_age_hours = cache_age / 3600
        
        if cache_age_hours < CACHE_EXPIRY_HOURS:
            logger.debug(f"{coin_id}: Using cached data ({cache_age_hours:.1f}h old)")
            with open(cp, "r", encoding="utf-8") as f:
                js = json.load(f)
            return coin_id, clean_market_cap_data(js, coin_id)
        else:
            logger.info(f"{coin_id}: Cache expired ({cache_age_hours:.1f}h old), fetching fresh data...")
            cp.unlink()

    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": VS_CURRENCY, "days": DAYS_HISTORY, "interval": "daily"}
    
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY

    cur_wait = WAIT_TIME
    last_err = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
                logger.debug(f"{coin_id}: API request (attempt {attempt}/{MAX_RETRIES}) - Status: {r.status}")

                if r.status in (429, 500, 502, 503, 504):
                    logger.warning(f"{coin_id}: HTTP {r.status} (try {attempt}/{MAX_RETRIES}) -> sleep {cur_wait:.1f}s")
                    await asyncio.sleep(cur_wait)
                    cur_wait *= BACKOFF_MULTIPLIER
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
            return coin_id, clean_market_cap_data(js, coin_id)

        except asyncio.TimeoutError as e:
            last_err = e
            logger.error(f"{coin_id}: Timeout error (try {attempt}/{MAX_RETRIES}) -> {e} | sleep {cur_wait:.1f}s")
            await asyncio.sleep(cur_wait)
            cur_wait *= BACKOFF_MULTIPLIER
        except Exception as e:
            last_err = e
            logger.error(f"{coin_id}: Error (try {attempt}/{MAX_RETRIES}) -> {e} | sleep {cur_wait:.1f}s")
            await asyncio.sleep(cur_wait)
            cur_wait *= BACKOFF_MULTIPLIER

    error_msg = f"{coin_id}: failed after {MAX_RETRIES} retries. last_err={last_err}"
    logger.error(error_msg)
    raise RuntimeError(error_msg)


async def fetch_all_coins_async(coin_list: List[Tuple[str, str, str, str]]) -> Dict[str, pd.Series]:
    """Fetch all coins in parallel using async requests."""
    if not HAS_AIOHTTP:
        raise RuntimeError("aiohttp not installed - cannot use async fetching")
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_market_caps_async(session, coin_id) for coin_id, _, _, _ in coin_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        series_dict = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Async fetch failed: {result}")
                continue
            coin_id, series_data = result
            # Find symbol for this coin_id
            for cid, sym, _, _ in coin_list:
                if cid == coin_id:
                    series_dict[sym] = series_data
                    break
        
        return series_dict


def fetch_all_coins(coin_list: List[Tuple[str, str, str, str]], max_concurrent: int = 5) -> Dict[str, pd.Series]:
    """
    Fetch all coins, using async if available, otherwise sequential.
    
    Args:
        coin_list: List of (coin_id, symbol, category, group) tuples
        max_concurrent: Maximum concurrent requests (for async mode)
    
    Returns:
        Dictionary mapping symbols to market cap Series
    """
    if USE_ASYNC and HAS_AIOHTTP:
        # Process in batches to respect rate limits
        coin_batches = [coin_list[i:i + max_concurrent] for i in range(0, len(coin_list), max_concurrent)]
        all_results = {}
        
        for batch_idx, batch in enumerate(coin_batches):
            logger.info(f"Fetching batch {batch_idx + 1}/{len(coin_batches)} ({len(batch)} coins)")
            batch_results = asyncio.run(fetch_all_coins_async(batch))
            all_results.update(batch_results)
            
            # Small delay between batches to avoid rate limits
            if batch_idx < len(coin_batches) - 1:
                time.sleep(BASE_SLEEP * 2)
        
        return all_results
    else:
        # Sequential fetching
        series_dict = {}
        for coin_id, sym, _, _ in coin_list:
            try:
                logger.info(f"Fetching {sym} ({coin_id})")
                series_dict[sym] = fetch_market_caps_retry(coin_id)
                time.sleep(BASE_SLEEP)
            except Exception as e:
                logger.error(f"Failed to fetch {sym} ({coin_id}): {e}")
        
        return series_dict

