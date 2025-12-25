"""Chart building utilities for visualization."""
import pandas as pd
from typing import Optional

import plotly.graph_objects as go

from src.constants import DOM_SYM


def compute_usdt_d_index(df_smoothed: pd.DataFrame) -> Optional[pd.Series]:
    """
    Compute USDT dominance index.
    
    Calculates USDT as percentage of total market cap, normalized to start at 100.
    
    Args:
        df_smoothed: DataFrame with smoothed market cap data
    
    Returns:
        USDT dominance index Series or None if USDT not available
    """
    if "USDT" not in df_smoothed.columns:
        return None
    
    total_est = df_smoothed.sum(axis=1)
    if (total_est == 0).any():
        return None
    
    usdt_d_pct = (df_smoothed["USDT"] / total_est) * 100.0
    # Normalize to start at 100
    s2 = usdt_d_pct.dropna()
    if s2.empty:
        return usdt_d_pct
    first = s2.iloc[0]
    if first == 0:
        return usdt_d_pct
    return (usdt_d_pct / first) * 100


def series_for_symbol(
    symbol: str, df_smoothed: pd.DataFrame, view: str
) -> Optional[pd.Series]:
    """
    Get series for a symbol, handling missing data before first valid point.
    
    For coins that start trading part-way through history, everything before
    the first meaningful value is treated as missing. This ensures correlation
    is computed starting from the later coin's true start date.
    
    Args:
        symbol: Coin symbol
        df_smoothed: Smoothed DataFrame
        view: View type (affects USDT.D handling)
    
    Returns:
        Series for the symbol or None if not available
    """
    if symbol == DOM_SYM:
        if view == "Market Cap (Log)":
            return None
        return compute_usdt_d_index(df_smoothed)
    
    if symbol in df_smoothed.columns:
        col = df_smoothed[symbol].copy()
        
        # Find first meaningful (non-zero, non-NaN) value
        valid_mask = (col != 0) & (~pd.isna(col))
        if not valid_mask.any():
            return None
        
        first_valid_idx = col[valid_mask].index[0]
        
        # Treat everything before first valid point as missing
        col.loc[col.index < first_valid_idx] = pd.NA
        return col
    
    return None


def create_returns_scatter(
    rets: pd.DataFrame, symbol_a: str, symbol_b: str, corr: float, corr_type: str = "returns"
) -> go.Figure:
    """
    Create a scatter plot of returns with correlation in title.
    
    Args:
        rets: DataFrame with returns data
        symbol_a: First symbol
        symbol_b: Second symbol
        corr: Correlation value
        corr_type: Type of correlation ("returns" or "levels")
    
    Returns:
        Plotly Figure with scatter plot
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=rets[symbol_a],
            y=rets[symbol_b],
            mode="markers",
            name=f"{symbol_a} vs {symbol_b}",
            marker=dict(size=6, opacity=0.6),
            hovertemplate=(
                f"<b>{symbol_a} return</b>: %{{x:.4f}}<br>"
                f"<b>{symbol_b} return</b>: %{{y:.4f}}<extra></extra>"
            )
        )
    )
    
    corr_label = "corr" if corr_type == "returns" else "levels corr"
    fig.update_layout(
        title=f"Returns scatter — {symbol_a} vs {symbol_b} | {corr_label}={corr:.3f}",
        xaxis_title=f"{symbol_a} daily return",
        yaxis_title=f"{symbol_b} daily return",
        margin=dict(t=40, r=30, l=60, b=50),
    )
    
    return fig

