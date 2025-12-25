"""Utility functions for the dashboard."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import LOG_DIR


def setup_logger(name: str = __name__) -> logging.Logger:
    """Set up and return a logger instance."""
    log_file = LOG_DIR / f"dashboard_{datetime.now().strftime('%Y%m%d')}.log"
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def check_aiohttp() -> bool:
    """Check if aiohttp is available."""
    try:
        import aiohttp
        return True
    except ImportError:
        return False

