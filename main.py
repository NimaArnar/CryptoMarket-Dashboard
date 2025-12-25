"""Main entry point for the Crypto Market Cap Dashboard."""
from src.app.app import create_app, run_app
from src.data_manager import DataManager
from src.utils import check_aiohttp, setup_logger

logger = setup_logger(__name__)


def main():
    """Main function to load data and start the dashboard."""
    # Check aiohttp availability
    if not check_aiohttp():
        logger.warning(
            "aiohttp not installed - async fetching will be disabled. "
            "Install with: pip install aiohttp"
        )
    
    # Load all data
    data_manager = DataManager()
    data_manager.load_all_data()
    
    # Create and run app
    app = create_app(data_manager)
    run_app(app)


if __name__ == "__main__":
    main()

