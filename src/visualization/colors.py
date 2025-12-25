"""Color utilities for chart visualization."""
from plotly.colors import qualitative


# Stable color palette for consistent coin colors
PALETTE = (
    qualitative.Dark24
    + qualitative.Light24
    + qualitative.Alphabet
    + qualitative.Set3
    + qualitative.Pastel
    + qualitative.Safe
)


def color_for(symbol: str) -> str:
    """
    Get a stable color for a symbol.
    
    Uses hash of symbol to ensure same symbol always gets same color.
    
    Args:
        symbol: Coin symbol (e.g., "BTC", "ETH")
    
    Returns:
        Hex color string
    """
    return PALETTE[abs(hash(symbol)) % len(PALETTE)]

