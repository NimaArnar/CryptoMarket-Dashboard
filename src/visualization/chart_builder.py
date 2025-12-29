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
    data: pd.DataFrame, symbol_a: str, symbol_b: str, corr: float, corr_type: str = "returns"
) -> go.Figure:
    """
    Create a scatter plot of returns or indexed levels with correlation in title.
    
    Args:
        data: DataFrame with returns data (for corr_type="returns") or indexed levels (for corr_type="levels")
        symbol_a: First symbol
        symbol_b: Second symbol
        corr: Correlation value
        corr_type: Type of correlation ("returns" or "levels")
    
    Returns:
        Plotly Figure with scatter plot
    """
    fig = go.Figure()
    
    if corr_type == "returns":
        # Returns mode: show daily returns
        fig.add_trace(
            go.Scatter(
                x=data[symbol_a],
                y=data[symbol_b],
                mode="markers",
                name=f"{symbol_a} vs {symbol_b}",
                marker=dict(size=6, opacity=0.6),
                hovertemplate=(
                    f"<b>{symbol_a} return</b>: %{{x:.2%}}<br>"
                    f"<b>{symbol_b} return</b>: %{{y:.2%}}<extra></extra>"
                )
            )
        )
        corr_label = "corr"
        title_text = f"Returns scatter — {symbol_a} vs {symbol_b} | {corr_label}={corr*100:.1f}%"
        xaxis_title = f"{symbol_a} daily return (%)"
        yaxis_title = f"{symbol_b} daily return (%)"
        xaxis_format = ".1%"
        yaxis_format = ".1%"
    else:
        # Levels mode: show indexed levels
        fig.add_trace(
            go.Scatter(
                x=data[symbol_a],
                y=data[symbol_b],
                mode="markers",
                name=f"{symbol_a} vs {symbol_b}",
                marker=dict(size=6, opacity=0.6),
                hovertemplate=(
                    f"<b>{symbol_a} index</b>: %{{x:.1f}}<br>"
                    f"<b>{symbol_b} index</b>: %{{y:.1f}}<extra></extra>"
                )
            )
        )
        corr_label = "levels corr"
        title_text = f"Levels scatter — {symbol_a} vs {symbol_b} | {corr_label}={corr*100:.1f}%"
        xaxis_title = f"{symbol_a} indexed level (100 = start)"
        yaxis_title = f"{symbol_b} indexed level (100 = start)"
        xaxis_format = ".1f"
        yaxis_format = ".1f"
    
    fig.update_layout(
        title=title_text,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        xaxis=dict(tickformat=xaxis_format),
        yaxis=dict(tickformat=yaxis_format),
        margin=dict(t=40, r=30, l=60, b=50),
    )
    
    return fig


def create_returns_scatter_split(
    rets: pd.DataFrame,
    symbol_a: str,
    symbol_b: str,
    corr: float,
    rets_positive: pd.DataFrame,
    rets_negative: pd.DataFrame
) -> go.Figure:
    """
    Create a scatter plot of returns with positive/negative days colored differently.
    
    Args:
        rets: DataFrame with all returns data
        symbol_a: First symbol (used to determine positive/negative)
        symbol_b: Second symbol
        corr: Overall correlation value
        rets_positive: DataFrame with returns for days where symbol_a was positive
        rets_negative: DataFrame with returns for days where symbol_a was negative
    
    Returns:
        Plotly Figure with scatter plot (green for positive days, red for negative days)
    """
    fig = go.Figure()
    
    # Add positive days (green)
    if not rets_positive.empty:
        fig.add_trace(
            go.Scatter(
                x=rets_positive[symbol_a],
                y=rets_positive[symbol_b],
                mode="markers",
                name=f"{symbol_a} positive days",
                marker=dict(size=6, opacity=0.6, color="#28a745"),
                hovertemplate=(
                    f"<b>{symbol_a} positive day</b><br>"
                    f"{symbol_a} return: %{{x:.2%}}<br>"
                    f"{symbol_b} return: %{{y:.2%}}<extra></extra>"
                )
            )
        )
    
    # Add negative days (red)
    if not rets_negative.empty:
        fig.add_trace(
            go.Scatter(
                x=rets_negative[symbol_a],
                y=rets_negative[symbol_b],
                mode="markers",
                name=f"{symbol_a} negative days",
                marker=dict(size=6, opacity=0.6, color="#dc3545"),
                hovertemplate=(
                    f"<b>{symbol_a} negative day</b><br>"
                    f"{symbol_a} return: %{{x:.2%}}<br>"
                    f"{symbol_b} return: %{{y:.2%}}<extra></extra>"
                )
            )
        )
    
    # Add zero days (gray) if any - check in the original rets DataFrame
    # Zero days are those where symbol_a return is exactly 0
    rets_zero = rets[(rets[symbol_a] == 0) & (rets[symbol_b].notna())]
    if not rets_zero.empty:
        fig.add_trace(
            go.Scatter(
                x=rets_zero[symbol_a],
                y=rets_zero[symbol_b],
                mode="markers",
                name=f"{symbol_a} zero days",
                marker=dict(size=6, opacity=0.4, color="#6c757d"),
                hovertemplate=(
                    f"<b>{symbol_a} zero day</b><br>"
                    f"{symbol_a} return: %{{x:.2%}}<br>"
                    f"{symbol_b} return: %{{y:.2%}}<extra></extra>"
                )
            )
        )
    
    fig.update_layout(
        title=f"Returns scatter — {symbol_a} vs {symbol_b} | corr={corr*100:.1f}%",
        xaxis_title=f"{symbol_a} daily return (%)",
        yaxis_title=f"{symbol_b} daily return (%)",
        xaxis=dict(tickformat=".1%"),
        yaxis=dict(tickformat=".1%"),
        margin=dict(t=40, r=30, l=60, b=50),
        legend=dict(
            x=1.02,
            y=1,
            xanchor="left",
            yanchor="top"
        )
    )
    
    return fig

