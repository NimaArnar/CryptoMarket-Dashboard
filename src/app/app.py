"""Main Dash application setup."""
import os
from dash import Dash

from src.app import callbacks, layout
from src.config import DASH_DEBUG, DASH_PORT
from src.constants import DEFAULT_GROUP, DOM_SYM
from src.data_manager import DataManager
from src.utils import setup_logger

logger = setup_logger(__name__)


def create_app(data_manager: DataManager) -> Dash:
    """
    Create and configure the Dash application.
    
    Args:
        data_manager: DataManager instance with loaded data
    
    Returns:
        Configured Dash application
    """
    app = Dash(__name__)
    
    # Compute default selected coins
    default_selected = ["BTC", "ETH", "DOGE", "FART"]
    if "SKY" in data_manager.df_raw.columns:
        default_selected.append("SKY")
    if "USDT" in data_manager.df_raw.columns:
        default_selected.append(DOM_SYM)
    
    # Filter to only available symbols
    default_selected = [s for s in default_selected if s in data_manager.symbols_all]
    if not default_selected:
        default_selected = data_manager.symbols_all[:min(5, len(data_manager.symbols_all))]
    
    # Set layout
    app.layout = layout.create_layout(data_manager.coin_status, default_selected)
    
    # Register callbacks
    callbacks.register_callbacks(app, data_manager)
    
    return app


def run_app(app: Dash) -> None:
    """Run the Dash application."""
    # Allow binding to 0.0.0.0 for network access via DASH_HOST env var
    # Default to 0.0.0.0 if PORT is set (cloud deployment), otherwise check DASH_HOST
    if os.getenv("PORT"):
        host = "0.0.0.0"
    elif os.getenv("DASH_HOST"):
        host = os.getenv("DASH_HOST")
    else:
        host = "127.0.0.1"  # Default to localhost only
    
    startup_msg = f"Starting Dash… open http://{host}:{DASH_PORT}/"
    logger.info(startup_msg)
    # Log file path is set in utils.setup_logger
    app.run(debug=DASH_DEBUG, host=host, port=DASH_PORT)

