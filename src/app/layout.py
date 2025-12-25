"""Dash application layout."""
from dash import dcc, html

from src.constants import DEFAULT_CORR_MODE, DEFAULT_GROUP, DEFAULT_SMOOTHING, DEFAULT_VIEW, DOM_SYM


def create_layout(coin_status: dict, default_selected: list) -> html.Div:
    """
    Create the Dash application layout.
    
    Args:
        coin_status: Dictionary with coin loading status
        default_selected: List of default selected symbols
    
    Returns:
        HTML Div containing the full layout
    """
    return html.Div(
        style={"fontFamily": "Arial", "padding": "12px"},
        children=[
            html.H3("1Y Chart — Group/Smoothing/View + Correlation + Returns Scatter"),
            
            _create_coin_status_div(coin_status),
            
            dcc.Store(
                id="state",
                data={
                    "group": DEFAULT_GROUP,
                    "smoothing": DEFAULT_SMOOTHING,
                    "view": DEFAULT_VIEW,
                    "corr_mode": DEFAULT_CORR_MODE
                },
            ),
            dcc.Store(id="selected", data=default_selected),
            dcc.Store(id="order", data=[]),
            
            _create_controls_div(),
            
            dcc.Graph(id="chart", style={"height": "62vh"}),
            
            html.Div(
                style={"marginTop": "10px", "fontWeight": "bold"},
                children="Returns scatter (Coin A vs Coin B)"
            ),
            dcc.Graph(id="scatter", style={"height": "32vh"}),
            
            html.Div(
                style={"marginTop": "8px", "color": "#666"},
                children="Tip: Use legend to toggle coins. Correlation + scatter appear when exactly 2 symbols are selected."
            )
        ]
    )


def _create_coin_status_div(coin_status: dict) -> html.Div:
    """Create the coin status display div."""
    children = [
        html.Span(
            f"✅ Loaded: {coin_status['total_loaded']}/{coin_status['total_expected']} coins",
            style={"color": "#28a745", "fontWeight": "bold"}
        ),
        html.Br(),
        html.Span("Available: ", style={"fontWeight": "bold"}),
        html.Span(
            ", ".join(coin_status['available'][:10]) +
            (f" (+{len(coin_status['available']) - 10} more)" if len(coin_status['available']) > 10 else ""),
            style={"color": "#333"}
        ),
    ]
    
    if coin_status['missing']:
        children.extend([
            html.Br(),
            html.Span("⚠️ Missing: ", style={"fontWeight": "bold", "color": "#dc3545"}),
            html.Span(", ".join(coin_status['missing']), style={"color": "#dc3545"}),
        ])
    
    return html.Div(
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
        children=children
    )


def _create_controls_div() -> html.Div:
    """Create the controls section with buttons."""
    return html.Div(
        style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
        children=[
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
        ]
    )

