"""Generate static HTML dashboard from latest data."""
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

from src.data_manager import DataManager
from src.utils import setup_logger

logger = setup_logger(__name__)


def generate_static_dashboard():
    """Generate static HTML dashboard with latest data."""
    # Load data
    logger.info("Loading data...")
    data_manager = DataManager()
    data_manager.load_all_data()
    
    # Create output directory
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    # Generate HTML
    html_content = generate_html(data_manager)
    
    # Write HTML file
    index_path = docs_dir / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    logger.info(f"Static dashboard generated at {index_path}")
    
    # Also save data as JSON for potential future use
    data_json = {
        "last_updated": pd.Timestamp.now().isoformat(),
        "coins_loaded": len(data_manager.series),
        "available_coins": sorted(data_manager.series.keys())
    }
    
    with open(docs_dir / "data.json", "w", encoding="utf-8") as f:
        json.dump(data_json, f, indent=2)


def generate_html(data_manager: DataManager) -> str:
    """Generate HTML content with embedded charts."""
    df_raw = data_manager.df_raw
    
    # Create normalized view chart
    from src.data.transformer import normalize_start100, apply_smoothing
    from src.visualization import series_for_symbol
    
    # Apply smoothing
    df_smoothed = apply_smoothing(df_raw, "7D SMA")
    
    # Normalize to start at 100 (same as main app)
    df_normalized = normalize_start100(df_smoothed)
    
    # Chart 1: BTC and ETH normalized view
    fig_btc_eth = go.Figure()
    
    for coin in ["BTC", "ETH"]:
        if coin not in df_normalized.columns:
            logger.warning(f"{coin}: Not found in df_normalized.columns")
            continue
        
        # Extract series from normalized dataframe
        data_series = df_normalized[coin].copy()
        
        # Find first non-NaN, non-zero value (this should be the baseline = 100)
        mask_valid = (~pd.isna(data_series)) & (data_series != 0)
        if not mask_valid.any():
            logger.warning(f"{coin}: No valid (non-zero, non-NaN) data found")
            continue
        
        # Get first valid index
        first_valid_idx = data_series[mask_valid].index[0]
        first_valid_val = data_series.loc[first_valid_idx]
        
        # Filter: only keep data from first_valid_idx onwards, and exclude zeros
        valid_data = data_series.loc[data_series.index >= first_valid_idx]
        valid_data = valid_data[valid_data != 0].dropna()
        
        if valid_data.empty:
            logger.warning(f"{coin}: No valid data after filtering")
            continue
        
        # Ensure first value is exactly 100 (re-normalize if needed)
        first_val = valid_data.iloc[0]
        if abs(first_val - 100) > 0.01:
            logger.info(f"{coin}: Re-normalizing from {first_val:.2f} to 100")
            valid_data = (valid_data / first_val) * 100
        
        # Final check: first value must be 100
        if abs(valid_data.iloc[0] - 100) > 0.01:
            logger.error(f"{coin}: First value is {valid_data.iloc[0]:.2f}, expected 100.0")
            # Force it to 100
            valid_data.iloc[0] = 100.0
        
        logger.info(f"{coin}: Added trace with {len(valid_data)} points, first={valid_data.iloc[0]:.2f}")
        
        fig_btc_eth.add_trace(go.Scatter(
            x=valid_data.index,
            y=valid_data.values,
            mode="lines",
            name=coin,
            line=dict(width=3)
        ))
    
    fig_btc_eth.update_layout(
        title="BTC vs ETH - Normalized Market Cap (Indexed to 100)",
        xaxis_title="Date",
        yaxis_title="Index (100 = first value)",
        hovermode="closest",
        height=600,
        template="plotly_white",
        legend=dict(x=0.02, y=0.98)
    )
    
    # Convert figure to JSON
    fig_btc_eth_json = json.dumps(fig_btc_eth, cls=PlotlyJSONEncoder)
    
    # Generate HTML - Simple page with just the chart
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BTC vs ETH - Normalized Market Cap</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .chart-container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <div class="chart-container">
        <div id="chart-btc-eth"></div>
    </div>
    
    <script>
        var figureBtcEth = """ + fig_btc_eth_json + """;
        Plotly.newPlot('chart-btc-eth', figureBtcEth.data, figureBtcEth.layout, {responsive: true});
    </script>
</body>
</html>
"""
    
    return html


if __name__ == "__main__":
    generate_static_dashboard()

