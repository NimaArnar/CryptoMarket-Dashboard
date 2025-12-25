"""Data cleaning and Q fix logic for corrupted market cap data."""
import pandas as pd
from typing import Dict, Optional

from src.constants import (
    MIN_MARKET_CAP_FOR_VALID,
    Q_DROP_THRESHOLD,
    PRICE_DROP_THRESHOLD,
)
from src.utils import setup_logger

logger = setup_logger(__name__)


def clean_market_cap_data(api_response: Dict, coin_id: str = "") -> pd.Series:
    """
    Parse and clean market cap data from CoinGecko API response.
    
    Automatically detects and fixes corrupted circulating supply data by:
    1. Calculating implied supply (Q = Market Cap / Price)
    2. Detecting abnormal supply drops that don't match price movements
    3. Using the last correct Q value before corruption as baseline
    4. Recomputing market cap as: MC_fixed = Q_baseline × Price
    
    Args:
        api_response: JSON response from CoinGecko API
        coin_id: Coin identifier for logging
    
    Returns:
        Cleaned market cap Series with date index
    """
    if "market_caps" not in api_response or not api_response["market_caps"]:
        raise ValueError("Invalid API response: missing or empty market_caps")
    
    # Extract prices for validation
    prices = None
    if "prices" in api_response and api_response["prices"]:
        df_prices = pd.DataFrame(api_response["prices"], columns=["ts", "price"])
        df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
        df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
        prices = df_prices.set_index("date")["price"].sort_index()
    
    # Extract market caps
    df = pd.DataFrame(api_response["market_caps"], columns=["ts", "market_cap"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.floor("D")
    df = df.sort_values("ts").groupby("date", as_index=False).last()
    series = df.set_index("date")["market_cap"].sort_index()
    
    # Apply Q fix if prices are available
    if prices is not None and len(prices) > 0 and len(series) > 0:
        series = _apply_q_fix(series, prices, coin_id)
    
    return series


def _apply_q_fix(series: pd.Series, prices: pd.Series, coin_id: str) -> pd.Series:
    """
    Apply Q fix to corrupted market cap data.
    
    Detects when implied supply (Q) drops abnormally and fixes it by
    recomputing MC using the last correct Q value.
    """
    common_dates = series.index.intersection(prices.index)
    if len(common_dates) < 20:
        return series  # Not enough data for Q fix
    
    mc_aligned = series.loc[common_dates]
    price_aligned = prices.loc[common_dates]
    
    # Calculate implied supply Q = MC / Price
    q_implied = mc_aligned / price_aligned
    
    # Day-to-day moves
    mc_pct = mc_aligned.pct_change()
    price_pct = price_aligned.pct_change()
    q_pct = q_implied.pct_change()
    
    # Detect abnormal Q drops (≥30% drop in Q while price doesn't drop similarly)
    q_drop_mask = (q_pct <= Q_DROP_THRESHOLD) & (price_pct > PRICE_DROP_THRESHOLD)
    q_drop_idx = q_drop_mask[q_drop_mask].index
    
    if len(q_drop_idx) == 0:
        return series  # No corruption detected
    
    # Find break date (2 days before the drop to catch gradual decline)
    drop_date = q_drop_idx[0]
    drop_date_pos = mc_aligned.index.get_loc(drop_date)
    
    if drop_date_pos >= 2:
        break_date = mc_aligned.index[drop_date_pos - 2]
    elif drop_date_pos >= 1:
        break_date = mc_aligned.index[drop_date_pos - 1]
    else:
        break_date = drop_date
    
    # Get history before break to find last correct Q
    history_mask = mc_aligned.index < break_date
    history_idx = mc_aligned.index[history_mask]
    
    if len(history_idx) < 10:
        return series  # Not enough history
    
    mc_hist = mc_aligned.loc[history_idx]
    price_hist = price_aligned.loc[history_idx]
    
    valid_hist = (mc_hist > 0) & (price_hist > 0)
    if not valid_hist.any():
        return series
    
    q_hist = (mc_hist[valid_hist] / price_hist[valid_hist])
    # Use LAST correct Q value (not mean) - most recent valid supply
    q_baseline = q_hist.iloc[-1]
    
    if q_baseline <= 0:
        return series
    
    # Apply fix: recompute MC from break_date onward
    series_cleaned = series.copy()
    fixed_samples = []
    
    all_future_dates = series_cleaned.index[series_cleaned.index >= break_date]
    for dt in all_future_dates:
        if dt not in prices.index:
            continue
        
        price_dt = prices.loc[dt]
        if not pd.notna(price_dt) or price_dt <= 0:
            continue
        
        mc_orig = series_cleaned.loc[dt]
        mc_fixed = float(q_baseline * price_dt)
        
        # Always apply the fix to ensure Q remains constant
        series_cleaned.loc[dt] = mc_fixed
        
        if len(fixed_samples) < 5:
            fixed_samples.append(
                f"{dt.strftime('%Y-%m-%d')}: MC {mc_orig:,.0f}→{mc_fixed:,.0f}"
            )
    
    # Verify Q is constant after fix
    if len(all_future_dates) > 0:
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
            f"{coin_id or 'UNKNOWN'}: Detected corrupted supply on "
            f"{break_date.strftime('%Y-%m-%d')} "
            f"(Q drop={q_pct.loc[break_date]:+.1%}, price change={price_pct.loc[break_date]:+.1%}). "
            f"Using fixed Q_baseline={q_baseline:,.0f} (last correct Q before {break_date.strftime('%Y-%m-%d')}). "
            f"Recomputing MC as Q_baseline*Price from {break_date.strftime('%Y-%m-%d')} onward. "
            f"Samples: {'; '.join(fixed_samples)}"
        )
    
    return series_cleaned


def find_dydx_baseline_date(series: pd.Series) -> tuple[Optional[pd.Timestamp], Optional[float]]:
    """
    Find the baseline date and value for DYDX normalization.
    
    Looks for Dec 25, 2024, or the closest valid date within 3 days.
    This is used to ensure DYDX normalization uses the correct baseline
    instead of corrupted April 4 data.
    
    Args:
        series: Market cap Series with date index
    
    Returns:
        Tuple of (baseline_date, baseline_value) or (None, None) if not found
    """
    from datetime import timedelta
    
    dec25 = pd.Timestamp("2024-12-25")
    
    # Try Dec 25 first
    if dec25 in series.index:
        val = series.loc[dec25]
        if pd.notna(val) and val > MIN_MARKET_CAP_FOR_VALID:
            return dec25, val
    
    # Try dates around Dec 25 (Dec 24-27)
    for offset in [1, -1, 2, -2, 3]:
        try_date = dec25 + pd.Timedelta(days=offset)
        if try_date in series.index:
            val = series.loc[try_date]
            if pd.notna(val) and val > MIN_MARKET_CAP_FOR_VALID:
                return try_date, val
    
    # If still not found, use first valid date after Dec 25
    valid_mask = (series != 0) & (~pd.isna(series)) & (series.index >= dec25)
    if valid_mask.any():
        baseline_date = series[valid_mask].index[0]
        baseline_val = series.loc[baseline_date]
        if baseline_val > MIN_MARKET_CAP_FOR_VALID:
            return baseline_date, baseline_val
    
    return None, None

