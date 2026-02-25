"""Commodity price helpers (e.g. Gold XAU, Silver XAG, Copper XCU) using Yahoo Finance."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from src.utils import setup_logger

logger = setup_logger(__name__)

# Map our logical symbols to Yahoo Finance tickers
YAHOO_TICKERS = {
    "XAU": "GC=F",  # Gold futures (COMEX)
    "XAG": "SI=F",  # Silver futures (COMEX)
    "XCU": "HG=F",  # Copper futures (COMEX)
}


def fetch_latest_commodity_price(symbol: str) -> Optional[float]:
    """
    Fetch latest daily close price (USD) for a commodity symbol.

    Uses Yahoo Finance futures tickers as a proxy for spot:
    - XAU -> GC=F (gold)
    - XAG -> SI=F (silver)
    - XCU -> HG=F (copper)
    """
    sym = symbol.upper()
    ticker = YAHOO_TICKERS.get(sym)
    if not ticker:
        logger.warning(f"Unknown commodity symbol for Yahoo Finance: {symbol}")
        return None

    try:
        # Get a few days of daily data to ensure we have the latest close
        data = yf.download(ticker, period="5d", interval="1d", progress=False)
        if data.empty or "Close" not in data.columns:
            logger.warning(f"No price data returned for {symbol} ({ticker})")
            return None

        # Use the last available close
        close_series = data["Close"].dropna()
        if close_series.empty:
            logger.warning(f"Empty close series for {symbol} ({ticker})")
            return None

        latest_price = float(close_series.iloc[-1])
        logger.info(f"Latest {symbol} price (from {ticker}): {latest_price}")
        return latest_price
    except Exception as e:
        logger.error(f"Failed to fetch commodity price for {symbol} ({ticker}): {e}")
        return None

