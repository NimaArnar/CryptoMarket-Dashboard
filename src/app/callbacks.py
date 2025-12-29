"""Dash application callbacks."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, html, dcc
from dash import dash_table

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
from src.data import apply_smoothing, group_filter, normalize_start100, symbols_for_view
from src.data_manager import DataManager
from src.utils import setup_logger
from src.visualization import color_for, compute_usdt_d_index, create_returns_scatter, create_returns_scatter_split, series_for_symbol

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
            # Use defaults if state is None
            group_syms = group_filter(symbols_all, meta, DEFAULT_GROUP)
            return symbols_for_view(group_syms, DEFAULT_VIEW)
        group_syms = group_filter(symbols_all, meta, state.get("group", DEFAULT_GROUP))
        return symbols_for_view(group_syms, state.get("view", DEFAULT_VIEW))
    
    @app.callback(
        Output("state", "data"),
        Output("selected", "data"),
        Input("btn-s0", "n_clicks"),
        Input("btn-s7", "n_clicks"),
        Input("btn-s14", "n_clicks"),
        Input("btn-s30", "n_clicks"),
        Input("btn-view-norm-lin", "n_clicks"),
        Input("btn-view-norm-log", "n_clicks"),
        Input("btn-view-mc-log", "n_clicks"),
        Input("btn-corr-off", "n_clicks"),
        Input("btn-corr-ret", "n_clicks"),
        Input("btn-select-all", "n_clicks"),
        Input("btn-unselect-all", "n_clicks"),
        Input("chart", "restyleData"),
        State("state", "data"),
        State("selected", "data"),
        State("order", "data"),
        prevent_initial_call=True
    )
    def update_state_and_selected(
        n_s0, n_s7, n_s14, n_s30,
        n_v_lin, n_v_log, n_v_mc,
        n_c_off, n_c_ret,
        n_select_all, n_unselect_all,
        restyle,
        state, selected, order
    ):
        """Update state and selection based on button clicks and legend interactions."""
        trig = ctx.triggered_id
        new_state = dict(state or {})
        # Preserve selection order by using a list, not a set
        selected_list = list(selected or [])
        selected_set = set(selected_list)  # For efficient membership testing
        
        # Group buttons removed from UI but functionality preserved (defaults to "all")
        # Group state is maintained but not changeable via UI
        
        # Smoothing buttons
        if trig == "btn-s0":
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
        
        # Selection buttons
        elif trig == "btn-select-all":
            # Select all will be handled after order calculation
            pass
        elif trig == "btn-unselect-all":
            # Clear selection
            selected_list = []
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
                            # Add to end of list to preserve selection order
                            if sym not in selected_set:
                                selected_list.append(sym)
                                selected_set.add(sym)
                        elif v in (False, "legendonly"):
                            # Remove from list while preserving order
                            if sym in selected_set:
                                selected_list.remove(sym)
                                selected_set.remove(sym)
        
        # CRITICAL: Recalculate order based on new_state to ensure selected coins
        # are filtered correctly when view/group changes
        current_group = new_state.get("group", DEFAULT_GROUP)
        current_view = new_state.get("view", DEFAULT_VIEW)
        group_syms = group_filter(symbols_all, meta, current_group)
        current_order = symbols_for_view(group_syms, current_view)
        
        # Handle select all / unselect all
        if trig == "btn-select-all":
            # Select all coins in current order
            selected_list = list(current_order) if current_order else []
            selected_set = set(selected_list)
        elif trig == "btn-unselect-all":
            # Already cleared above
            pass
        
        # Restrict selected to current order (preserve order from selected_list)
        if current_order:
            allowed = set(current_order)
            # Filter while preserving order
            selected_list = [s for s in selected_list if s in allowed]
            selected_set = set(selected_list)
        
        # Return selected_list which preserves selection order (not sorted by chart order)
        return new_state, selected_list
    
    @app.callback(
        Output("tab-content", "children"),
        Output("controls-container", "style"),
        Input("main-tabs", "value"),
    )
    def update_tab_content(active_tab):
        """Update content based on selected tab and control visibility."""
        if active_tab == "chart-tab":
            chart = dcc.Graph(id="chart", style={"height": "75vh"})
            controls_style = {"display": "block"}
            return chart, controls_style
        elif active_tab == "data-tab":
            table = _generate_data_table(df_raw, meta, symbols_all)
            controls_style = {"display": "none"}
            return table, controls_style
        return html.Div("Unknown tab"), {"display": "block"}
    
    @app.callback(
        Output("chart", "figure"),
        Input("state", "data"),
        Input("selected", "data"),
        Input("order", "data"),
        Input("main-tabs", "value"),
    )
    def render_chart(state, selected_syms, order, active_tab):
        """Render the main chart with all selected coins."""
        # Only render if chart tab is active
        if active_tab != "chart-tab":
            return go.Figure()
        
        # Filter selected coins to match current order if order is available
        if order and selected_syms:
            filtered_selected = [s for s in selected_syms if s in order]
            if len(filtered_selected) != len(selected_syms):
                logger.info(f"Filtered selected coins to match order: {len(selected_syms)} -> {len(filtered_selected)}")
                selected_syms = filtered_selected
        
        return _render_chart_internal(state, selected_syms, order, df_raw, meta, symbols_all)
    
    @app.callback(
        Output("corr-output", "children"),
        Output("scatter", "figure"),
        Output("scatter-container", "style"),  # Control visibility
        Input("state", "data"),
        Input("selected", "data"),
        Input("order", "data"),
    )
    def corr_and_scatter(state, selected_syms, order):
        """Calculate correlation and render scatter plot."""
        corr_text, scatter_fig = _corr_and_scatter_internal(state, selected_syms, order, df_raw)
        
        # Check if correlation is off
        corr_mode = "off"
        if state:
            corr_mode = state.get("corr_mode", "off")
        
        # Check if exactly 2 coins are selected AND correlation is not off
        allowed = set(order or [])
        sel = [s for s in (selected_syms or []) if s in allowed]
        show_scatter = len(sel) == 2 and corr_mode != "off"
        
        # Hide scatter container if not exactly 2 coins or correlation is off
        container_style = {
            "marginTop": "20px",
            "display": "block" if show_scatter else "none"
        }
        
        return corr_text, scatter_fig, container_style
    
    @app.callback(
        Output("btn-s0", "style"),
        Output("btn-s7", "style"),
        Output("btn-s14", "style"),
        Output("btn-s30", "style"),
        Output("btn-view-norm-lin", "style"),
        Output("btn-view-norm-log", "style"),
        Output("btn-view-mc-log", "style"),
        Output("btn-corr-off", "style"),
        Output("btn-corr-ret", "style"),
        Input("state", "data"),
    )
    def update_button_styles(state):
        """Update button styles to show active state."""
        # Base button style
        button_style = {
            "padding": "10px 20px",
            "margin": "4px",
            "border": "1px solid #dee2e6",
            "borderRadius": "6px",
            "backgroundColor": "#ffffff",
            "color": "#495057",
            "fontSize": "14px",
            "fontWeight": "500",
            "cursor": "pointer",
            "transition": "all 0.2s ease",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"
        }
        
        # Active button style
        active_button_style = {
            **button_style,
            "backgroundColor": "#007bff",
            "color": "#ffffff",
            "borderColor": "#007bff",
            "boxShadow": "0 2px 6px rgba(0,123,255,0.3)"
        }
        
        # Get current state values
        if state is None:
            smoothing = DEFAULT_SMOOTHING
            view = DEFAULT_VIEW
            corr_mode = DEFAULT_CORR_MODE
        else:
            smoothing = state.get("smoothing", DEFAULT_SMOOTHING)
            view = state.get("view", DEFAULT_VIEW)
            corr_mode = state.get("corr_mode", DEFAULT_CORR_MODE)
        
        # Determine which buttons are active
        s0_active = smoothing == "No smoothing"
        s7_active = smoothing == "7D SMA"
        s14_active = smoothing == "14D EMA"
        s30_active = smoothing == "30D SMA"
        
        v_lin_active = view == "Normalized (Linear)"
        v_log_active = view == "Normalized (Log)"
        v_mc_active = view == "Market Cap (Log)"
        
        c_off_active = corr_mode == "off"
        c_ret_active = corr_mode == "returns"
        
        return (
            active_button_style if s0_active else button_style,
            active_button_style if s7_active else button_style,
            active_button_style if s14_active else button_style,
            active_button_style if s30_active else button_style,
            active_button_style if v_lin_active else button_style,
            active_button_style if v_log_active else button_style,
            active_button_style if v_mc_active else button_style,
            active_button_style if c_off_active else button_style,
            active_button_style if c_ret_active else button_style,
        )


def _generate_data_table(df_raw: pd.DataFrame, meta: Dict, symbols_all: List[str]) -> html.Div:
    """Generate a data table showing latest price, Q supply, and market cap for all coins."""
    if df_raw is None or df_raw.empty:
        return html.Div("No data available", style={"padding": "20px", "color": "#dc3545"})
    
    # Load price data
    prices_dict = _load_price_data()
    
    # Get latest date
    latest_date = df_raw.index.max()
    
    # Prepare data for table
    table_data = []
    for sym in sorted(symbols_all):
        if sym not in df_raw.columns:
            continue
        
        # Get latest market cap
        mc_series = df_raw[sym].dropna()
        if mc_series.empty:
            continue
        
        latest_mc = mc_series.iloc[-1]
        
        # Get latest price
        latest_price = None
        if sym in prices_dict:
            price_series = prices_dict[sym].dropna()
            if not price_series.empty:
                latest_price = price_series.iloc[-1]
        
        # Calculate Q supply (MC / Price)
        q_supply = None
        if latest_price and latest_price > 0:
            q_supply = latest_mc / latest_price
        
        # Store numeric values for proper sorting, formatting will be done by dash_table
        table_data.append({
            "Coin": sym,
            "Price (USD)": latest_price if latest_price and pd.notna(latest_price) else None,
            "Q Supply": q_supply if q_supply and pd.notna(q_supply) else None,
            "Market Cap (USD)": latest_mc if pd.notna(latest_mc) else None
        })
    
    if not table_data:
        return html.Div("No data available", style={"padding": "20px", "color": "#dc3545"})
    
    return html.Div(
        style={
            "backgroundColor": "#ffffff",
            "padding": "20px",
            "borderRadius": "8px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.08)"
        },
        children=[
            html.H3(
                f"Latest Data (as of {latest_date.strftime('%Y-%m-%d')})",
                style={
                    "marginBottom": "20px",
                    "color": "#2c3e50",
                    "fontWeight": "600"
                }
            ),
            dash_table.DataTable(
                data=table_data,
                columns=[
                    {"name": "Coin", "id": "Coin", "type": "text"},
                    {
                        "name": "Price (USD)", 
                        "id": "Price (USD)", 
                        "type": "numeric",
                        "format": dash_table.Format.Format(
                            scheme=dash_table.Format.Scheme.fixed,
                            precision=2
                        ).symbol_prefix("$")
                    },
                    {
                        "name": "Q Supply", 
                        "id": "Q Supply", 
                        "type": "numeric",
                        "format": dash_table.Format.Format(
                            scheme=dash_table.Format.Scheme.decimal_integer
                        )
                    },
                    {
                        "name": "Market Cap (USD)", 
                        "id": "Market Cap (USD)", 
                        "type": "numeric",
                        "format": dash_table.Format.Format(
                            scheme=dash_table.Format.Scheme.decimal_integer
                        ).symbol_prefix("$")
                    }
                ],
                style_table={
                    "overflowX": "auto",
                    "width": "100%"
                },
                style_cell={
                    "textAlign": "left",
                    "padding": "12px",
                    "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                    "fontSize": "14px",
                    "border": "1px solid #dee2e6"
                },
                style_cell_conditional=[
                    {
                        "if": {"column_id": "Price (USD)"},
                        "textAlign": "right"
                    },
                    {
                        "if": {"column_id": "Q Supply"},
                        "textAlign": "right"
                    },
                    {
                        "if": {"column_id": "Market Cap (USD)"},
                        "textAlign": "right"
                    }
                ],
                style_data_conditional=[
                    {
                        "if": {"row_index": "odd"},
                        "backgroundColor": "#f8f9fa"
                    }
                ],
                style_header={
                    "backgroundColor": "#007bff",
                    "color": "#ffffff",
                    "fontWeight": "600",
                    "textAlign": "center"
                },
                style_data={
                    "backgroundColor": "#ffffff",
                    "color": "#495057"
                },
                sort_action="native",
                filter_action="native",
                page_action="native",
                page_size=20
            )
        ]
    )


def _load_price_data() -> Dict[str, pd.Series]:
    """Load price data from cache files for all coins."""
    from src.config import CACHE_DIR, DAYS_HISTORY, VS_CURRENCY
    from src.constants import COINS
    
    prices_dict = {}
    
    for coin_id, sym, _, _ in COINS:
        cache_path = CACHE_DIR / f"{coin_id}_{DAYS_HISTORY}d_{VS_CURRENCY}.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    js = json.load(f)
                
                if "prices" in js and js["prices"]:
                    df_prices = pd.DataFrame(js["prices"], columns=["ts", "price"])
                    df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
                    df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
                    prices_dict[sym] = df_prices.set_index("date")["price"].sort_index()
            except Exception as e:
                logger.warning(f"Failed to load price data for {sym}: {e}")
    
    return prices_dict


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
    
    # Load price data for tooltips
    prices_dict = _load_price_data()
    
    # Prepare data for smoothing
    df_for_smoothing = _prepare_data_for_smoothing(df_raw)
    
    # Apply smoothing
    df_s = apply_smoothing(df_for_smoothing, smoothing)
    
    # Create plot data based on view
    df_plot, yaxis_title, yaxis_type, normalized_view = _prepare_plot_data(df_s, view)
    
    # Compute USDT.D index if needed
    usdt_d_index = compute_usdt_d_index(df_s) if normalized_view else None
    
    # Build figure
    fig = go.Figure()
    
    # Calculate order if not provided or empty
    if not order:
        group_syms = group_filter(symbols_all, meta, group_choice)
        cur_order = symbols_for_view(group_syms, view)
    else:
        cur_order = order
    
    logger.debug(f"Chart rendering: {len(cur_order)} coins in order, {len(selected_set)} selected")
    
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
                        f"<b>{DOM_SYM}</b><br>"
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
        
        # Get price data for tooltip
        price_data = None
        if sym in prices_dict:
            price_series = prices_dict[sym]
            # Align prices with valid_data dates
            price_data = price_series.reindex(valid_data.index)
        
        # Prepare customdata for hover (price values)
        customdata_list = None
        if price_data is not None and not price_data.empty:
            customdata_list = price_data.values
        
        # Build hovertemplate - simplified: only name, date, index/price
        if normalized_view:
            # For normalized views, show index and price
            if customdata_list is not None:
                hovertemplate = (
                    f"<b>{sym}</b><br>"
                    "Date: %{x}<br>"
                    "Index: %{y:.2f}<br>"
                    "Price: $%{customdata:,.2f}<extra></extra>"
                )
            else:
                hovertemplate = (
                    f"<b>{sym}</b><br>"
                    "Date: %{x}<br>"
                    "Index: %{y:.2f}<extra></extra>"
                )
        else:
            # For market cap view, show market cap and price
            if customdata_list is not None:
                hovertemplate = (
                    f"<b>{sym}</b><br>"
                    "Date: %{x}<br>"
                    "Market Cap: %{y:.3s} USD<br>"
                    "Price: $%{customdata:,.2f}<extra></extra>"
                )
            else:
                hovertemplate = (
                    f"<b>{sym}</b><br>"
                    "Date: %{x}<br>"
                    "Market Cap: %{y:.3s} USD<extra></extra>"
                )
        
        # Add trace to figure
        trace_kwargs = {
            "x": valid_data.index,
            "y": valid_data.values,
            "mode": "lines",
            "name": f"{sym} — {cat}",
            "line": dict(color=color_for(sym), width=2),
            "visible": True if sym in selected_set else "legendonly",
            "hovertemplate": hovertemplate,
        }
        
        # Add customdata if available (for normalized views)
        if customdata_list is not None:
            trace_kwargs["customdata"] = customdata_list
        
        fig.add_trace(go.Scatter(**trace_kwargs))
    
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
    
    logger.info(f"Chart rendered: {len(fig.data)} traces, order={len(cur_order)}, selected={len(selected_set)}")
    if len(fig.data) == 0:
        logger.error(
            f"ERROR: Figure has no traces! "
            f"cur_order={cur_order[:5] if cur_order else 'empty'}, "
            f"selected_set={list(selected_set)[:5] if selected_set else 'empty'}, "
            f"df_raw columns={list(df_raw.columns)[:5] if not df_raw.empty else 'empty'}"
        )
    
    return fig


def _prepare_data_for_smoothing(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Prepare data for smoothing by filtering out zeros before first valid point."""
    df_for_smoothing = df_raw.copy()
    
    for col in df_for_smoothing.columns:
        col_data = df_for_smoothing[col]
        valid_mask = (col_data != 0) & (~pd.isna(col_data))
        if valid_mask.any():
            first_valid_idx = col_data[valid_mask].index[0]
            
            # Set all values before first valid to NaN
            mask_before_valid = df_for_smoothing.index < first_valid_idx
            df_for_smoothing.loc[mask_before_valid, col] = pd.NA
        else:
            df_for_smoothing[col] = pd.NA
    
    return df_for_smoothing


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
        return df_plot, "Index (100 = first value)", "linear", True
    
    elif view == "Normalized (Log)":
        df_plot = normalize_start100(df_s)
        return df_plot, "Index (100 = first value, log)", "log", True
    
    else:  # Market Cap (Log)
        df_plot = df_s
        return df_plot, "Market Cap (USD, log)", "log", False


def _get_data_series_for_symbol(
    sym: str,
    df_plot: pd.DataFrame,
    df_s: pd.DataFrame,
    df_raw: pd.DataFrame,
    view: str,
    normalized_view: bool
) -> Optional[pd.Series]:
    """Get data series for a symbol."""
    # Try df_plot first
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
    """Prepare valid data for plotting."""
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
    # Preserve selection order from selected_syms (don't sort by chart order)
    sel = [s for s in (selected_syms or []) if s in allowed]
    
    if len(sel) != 2:
        return f"Select exactly 2 symbols (currently {len(sel)}).", empty_fig
    
    # Use selection order (first selected = a, second selected = b)
    # This ensures correlation and beta reflect the user's selection order
    # IMPORTANT: sel preserves the order from selected_syms, which maintains selection order
    a, b = sel[0], sel[1]
    
    # Prepare data for smoothing
    df_for_smoothing = _prepare_data_for_smoothing(df_raw)
    
    # Apply smoothing (correlation should use the selected smoothing)
    df_s = apply_smoothing(df_for_smoothing, smoothing)
    
    # Apply view transformation (correlation should use market cap data from the view)
    df_plot, _, _, normalized_view = _prepare_plot_data(df_s, view)
    
    # Get series from transformed data (market cap based on view)
    # IMPORTANT: For USDT.D, always use df_s (raw smoothed) not df_plot (normalized)
    # because USDT.D calculation needs actual market cap values, not normalized ones
    # For regular coins, using df_plot (normalized) is correct because:
    # - Returns are scale-invariant (percentage changes), so normalization doesn't affect correlation
    # - Both coins use the same data source (df_plot), ensuring consistency
    # - The view transformation (normalized vs raw) is applied consistently to both
    if a == DOM_SYM:
        sA = series_for_symbol(a, df_s, view)  # Use raw smoothed data for USDT.D
    else:
        sA = series_for_symbol(a, df_plot, view)  # Use transformed data (normalized if view is normalized)
    
    if b == DOM_SYM:
        sB = series_for_symbol(b, df_s, view)  # Use raw smoothed data for USDT.D
    else:
        sB = series_for_symbol(b, df_plot, view)  # Use transformed data (normalized if view is normalized)
    
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
    
    if rets.empty:
        return "Not enough data to calculate returns.", empty_fig
    
    # Check if we have enough data points after calculating returns
    if len(rets) < MIN_CORR_DAYS:
        return (
            f"Not enough data points for correlation after calculating returns "
            f"(need ≥{MIN_CORR_DAYS} days, got {len(rets)}).",
            empty_fig,
        )
    
    # Split returns by positive/negative days of coin A (first selected)
    # NOTE: Subset correlations (positive/negative days) can differ from overall correlation
    # This is mathematically valid and reflects different relationship structures
    # in different market conditions (e.g., stronger correlation in down markets)
    positive_mask = rets[a] > 0
    negative_mask = rets[a] < 0
    
    rets_positive = rets[positive_mask]
    rets_negative = rets[negative_mask]
    
    # Calculate overall correlation and beta
    # Check for NaN (can happen if one series is constant or insufficient data)
    corr_overall = rets[a].corr(rets[b])
    if pd.isna(corr_overall):
        return f"Cannot calculate correlation: insufficient variance in {a} or {b} returns.", empty_fig
    
    beta_overall = None
    if rets[a].var() > 0 and not pd.isna(rets[a].var()):
        beta_overall = rets[b].cov(rets[a]) / rets[a].var()
        if pd.isna(beta_overall):
            beta_overall = None
    
    # Calculate correlation and beta for positive days
    corr_positive = None
    beta_positive = None
    n_positive = len(rets_positive)
    if n_positive >= MIN_CORR_DAYS:  # Use MIN_CORR_DAYS for consistency
        corr_positive = rets_positive[a].corr(rets_positive[b])
        # Check if correlation is valid (not NaN)
        if pd.isna(corr_positive):
            corr_positive = None
        elif rets_positive[a].var() > 0 and not pd.isna(rets_positive[a].var()):
            beta_positive = rets_positive[b].cov(rets_positive[a]) / rets_positive[a].var()
            if pd.isna(beta_positive):
                beta_positive = None
    
    # Calculate correlation and beta for negative days
    corr_negative = None
    beta_negative = None
    n_negative = len(rets_negative)
    if n_negative >= MIN_CORR_DAYS:  # Use MIN_CORR_DAYS for consistency
        corr_negative = rets_negative[a].corr(rets_negative[b])
        # Check if correlation is valid (not NaN)
        if pd.isna(corr_negative):
            corr_negative = None
        elif rets_negative[a].var() > 0 and not pd.isna(rets_negative[a].var()):
            beta_negative = rets_negative[b].cov(rets_negative[a]) / rets_negative[a].var()
            if pd.isna(beta_negative):
                beta_negative = None
    
    # Create scatter plot with positive/negative coloring
    scat = create_returns_scatter_split(rets, a, b, corr_overall, rets_positive, rets_negative)
    
    # Build text output
    text_parts = []
    
    # Overall statistics
    if beta_overall is not None:
        implied_move = beta_overall * 10
        text_parts.append(
            f"Overall: corr={corr_overall*100:.1f}%, beta={beta_overall:.2f} "
            f"(if {a} +10%, {b} ≈ {implied_move:+.1f}%)"
        )
    else:
        text_parts.append(f"Overall: corr={corr_overall*100:.1f}%")
    
    # Positive days statistics
    if corr_positive is not None and beta_positive is not None:
        implied_move_pos = beta_positive * 10
        text_parts.append(
            f"📈 {a} positive days ({n_positive} days): corr={corr_positive*100:.1f}%, "
            f"beta={beta_positive:.2f} (if {a} +10%, {b} ≈ {implied_move_pos:+.1f}%)"
        )
    elif corr_positive is not None:
        text_parts.append(
            f"📈 {a} positive days ({n_positive} days): corr={corr_positive*100:.1f}%"
        )
    
    # Negative days statistics
    if corr_negative is not None and beta_negative is not None:
        # When coin A goes down 10%, coin B should also go down (negative move)
        implied_move_neg = beta_negative * -10
        text_parts.append(
            f"📉 {a} negative days ({n_negative} days): corr={corr_negative*100:.1f}%, "
            f"beta={beta_negative:.2f} (if {a} -10%, {b} ≈ {implied_move_neg:+.1f}%)"
        )
    elif corr_negative is not None:
        text_parts.append(
            f"📉 {a} negative days ({n_negative} days): corr={corr_negative*100:.1f}%"
        )
    
    text = f"Correlation (daily returns) — {a} vs {b} | " + " | ".join(text_parts)
    
    return text, scat

