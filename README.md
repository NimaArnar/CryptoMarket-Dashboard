# Crypto Market Cap Dashboard

An interactive web dashboard for visualizing cryptocurrency market cap data using CoinGecko API.

## Features

- 📊 **Interactive Charts**: View market cap trends with multiple smoothing options (7D SMA, 14D EMA, 30D SMA)
- 📈 **Normalized Views**: Compare coins using normalized indices (linear and log scale)
- 🔍 **Correlation Analysis**: Scatter plots showing returns correlation between pairs of coins
- 🎯 **Smart Data Cleaning**: Automatic detection and correction of corrupted circulating supply data
- ⚡ **Fast Data Loading**: Async parallel fetching for faster startup times
- 💾 **Caching**: 24-hour cache to minimize API calls
- 📁 **Excel Export**: Export market cap data to Excel files

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd CryptoDashboard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage (Free API)

```bash
python main.py
```

The dashboard will open at `http://127.0.0.1:8052/`

### With CoinGecko Pro API (Optional)

For higher rate limits, you can use a CoinGecko Pro API key:

**Windows PowerShell:**
```powershell
$env:COINGECKO_API_KEY="your-api-key-here"
python crypto_market_cap_dashboard.py
```

**Windows CMD:**
```cmd
set COINGECKO_API_KEY=your-api-key-here
python crypto_market_cap_dashboard.py
```

**Linux/Mac:**
```bash
export COINGECKO_API_KEY="your-api-key-here"
python crypto_market_cap_dashboard.py
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COINGECKO_API_KEY` | None | CoinGecko Pro API key (optional) |
| `USE_ASYNC_FETCH` | "true" | Enable async parallel fetching |
| `MAX_CONCURRENT_REQUESTS` | "5" | Max concurrent API requests |
| `MIN_CORR_DAYS` | "10" | Minimum overlapping days for correlation |

### Custom Async Configuration

```bash
# Disable async (use sequential fetching)
$env:USE_ASYNC_FETCH="false"

# Increase concurrent requests (if you have Pro API)
$env:MAX_CONCURRENT_REQUESTS="10"

python crypto_market_cap_dashboard.py
```

## Project Structure

```
CryptoMarket-Dashboard/
├── main.py                          # Entry point
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── .gitignore                      # Git ignore rules
├── src/                            # Source code
│   ├── __init__.py
│   ├── config.py                   # Configuration settings
│   ├── constants.py                # Coin definitions and constants
│   ├── utils.py                    # Utility functions
│   ├── data_manager.py             # Data loading and management
│   ├── data/                       # Data processing modules
│   │   ├── __init__.py
│   │   ├── fetcher.py             # API fetching (sync & async)
│   │   ├── cleaner.py             # Q fix and data cleaning
│   │   └── transformer.py        # Smoothing and normalization
│   ├── visualization/              # Visualization modules
│   │   ├── __init__.py
│   │   ├── colors.py              # Color utilities
│   │   └── chart_builder.py       # Chart building functions
│   └── app/                        # Dash application
│       ├── __init__.py
│       ├── app.py                 # App creation and setup
│       ├── layout.py              # Dash layout
│       └── callbacks.py           # Dash callbacks
├── cg_cache/                       # API response cache (auto-generated)
├── logs/                           # Log files (auto-generated)
└── market_caps Data/              # Exported Excel files (auto-generated)
```

## Features Explained

### Data Cleaning

The dashboard automatically detects and fixes corrupted circulating supply data by:
1. Calculating implied supply (Q = Market Cap / Price) for each day
2. Detecting abnormal supply drops (≥30%) that don't match price movements
3. Using the **last correct Q value** before corruption as the baseline
4. Recomputing market cap as: `MC_fixed = Q_baseline × Price` from the break date onward

This ensures market cap accurately reflects price movements even when API supply data is corrupted (e.g., DYDX on April 2-4, 2025).

### Views

- **Market Cap (Log)**: Raw market cap values on logarithmic scale
- **Normalized (Linear)**: All coins start at 100, linear scale
- **Normalized (Log)**: All coins start at 100, logarithmic scale

### Smoothing Options

- **No smoothing**: Raw daily data
- **7D SMA**: 7-day simple moving average
- **14D EMA**: 14-day exponential moving average
- **30D SMA**: 30-day simple moving average

## Logging

Logs are automatically saved to `./logs/dashboard_YYYYMMDD.log`:
- **INFO**: General information (data fetching, successful operations)
- **WARNING**: Non-critical issues (missing coins, cache expiry)
- **ERROR**: Errors that need attention (API failures, data validation issues)

## Troubleshooting

### Async Import Error
If you see: `aiohttp not installed - async fetching will be disabled`
- **Solution**: Install aiohttp: `pip install aiohttp`
- **Alternative**: Set `USE_ASYNC_FETCH=false` to use sequential fetching

### API Rate Limits
If you hit rate limits:
- Use Pro API key: `$env:COINGECKO_API_KEY="your-key"`
- Reduce concurrent requests: `$env:MAX_CONCURRENT_REQUESTS="3"`
- Disable async: `$env:USE_ASYNC_FETCH="false"`

### Chart Not Updating
- Hard refresh browser (Ctrl+F5)
- Clear browser cache
- Check console output for error messages
- Check log file in `./logs/` directory

## Performance

| Feature | Performance |
|---------|-------------|
| Data Fetching | Sequential: ~34s, Async: ~7s (5 concurrent) |
| Cache Duration | 24 hours |
| Startup Time | ~7 seconds (with async, 5 concurrent) |

## Dependencies

- `dash>=2.14.0` - Web framework
- `pandas>=2.0.0` - Data manipulation
- `plotly>=5.17.0` - Interactive charts
- `requests>=2.31.0` - HTTP requests
- `openpyxl>=3.1.0` - Excel export
- `aiohttp>=3.9.0` - Async HTTP (optional but recommended)

## License

This project is open source and available for personal and commercial use.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues or questions, please open an issue on GitHub.

