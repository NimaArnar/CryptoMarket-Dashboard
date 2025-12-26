"""Dash application callbacks."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx

from src.config import CACHE_DIR, MIN_CORR_DAYS
from src.constants import (
    DEFAULT_CORR_MODE,
    DEFAULT_GROUP,
    DEFAULT_SMOOTHING,
    DEFAULT_VIEW,
    DOM_CAT,
    DOM_SYM,
    MIN_MARKET_CAP_FOR_VALID,
)
from src.data import apply_smoothing, find_dydx_baseline_date, group_filter, normalize_start100, symbols_for_view
from src.data_manager import DataManager
from src.utils import setup_logger
from src.visualization import color_for, compute_usdt_d_index, create_returns_scatter, series_for_symbol

logger = setup_logger(__name__)


def register_callbacks(app, data_manager: DataManager) -> None:
    """
    Register all Dash callbacks with the app.
    
    Args:
        app: Dash application instance
        data_manager: DataManager instance with loaded data
    """
    # Store references for callbacks to access
    df_raw = data_manager.df_raw
    meta = data_manager.meta
    symbols_all = data_manager.symbols_all
    
    @app.callback(
        Output("order", "data"),
        Input("state", "data"),
    )
    def update_order(state):
        """Update trace order whenever state changes."""
        if state is None:
            return []
        group_syms = group_filter(symbols_all, meta, state["group"])
        return symbols_for_view(group_syms, state["view"])
    
    @app.callback(
        Output("state", "data"),
        Output("selected", "data"),
        Input("btn-all", "n_clicks"),
        Input("btn-infra", "n_clicks"),
        Input("btn-defi", "n_clicks"),
        Input("btn-memes", "n_clicks"),
        Input("btn-consumer", "n_clicks"),
        Input("btn-infra-memes", "n_clicks"),
        Input("btn-s0", "n_clicks"),
        Input("btn-s7", "n_clicks"),
        Input("btn-s14", "n_clicks"),
        Input("btn-s30", "n_clicks"),
        Input("btn-view-norm-lin", "n_clicks"),
        Input("btn-view-norm-log", "n_clicks"),
        Input("btn-view-mc-log", "n_clicks"),
        Input("btn-corr-off", "n_clicks"),
        Input("btn-corr-ret", "n_clicks"),
        Input("btn-corr-lvl", "n_clicks"),
        Input("btn-select-all", "n_clicks"),
        Input("btn-unselect-all", "n_clicks"),
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
        n_sel_all, n_unselect_all,
        restyle,
        state, selected, order
    ):
        """Update state and selection based on button clicks and legend interactions."""
        trig = ctx.triggered_id
        new_state = dict(state or {})
        selected_set = set(selected or [])
        
        # Group buttons
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
        
        # Smoothing buttons
        elif trig == "btn-s0":
            new_state["smoothing"] = "No smoothing"
        elif trig == "btn-s7":
            new_state["smoothing"] = "7D SMA"
        elif trig == "btn-s14":
            new_state["smoothing"] = "14D EMA"
        elif trig == "btn-s30":
            new_state["smoothing"] = "30D SMA"
        
        # View buttons
        elif trig == "btn-view-norm-lin":
            new_state["view"] = "Normalized (Linear)"
        elif trig == "btn-view-norm-log":
            new_state["view"] = "Normalized (Log)"
        elif trig == "btn-view-mc-log":
            new_state["view"] = "Market Cap (Log)"
        
        # Correlation mode buttons
        elif trig == "btn-corr-off":
            new_state["corr_mode"] = "off"
        elif trig == "btn-corr-ret":
            new_state["corr_mode"] = "returns"
        elif trig == "btn-corr-lvl":
            new_state["corr_mode"] = "levels"
        
        # Bulk selection buttons
        elif trig == "btn-select-all":
            selected_set = set(order or [])
        elif trig == "btn-unselect-all":
            selected_set = set()
        
        # Legend click persistence
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
        
        # CRITICAL: Recalculate order based on new_state to ensure selected coins
        # are filtered correctly when view/group changes
        current_group = new_state.get("group", DEFAULT_GROUP)
        current_view = new_state.get("view", DEFAULT_VIEW)
        group_syms = group_filter(symbols_all, meta, current_group)
        current_order = symbols_for_view(group_syms, current_view)
        
        # Restrict selected to current order (use recalculated order, not old one)
        if current_order:
            allowed = set(current_order)
            selected_set = {s for s in selected_set if s in allowed}
        
        def sort_key(s):
            try:
                return (current_order.index(s) if current_order and s in current_order else 10**9, s)
            except ValueError:
                return (10**9, s)
        
        ordered_selected = sorted(selected_set, key=sort_key)
        return new_state, ordered_selected
    
    @app.callback(
        Output("chart", "figure"),
        Input("state", "data"),
        Input("selected", "data"),
        Input("order", "data"),
    )
    def render_chart(state, selected_syms, order):
        """Render the main chart with all selected coins."""
        return _render_chart_internal(state, selected_syms, order, df_raw, meta, symbols_all)
    
    @app.callback(
        Output("corr-output", "children"),
        Output("scatter", "figure"),
        Input("state", "data"),
        Input("selected", "data"),
        Input("order", "data"),
    )
    def corr_and_scatter(state, selected_syms, order):
        """Calculate correlation and render scatter plot."""
        return _corr_and_scatter_internal(state, selected_syms, order, df_raw)


def _render_chart_internal(
    state: Dict,
    selected_syms: List[str],
    order: List[str],
    df_raw: pd.DataFrame,
    meta: Dict,
    symbols_all: List[str]
) -> go.Figure:
    """Internal function to render chart (extracted for clarity)."""
    # Handle None state
    if state is None:
        logger.error("State is None in render_chart callback!")
        state = {
            "group": DEFAULT_GROUP,
            "smoothing": DEFAULT_SMOOTHING,
            "view": DEFAULT_VIEW,
            "corr_mode": DEFAULT_CORR_MODE
        }
    
    smoothing = state.get("smoothing", DEFAULT_SMOOTHING)
    group_choice = state.get("group", DEFAULT_GROUP)
    view = state.get("view", DEFAULT_VIEW)
    selected_set = set(selected_syms or [])
    
    logger.debug(f"Rendering chart: View={view}, Smoothing={smoothing}, Group={group_choice}")
    
    # Prepare data for smoothing
    df_for_smoothing = _prepare_data_for_smoothing(df_raw)
    
    # Apply smoothing
    df_s = apply_smoothing(df_for_smoothing, smoothing)
    
    # Handle DYDX special smoothing (keep Q constant)
    df_s = _handle_dydx_smoothing(df_s, df_for_smoothing, smoothing)
    
    # Create plot data based on view
    df_plot, yaxis_title, yaxis_type, normalized_view = _prepare_plot_data(df_s, view)
    
    # Compute USDT.D index if needed
    usdt_d_index = compute_usdt_d_index(df_s) if normalized_view else None
    
    # Build figure
    fig = go.Figure()
    cur_order = order or symbols_for_view(group_filter(symbols_all, meta, group_choice), view)
    
    for sym in cur_order:
        if sym not in meta:
            continue
        
        cat, grp = meta.get(sym, ("", ""))
        
        # Handle USDT.D
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
        
        # Get data series for this symbol
        data_series = _get_data_series_for_symbol(sym, df_plot, df_s, df_raw, view, normalized_view)
        
        if data_series is None:
            continue
        
        # Prepare valid data for plotting
        valid_data = _prepare_valid_data(data_series, sym, df_s, normalized_view, view)
        
        if valid_data is None or valid_data.empty:
            continue
        
        # Add trace to figure
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
    
    logger.debug(f"Returning figure with {len(fig.data)} traces")
    if len(fig.data) == 0:
        logger.warning("WARNING: Figure has no traces! cur_order might be empty or no valid data found.")
    
    return fig


def _prepare_data_for_smoothing(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Prepare data for smoothing by filtering out zeros before first valid point."""
    df_for_smoothing = df_raw.copy()
    
    for col in df_for_smoothing.columns:
        col_data = df_for_smoothing[col]
        valid_mask = (col_data != 0) & (~pd.isna(col_data))
        if valid_mask.any():
            first_valid_idx = col_data[valid_mask].index[0]
            
            # For DYDX, use Dec 25 as first valid index
            if col == "DYDX":
                dec25 = pd.Timestamp("2024-12-25")
                if dec25 in col_data.index and col_data.loc[dec25] > MIN_MARKET_CAP_FOR_VALID:
                    first_valid_idx = dec25
                    logger.info(f"DYDX: Forcing first_valid_idx to Dec 25 (MC={col_data.loc[dec25]:,.0f})")
            
            # Set all values before first valid to NaN
            mask_before_valid = df_for_smoothing.index < first_valid_idx
            df_for_smoothing.loc[mask_before_valid, col] = pd.NA
        else:
            df_for_smoothing[col] = pd.NA
    
    return df_for_smoothing


def _handle_dydx_smoothing(
    df_s: pd.DataFrame,
    df_for_smoothing: pd.DataFrame,
    smoothing: str
) -> pd.DataFrame:
    """Handle special DYDX smoothing to keep Q constant."""
    if "DYDX" not in df_for_smoothing.columns or smoothing == "No smoothing":
        return df_s
    
    apr2 = pd.Timestamp("2025-04-02")
    if apr2 not in df_for_smoothing.index:
        return df_s
    
    apr4_check = pd.Timestamp("2025-04-04")
    if apr4_check not in df_for_smoothing.index:
        return df_s
    
    apr4_mc_check = df_for_smoothing.loc[apr4_check, "DYDX"]
    if apr4_mc_check <= MIN_MARKET_CAP_FOR_VALID:
        return df_s  # DYDX not fixed, use normal smoothing
    
    # Load prices and smooth them instead of MC
    cache_path = CACHE_DIR / "dydx_365d_usd.json"
    if not cache_path.exists():
        return df_s
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            js = json.load(f)
        
        if "prices" not in js or not js["prices"]:
            return df_s
        
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
        
        # Calculate last correct Q value before break_date
        break_date = apr2
        before_break = df_for_smoothing.index[df_for_smoothing.index < break_date]
        if len(before_break) > 0 and "DYDX" in df_for_smoothing.columns:
            last_correct_date = before_break[-1]
            if last_correct_date in prices_raw.index:
                last_mc = df_for_smoothing.loc[last_correct_date, "DYDX"]
                last_price = prices_raw.loc[last_correct_date]
                if last_price > 0 and last_mc > 0:
                    q_baseline = last_mc / last_price
                else:
                    return df_s  # Can't calculate Q
            else:
                return df_s
        else:
            return df_s
        
        # Recalculate MC = Q_baseline * Price_smoothed for dates >= break_date
        for dt in df_for_smoothing.index:
            if dt >= break_date and dt in prices_smoothed.index:
                price_sm = prices_smoothed.loc[dt]
                if pd.notna(price_sm) and price_sm > 0:
                    mc_recalc = q_baseline * price_sm
                    df_s.loc[dt, "DYDX"] = mc_recalc
        
        logger.info("Fixed DYDX smoothing: Used Price smoothing to keep Q constant")
    except Exception as e:
        logger.error(f"Error in DYDX smoothing fix: {e}")
    
    return df_s


def _prepare_plot_data(
    df_s: pd.DataFrame, view: str
) -> Tuple[pd.DataFrame, str, str, bool]:
    """
    Prepare plot data based on view type.
    
    Returns:
        Tuple of (df_plot, yaxis_title, yaxis_type, normalized_view)
    """
    if view == "Normalized (Linear)":
        df_plot = normalize_start100(df_s)
        # Force DYDX normalization
        df_plot = _force_dydx_normalization(df_plot, df_s)
        return df_plot, "Index (100 = first value)", "linear", True
    
    elif view == "Normalized (Log)":
        df_plot = normalize_start100(df_s)
        df_plot = _force_dydx_normalization(df_plot, df_s)
        return df_plot, "Index (100 = first value, log)", "log", True
    
    else:  # Market Cap (Log)
        df_plot = df_s
        return df_plot, "Market Cap (USD, log)", "log", False


def _force_dydx_normalization(df_plot: pd.DataFrame, df_s: pd.DataFrame) -> pd.DataFrame:
    """Force correct DYDX normalization using Dec 25 baseline."""
    if "DYDX" not in df_s.columns:
        return df_plot
    
    baseline_date, baseline_mc = find_dydx_baseline_date(df_s["DYDX"])
    if baseline_date is None or baseline_mc is None:
        logger.warning("DYDX: Could not find valid baseline date near Dec 25")
        return df_plot
    
    dydx_col = df_s["DYDX"]
    dydx_normalized = (dydx_col / baseline_mc * 100)
    dydx_normalized.loc[dydx_normalized.index < baseline_date] = pd.NA
    dydx_normalized[dydx_col.isna()] = pd.NA
    df_plot["DYDX"] = dydx_normalized
    
    logger.info(
        f"DYDX: Force normalized using {baseline_date.strftime('%Y-%m-%d')} "
        f"baseline (MC={baseline_mc:,.0f})"
    )
    
    return df_plot


def _get_data_series_for_symbol(
    sym: str,
    df_plot: pd.DataFrame,
    df_s: pd.DataFrame,
    df_raw: pd.DataFrame,
    view: str,
    normalized_view: bool
) -> Optional[pd.Series]:
    """Get data series for a symbol, with special handling for DYDX."""
    # For DYDX, always use df_plot
    if sym == "DYDX":
        if sym in df_plot.columns:
            data_series = df_plot[sym]
            if data_series.dropna().empty:
                logger.error("DYDX is in df_plot but has no valid data!")
                return None
        else:
            logger.error("DYDX is NOT in df_plot! This should not happen.")
            if sym in df_s.columns:
                df_plot[sym] = normalize_start100(df_s[[sym]])[sym]
                data_series = df_plot[sym]
                logger.warning("Force-added DYDX to df_plot")
            else:
                return None
        
        # Final safety: recalculate normalization
        if sym in df_s.columns and normalized_view:
            baseline_date, baseline_mc = find_dydx_baseline_date(df_s[sym])
            if baseline_date is not None and baseline_mc is not None:
                data_series_fixed = (df_s[sym] / baseline_mc * 100)
                data_series_fixed.loc[data_series_fixed.index < baseline_date] = pd.NA
                data_series_fixed[df_s[sym].isna()] = pd.NA
                data_series = data_series_fixed
                logger.info(
                    f"DYDX: Final safety recalculation - "
                    f"baseline={baseline_mc:,.0f} (date={baseline_date.strftime('%Y-%m-%d')})"
                )
        
        return data_series
    
    # For other symbols, try df_plot first
    if sym in df_plot.columns:
        data_series = df_plot[sym]
        if not data_series.dropna().empty and not (data_series.dropna() == 0).all():
            return data_series
    
    # Fallback to raw data
    if sym in df_raw.columns:
        raw_col = df_raw[sym]
        if normalized_view:
            valid_mask = (raw_col != 0) & (~pd.isna(raw_col))
            if not valid_mask.any():
                return None
            
            first_valid_idx = raw_col[valid_mask].index[0]
            first_valid_val = raw_col.loc[first_valid_idx]
            
            data_series = (raw_col / first_valid_val * 100)
            data_series.loc[data_series.index < first_valid_idx] = pd.NA
            return data_series
        else:
            return raw_col
    
    return None


def _prepare_valid_data(
    data_series: pd.Series,
    sym: str,
    df_s: pd.DataFrame,
    normalized_view: bool,
    view: str
) -> Optional[pd.Series]:
    """Prepare valid data for plotting, with special handling for DYDX."""
    # Drop NaN values
    valid_data = data_series.dropna()
    if valid_data.empty:
        return None
    
    # Remove zeros at the start
    non_zero_mask = valid_data != 0
    if non_zero_mask.any():
        first_non_zero_idx = valid_data[non_zero_mask].index[0]
        valid_data = valid_data.loc[valid_data.index >= first_non_zero_idx]
    
    if valid_data.empty:
        return None
    
    # Final safety for DYDX: recalculate right before plotting
    if sym == "DYDX" and normalized_view and sym in df_s.columns:
        baseline_date, baseline_mc = find_dydx_baseline_date(df_s[sym])
        if baseline_date is not None and baseline_mc is not None:
            data_series_final = (df_s[sym] / baseline_mc * 100)
            data_series_final.loc[data_series_final.index < baseline_date] = pd.NA
            data_series_final[df_s[sym].isna()] = pd.NA
            
            valid_data_final = data_series_final.dropna()
            if len(valid_data_final) > 0:
                non_zero_final = valid_data_final != 0
                if non_zero_final.any():
                    first_non_zero_final = valid_data_final[non_zero_final].index[0]
                    valid_data = valid_data_final.loc[valid_data_final.index >= first_non_zero_final]
                    logger.info(
                        f"DYDX: Final pre-plot recalculation applied "
                        f"(baseline={baseline_date.strftime('%Y-%m-%d')})"
                    )
    
    return valid_data


def _corr_and_scatter_internal(
    state: Dict,
    selected_syms: List[str],
    order: List[str],
    df_raw: pd.DataFrame
) -> Tuple[str, go.Figure]:
    """Internal function to calculate correlation and create scatter plot."""
    view = state.get("view", DEFAULT_VIEW)
    smoothing = state.get("smoothing", DEFAULT_SMOOTHING)
    corr_mode = state.get("corr_mode", "off")
    
    # Build empty placeholder
    empty_fig = go.Figure()
    empty_fig.update_layout(
        xaxis_title="Returns of A",
        yaxis_title="Returns of B",
        margin=dict(t=30, r=30, l=60, b=50),
        annotations=[dict(
            text="Select exactly 2 symbols to see the returns scatter.",
            x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False
        )],
    )
    
    if corr_mode == "off":
        return "Correlation: Off", empty_fig
    
    # Only consider symbols that are currently traceable
    allowed = set(order or [])
    sel = [s for s in (selected_syms or []) if s in allowed]
    
    if len(sel) != 2:
        return f"Select exactly 2 symbols (currently {len(sel)}).", empty_fig
    
    a, b = sel[0], sel[1]
    
    df_s = apply_smoothing(df_raw, smoothing)
    
    sA = series_for_symbol(a, df_s, view)
    sB = series_for_symbol(b, df_s, view)
    
    if sA is None or sB is None:
        return f"Cannot compute series for {a} or {b} in this view.", empty_fig
    
    # Align by date (inner join)
    df = pd.concat([sA.rename(a), sB.rename(b)], axis=1, join="inner").dropna()
    
    if df.shape[0] < MIN_CORR_DAYS:
        return (
            f"Not enough overlapping data for {a} and {b} "
            f"(need ≥{MIN_CORR_DAYS} days, got {df.shape[0]}).",
            empty_fig,
        )
    
    # Calculate returns and correlation
    rets = df.pct_change().dropna()
    
    # Calculate beta (regression slope)
    beta = None
    if not rets.empty and rets[a].var() > 0:
        beta = rets[b].cov(rets[a]) / rets[a].var()
    
    if corr_mode == "returns":
        corr = rets[a].corr(rets[b])
        scat = create_returns_scatter(rets, a, b, corr, "returns")
        if beta is not None:
            implied_move = beta * 10
            text = (
                f"Correlation (daily returns) — {a} vs {b}: {corr:.3f} | "
                f"beta={beta:.2f} (if {a} +10%, {b} ≈ {implied_move:+.1f}%)"
            )
        else:
            text = f"Correlation (daily returns) — {a} vs {b}: {corr:.3f}"
        return text, scat
    
    # Levels mode: correlate indexed levels
    idx = df / df.iloc[0] * 100
    corr = idx[a].corr(idx[b])
    
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

