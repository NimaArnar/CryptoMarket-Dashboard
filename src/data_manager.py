"""Data manager for loading and managing market cap data."""
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from src.config import BASE_SLEEP, CACHE_DIR, MAX_CONCURRENT, USE_ASYNC
from src.constants import COINS, DOM_SYM, DOM_CAT, DOM_GRP
from src.data import fetch_all_coins, fetch_market_caps_retry
from src.utils import check_aiohttp, setup_logger

logger = setup_logger(__name__)


class DataManager:
    """Manages market cap data loading, cleaning, and export."""
    
    def __init__(self):
        self.series: Dict[str, pd.Series] = {}
        self.meta: Dict[str, Tuple[str, str]] = {}
        self.failed: List[Tuple[str, str, str]] = []
        self.df_raw: pd.DataFrame = None
        self.symbols_all: List[str] = []
        self.coin_status: Dict = {}
    
    def load_all_data(self) -> None:
        """Load all coin data from CoinGecko API."""
        logger.info(f"Starting data fetch (async={USE_ASYNC}, max_concurrent={MAX_CONCURRENT})")
        
        if USE_ASYNC and check_aiohttp():
            self._load_async()
        else:
            if USE_ASYNC and not check_aiohttp():
                logger.warning("Async fetching requested but aiohttp not installed. Falling back to sequential.")
            self._load_sequential()
        
        self._process_results()
        self._export_to_excel()
        self._create_dataframe()
    
    def _load_async(self) -> None:
        """Load data using async parallel fetching."""
        try:
            all_results = fetch_all_coins(COINS, MAX_CONCURRENT)
            
            for coin_id, sym, cat, grp in COINS:
                if sym in all_results:
                    self.series[sym] = all_results[sym]
                    self.meta[sym] = (cat, grp)
                    logger.info(f"✅ Successfully loaded {sym}")
                else:
                    self._handle_missing_coin(coin_id, sym, cat, grp, "Not found in async results")
        except Exception as e:
            logger.error(f"Async fetch failed: {e}, falling back to sequential")
            self._load_sequential()
    
    def _load_sequential(self) -> None:
        """Load data sequentially."""
        logger.info("Using sequential fetching")
        for coin_id, sym, cat, grp in COINS:
            try:
                logger.info(f"Fetching {sym} ({coin_id})")
                self.series[sym] = fetch_market_caps_retry(coin_id)
                self.meta[sym] = (cat, grp)
                time.sleep(BASE_SLEEP)
            except Exception as e:
                self._handle_missing_coin(coin_id, sym, cat, grp, str(e))
    
    def _handle_missing_coin(self, coin_id: str, sym: str, cat: str, grp: str, error: str) -> None:
        """Handle missing coin, with special fallback for SKY."""
        if coin_id == "sky":
            try:
                logger.info("SKY failed; falling back to maker (MKR) but labeling as SKY.")
                self.series[sym] = fetch_market_caps_retry("maker")
                self.meta[sym] = (cat, grp)
                if not USE_ASYNC:
                    time.sleep(BASE_SLEEP)
            except Exception as e2:
                self.failed.append((coin_id, sym, str(e2)))
                logger.error(f"SKY fallback failed: {e2}")
        else:
            self.failed.append((coin_id, sym, error))
            logger.error(f"Failed to fetch {sym} ({coin_id}): {error}")
    
    def _process_results(self) -> None:
        """Process loading results and create coin status."""
        if not self.series:
            raise RuntimeError("No coin data was successfully fetched. Cannot create dashboard.")
        
        if self.failed:
            logger.warning(f"FAILED ({len(self.failed)} coins):")
            for coin_id, sym, err in self.failed:
                logger.warning(f"- {sym} ({coin_id}) -> {err}")
        
        successfully_fetched = set(self.series.keys())
        expected_coins = {sym for _, sym, _, _ in COINS}
        missing_coins = expected_coins - successfully_fetched
        
        if missing_coins:
            logger.warning(f"⚠️  WARNING: {len(missing_coins)} coin(s) not available in chart:")
            for sym in sorted(missing_coins):
                logger.warning(f"  - {sym}")
        
        logger.info(
            f"\n✅ Successfully loaded {len(successfully_fetched)} coin(s): "
            f"{', '.join(sorted(successfully_fetched))}"
        )
        
        self.coin_status = {
            "available": sorted(successfully_fetched),
            "missing": sorted(missing_coins) if missing_coins else [],
            "total_expected": len(expected_coins),
            "total_loaded": len(successfully_fetched)
        }
    
    def _export_to_excel(self) -> None:
        """Export market cap data to Excel files."""
        from src.config import EXPORT_DIR
        
        try:
            for sym, s in self.series.items():
                try:
                    df_export = s.to_frame(name="market_cap_usd")
                    export_path = EXPORT_DIR / f"{sym}_market_cap.xlsx"
                    df_export.to_excel(export_path, sheet_name="market_cap")
                except Exception as e:
                    logger.warning(f"⚠️  Could not export Excel for {sym}: {e}")
            
            logger.info(f"\n📁 Exported market cap data for {len(self.series)} coin(s) to: {EXPORT_DIR}")
        except Exception as e:
            logger.error(f"⚠️  Failed to export market cap Excel files: {e}")
    
    def _create_dataframe(self) -> None:
        """Create DataFrame from series and add pseudo series."""
        self.df_raw = pd.DataFrame(self.series).sort_index().ffill()
        
        # Add pseudo series (USDT.D)
        self.meta[DOM_SYM] = (DOM_CAT, DOM_GRP)
        self.symbols_all = list(self.df_raw.columns) + [DOM_SYM]

