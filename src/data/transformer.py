"""Data transformation: smoothing and normalization."""
import pandas as pd
from typing import Dict, List, Optional

from src.constants import DOM_SYM, MIN_MARKET_CAP_FOR_VALID
from src.data.cleaner import find_dydx_baseline_date
from src.utils import setup_logger

logger = setup_logger(__name__)


def apply_smoothing(df: pd.DataFrame, smoothing: str) -> pd.DataFrame:
    """
    Apply smoothing to DataFrame, preserving NaN values.
    
    NaN values represent missing/zero data before first valid point
    and should remain NaN after smoothing.
    
    Args:
        df: DataFrame with date index
        smoothing: Smoothing method ("No smoothing", "7D SMA", "14D EMA", "30D SMA")
    
    Returns:
        Smoothed DataFrame with same index
    """
    if smoothing == "No smoothing":
        return df
    
    if smoothing == "7D SMA":
        result = df.rolling(7, min_periods=1).mean()
        result[df.isna()] = pd.NA
        return result
    
    if smoothing == "14D EMA":
        result = df.ewm(span=14, adjust=False, ignore_na=True).mean()
        result[df.isna()] = pd.NA
        return result
    
    if smoothing == "30D SMA":
        result = df.rolling(30, min_periods=1).mean()
        result[df.isna()] = pd.NA
        return result
    
    raise ValueError(f"Unknown smoothing: {smoothing}")


def normalize_start100(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize each column to start at 100, using first meaningful value.
    
    For DYDX, uses Dec 25, 2024 (or nearby date) as baseline instead of
    corrupted April 4 data.
    
    Args:
        df: DataFrame with date index
    
    Returns:
        Normalized DataFrame where each column starts at 100
    """
    out = pd.DataFrame(index=df.index)
    
    for col in df.columns:
        col_data = df[col]
        
        # Find first meaningful value (non-zero, non-NaN)
        non_nan_mask = ~pd.isna(col_data)
        if not non_nan_mask.any():
            out[col] = pd.Series(index=df.index, dtype=float)
            continue
        
        non_nan_data = col_data[non_nan_mask]
        non_zero_mask = non_nan_data != 0
        if not non_zero_mask.any():
            out[col] = pd.Series(index=df.index, dtype=float)
            continue
        
        first_valid_idx = non_nan_data[non_zero_mask].index[0]
        first_valid_val = col_data.loc[first_valid_idx]
        
        # Special handling for DYDX: use Dec 25 (or nearby) as baseline
        if col == "DYDX":
            baseline_date, baseline_val = find_dydx_baseline_date(col_data)
            if baseline_date is not None and baseline_val is not None:
                first_valid_idx = baseline_date
                first_valid_val = baseline_val
                logger.info(
                    f"DYDX normalization: Using {baseline_date.strftime('%Y-%m-%d')} "
                    f"as baseline (MC={first_valid_val:,.0f})"
                )
            else:
                logger.warning(
                    "DYDX normalization: Could not find valid baseline date, "
                    "using auto-detected first_valid_idx"
                )
        
        # Normalize using first valid value
        normalized = (col_data / first_valid_val * 100)
        
        # Set values before first_valid_idx to NaN
        normalized.loc[normalized.index < first_valid_idx] = pd.NA
        
        # Preserve existing NaN values
        normalized[col_data.isna()] = pd.NA
        
        out[col] = normalized
    
    return out


def normalize_series_start100(series: pd.Series) -> pd.Series:
    """Normalize a Series to start at 100."""
    s2 = series.dropna()
    if s2.empty:
        return series
    first = s2.iloc[0]
    if first == 0:
        return series
    return (series / first) * 100


def group_filter(symbols: List[str], meta: Dict, group_choice: str) -> List[str]:
    """
    Filter symbols by group.
    
    Args:
        symbols: List of all symbols
        meta: Metadata dict mapping symbol to (category, group)
        group_choice: Group to filter by
    
    Returns:
        Filtered list of symbols
    """
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


def symbols_for_view(group_syms: List[str], view: str) -> List[str]:
    """
    Filter symbols based on view type.
    
    USDT.D doesn't belong on market cap view, so remove it.
    """
    if view == "Market Cap (Log)":
        return [s for s in group_syms if s != DOM_SYM]
    return group_syms

