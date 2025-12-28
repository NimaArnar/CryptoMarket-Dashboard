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
        title="BTC vs ETH - Normalized Market Cap (100 = first value)",
        xaxis_title="Date",
        yaxis_title="Index (100 = first value)",
        hovermode="closest",
        height=500,
        template="plotly_white",
        legend=dict(x=0.02, y=0.98)
    )
    
    # Chart 2: Correlation scatter plot (BTC vs ETH returns)
    fig_corr = None
    corr_value = None
    beta_value = None
    
    if "BTC" in df_normalized.columns and "ETH" in df_normalized.columns:
        # Use normalized data (same as main app for correlation)
        s_btc = df_normalized["BTC"].dropna()
        s_eth = df_normalized["ETH"].dropna()
        
        # Remove zeros at the start
        non_zero_mask_btc = s_btc != 0
        if non_zero_mask_btc.any():
            first_non_zero_idx_btc = s_btc[non_zero_mask_btc].index[0]
            s_btc = s_btc.loc[s_btc.index >= first_non_zero_idx_btc]
        
        non_zero_mask_eth = s_eth != 0
        if non_zero_mask_eth.any():
            first_non_zero_idx_eth = s_eth[non_zero_mask_eth].index[0]
            s_eth = s_eth.loc[s_eth.index >= first_non_zero_idx_eth]
        
        # Align by date (inner join)
        df_aligned = pd.concat([s_btc.rename("BTC"), s_eth.rename("ETH")], axis=1, join="inner").dropna()
        
        if df_aligned.shape[0] >= 10:
            # Calculate returns from normalized data
            rets = df_aligned.pct_change().dropna()
            
            if not rets.empty and len(rets) > 0:
                # Calculate correlation
                corr_value = rets["BTC"].corr(rets["ETH"])
                
                # Calculate beta
                if rets["BTC"].var() > 0:
                    beta_value = rets["ETH"].cov(rets["BTC"]) / rets["BTC"].var()
                
                # Create scatter plot
                fig_corr = go.Figure()
                fig_corr.add_trace(go.Scatter(
                    x=rets["BTC"] * 100,  # Convert to percentage
                    y=rets["ETH"] * 100,  # Convert to percentage
                    mode="markers",
                    name="Daily Returns",
                    marker=dict(size=6, opacity=0.6, color="rgba(31, 119, 180, 0.6)")
                ))
                
                corr_percent = corr_value * 100 if corr_value else 0
                fig_corr.update_layout(
                    title=f"BTC vs ETH Correlation - Returns Scatter (corr={corr_percent:.1f}%)",
                    xaxis_title="BTC Daily Return (%)",
                    yaxis_title="ETH Daily Return (%)",
                    xaxis=dict(tickformat=".1%"),
                    yaxis=dict(tickformat=".1%"),
                    height=500,
                    template="plotly_white",
                    hovermode="closest"
                )
    
    # Convert figures to JSON
    fig_btc_eth_json = json.dumps(fig_btc_eth, cls=PlotlyJSONEncoder)
    fig_corr_json = json.dumps(fig_corr, cls=PlotlyJSONEncoder) if fig_corr else None
    
    # Get latest market cap data
    latest_data = df_raw.iloc[-1].to_dict()
    latest_date = df_raw.index[-1].strftime("%Y-%m-%d")
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Market Cap Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .info {{
            background-color: #e8f4f8;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .chart-container {{
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .data-table {{
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #6c757d;
            font-size: 14px;
        }}
        .note {{
            background-color: #fff3cd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #ffc107;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Crypto Market Cap Dashboard</h1>
        <p>Static snapshot - Updated daily via GitHub Actions</p>
    </div>
    
    <div class="note">
        <strong>ℹ️ Note:</strong> This is a static snapshot. For the full interactive dashboard with real-time updates, 
        please visit the <a href="https://github.com/NimaArnar/CryptoMarket-Dashboard" target="_blank">GitHub repository</a> 
        and run it locally or deploy it to a cloud platform.
    </div>
    
    <div class="info">
        <p><strong>Last Updated:</strong> {latest_date}</p>
        <p><strong>Coins Tracked:</strong> {len(data_manager.series)}</p>
    </div>
    
    <div class="chart-container">
        <h2 style="margin-top: 0;">BTC vs ETH - Market Cap Comparison</h2>
        <div id="chart-btc-eth"></div>
    </div>
"""
    
    # Add correlation chart if available
    if fig_corr_json:
        corr_display = f"{corr_value*100:.1f}%" if corr_value else "N/A"
        beta_display = f"{beta_value:.2f}" if beta_value else "N/A"
        html += f"""
    <div class="chart-container">
        <h2 style="margin-top: 0;">BTC vs ETH - Correlation Analysis</h2>
        <p style="margin-bottom: 15px; color: #495057;">
            <strong>Correlation:</strong> {corr_display} | 
            <strong>Beta:</strong> {beta_display}
        </p>
        <div id="chart-corr"></div>
    </div>
"""
    
    html += """
    <div class="data-table">
        <h2>Latest Market Cap Data</h2>
        <table>
            <thead>
                <tr>
                    <th>Coin</th>
                    <th>Market Cap (USD)</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add table rows
    for coin, mc in sorted(latest_data.items(), key=lambda x: x[1] or 0, reverse=True)[:20]:
        if mc and pd.notna(mc) and mc > 0:
            mc_formatted = f"${mc:,.0f}" if mc >= 1000 else f"${mc:,.2f}"
            html += f"                <tr><td>{coin}</td><td>{mc_formatted}</td></tr>\n"
    
    html += """            </tbody>
        </table>
    </div>
    
    <div class="footer">
        <p>Generated automatically by GitHub Actions | 
        <a href="https://github.com/NimaArnar/CryptoMarket-Dashboard" target="_blank">View Source</a></p>
    </div>
    
    <script>
        var figureBtcEth = """ + fig_btc_eth_json + """;
        Plotly.newPlot('chart-btc-eth', figureBtcEth.data, figureBtcEth.layout, {responsive: true});
"""
    
    if fig_corr_json:
        html += """
        var figureCorr = """ + fig_corr_json + """;
        Plotly.newPlot('chart-corr', figureCorr.data, figureCorr.layout, {responsive: true});
"""
    
    html += """    </script>
</body>
</html>
"""
    
    return html


if __name__ == "__main__":
    generate_static_dashboard()

