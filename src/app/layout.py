"""Dash application layout."""
from dash import dcc, html, dash_table

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
        style={
            "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
            "padding": "20px",
            "maxWidth": "100%",
            "backgroundColor": "#f8f9fa"
        },
        children=[
            html.H2(
                "Crypto Market Cap Dashboard",
                style={
                    "marginBottom": "10px",
                    "color": "#2c3e50",
                    "fontWeight": "600"
                }
            ),
            
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
            
            html.Div(id="controls-container", children=_create_controls_div()),
            
            dcc.Tabs(
                id="main-tabs",
                value="chart-tab",
                style={
                    "marginTop": "20px",
                    "borderBottom": "1px solid #dee2e6"
                },
                children=[
                    dcc.Tab(
                        label="Charts",
                        value="chart-tab",
                        style={
                            "padding": "12px 24px",
                            "fontWeight": "500",
                            "fontSize": "15px"
                        },
                        selected_style={
                            "backgroundColor": "#007bff",
                            "color": "#ffffff",
                            "borderTop": "2px solid #007bff"
                        }
                    ),
                    dcc.Tab(
                        label="Latest Data",
                        value="data-tab",
                        style={
                            "padding": "12px 24px",
                            "fontWeight": "500",
                            "fontSize": "15px"
                        },
                        selected_style={
                            "backgroundColor": "#007bff",
                            "color": "#ffffff",
                            "borderTop": "2px solid #007bff"
                        }
                    )
                ]
            ),
            
            html.Div(id="tab-content", style={"marginTop": "20px"}),
            
            html.Div(
                id="scatter-container",
                style={
                    "marginTop": "20px",
                },
                children=[
                    html.Div(
                        style={
                            "fontWeight": "600",
                            "fontSize": "16px",
                            "color": "#2c3e50",
                            "marginBottom": "10px"
                        },
                        children="Returns Scatter (Coin A vs Coin B)"
                    ),
                    dcc.Graph(id="scatter", style={"height": "50vh", "marginTop": "10px"}),
                ]
            ),
            
            html.Div(
                style={
                    "marginTop": "12px",
                    "color": "#6c757d",
                    "fontSize": "13px",
                    "fontStyle": "italic"
                },
                children="💡 Tip: Use legend to toggle coins. Correlation + scatter appear when exactly 2 symbols are selected."
            )
        ]
    )


def _create_coin_status_div(coin_status: dict) -> html.Div:
    """Create the coin status display div."""
    children = [
        html.Span(
            f"✅ Loaded: {coin_status['total_loaded']}/{coin_status['total_expected']} coins",
            style={"color": "#28a745", "fontWeight": "600", "fontSize": "14px"}
        ),
        html.Br(),
        html.Span("Available: ", style={"fontWeight": "600", "fontSize": "14px"}),
        html.Span(
            ", ".join(coin_status['available'][:10]) +
            (f" (+{len(coin_status['available']) - 10} more)" if len(coin_status['available']) > 10 else ""),
            style={"color": "#495057", "fontSize": "14px"}
        ),
    ]
    
    if coin_status['missing']:
        children.extend([
            html.Br(),
            html.Span("⚠️ Missing: ", style={"fontWeight": "600", "color": "#dc3545", "fontSize": "14px"}),
            html.Span(", ".join(coin_status['missing']), style={"color": "#dc3545", "fontSize": "14px"}),
        ])
    
    return html.Div(
        id="coin-status",
        style={
            "marginBottom": "20px",
            "marginTop": "0px",
            "padding": "14px 16px",
            "backgroundColor": "#e8f4f8",
            "border": "1px solid #bee5eb",
            "borderRadius": "8px",
            "fontSize": "14px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.08)"
        },
        children=children
    )


def _create_controls_div() -> html.Div:
    """Create the controls section with buttons."""
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
    
    button_style_hover = {
        **button_style,
        "backgroundColor": "#f8f9fa",
        "borderColor": "#adb5bd",
        "transform": "translateY(-1px)",
        "boxShadow": "0 2px 4px rgba(0,0,0,0.15)"
    }
    
    active_button_style = {
        **button_style,
        "backgroundColor": "#007bff",
        "color": "#ffffff",
        "borderColor": "#007bff",
        "boxShadow": "0 2px 6px rgba(0,123,255,0.3)"
    }
    
    return html.Div(
        style={
            "display": "flex",
            "gap": "24px",
            "flexWrap": "wrap",
            "padding": "16px",
            "backgroundColor": "#ffffff",
            "borderRadius": "8px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.08)",
            "marginBottom": "10px"
        },
        children=[
            html.Div(
                style={"display": "flex", "flexDirection": "column", "gap": "8px"},
                children=[
                    html.Div(
                        "Smoothing",
                        style={
                            "fontWeight": "600",
                            "fontSize": "13px",
                            "color": "#6c757d",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.5px",
                            "marginBottom": "4px"
                        }
                    ),
                    html.Div(
                        style={"display": "flex", "flexWrap": "wrap", "gap": "4px"},
                        children=[
                            html.Button("No smoothing", id="btn-s0", style=button_style),
                            html.Button("7D SMA", id="btn-s7", style=button_style),
                            html.Button("14D EMA", id="btn-s14", style=button_style),
                            html.Button("30D SMA", id="btn-s30", style=button_style),
                        ]
                    )
                ]
            ),
            html.Div(
                style={"display": "flex", "flexDirection": "column", "gap": "8px"},
                children=[
                    html.Div(
                        "View",
                        style={
                            "fontWeight": "600",
                            "fontSize": "13px",
                            "color": "#6c757d",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.5px",
                            "marginBottom": "4px"
                        }
                    ),
                    html.Div(
                        style={"display": "flex", "flexWrap": "wrap", "gap": "4px"},
                        children=[
                            html.Button("Normalized (Linear)", id="btn-view-norm-lin", style=button_style),
                            html.Button("Normalized (Log)", id="btn-view-norm-log", style=button_style),
                            html.Button("Market Cap (Log)", id="btn-view-mc-log", style=button_style),
                        ]
                    )
                ]
            ),
            html.Div(
                style={"display": "flex", "flexDirection": "column", "gap": "8px"},
                children=[
                    html.Div(
                        "Correlation",
                        style={
                            "fontWeight": "600",
                            "fontSize": "13px",
                            "color": "#6c757d",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.5px",
                            "marginBottom": "4px"
                        }
                    ),
                    html.Div(
                        style={"display": "flex", "flexWrap": "wrap", "gap": "4px"},
                        children=[
                            html.Button("Off", id="btn-corr-off", style=button_style),
                            html.Button("Returns", id="btn-corr-ret", style=button_style),
                            html.Button("Levels", id="btn-corr-lvl", style=button_style),
                        ]
                    ),
                    html.Div(
                        id="corr-output",
                        style={
                            "marginTop": "8px",
                            "fontSize": "13px",
                            "color": "#495057",
                            "fontWeight": "500",
                            "padding": "8px 12px",
                            "backgroundColor": "#f8f9fa",
                            "borderRadius": "4px"
                        }
                    ),
                ]
            ),
            html.Div(
                style={"display": "flex", "flexDirection": "column", "gap": "8px"},
                children=[
                    html.Div(
                        "Selection",
                        style={
                            "fontWeight": "600",
                            "fontSize": "13px",
                            "color": "#6c757d",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.5px",
                            "marginBottom": "4px"
                        }
                    ),
                    html.Div(
                        style={"display": "flex", "flexWrap": "wrap", "gap": "4px"},
                        children=[
                            html.Button("Select All", id="btn-select-all", style=button_style),
                            html.Button("Unselect All", id="btn-unselect-all", style=button_style),
                        ]
                    ),
                ]
            ),
        ]
    )

