# Crypto Market Cap Dashboard

An interactive web dashboard for visualizing cryptocurrency market cap data using CoinGecko API.

## Features

- 📊 **Interactive Charts**: View market cap trends with multiple smoothing options (7D SMA, 14D EMA, 30D SMA)
- 📈 **Normalized Views**: Compare coins using normalized indices (linear and log scale)
- 🔍 **Correlation Analysis**: Scatter plots showing returns correlation between pairs of coins
- 📋 **Latest Data Table**: View latest price, Q supply, and market cap for all coins in a sortable, filterable table
- 🎯 **Smart Data Cleaning**: Automatic detection and correction of corrupted circulating supply data
- ⚡ **Fast Data Loading**: Async parallel fetching for faster startup times
- 💾 **Caching**: 24-hour cache to minimize API calls
- 📁 **Excel Export**: Export market cap data to Excel files
- 🎨 **Modern UI**: Clean, intuitive interface with tabbed navigation, improved button styling and larger charts
- ✅ **Bulk Selection**: Select All/Unselect All buttons for quick coin selection

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
python main.py
```

**Windows CMD:**
```cmd
set COINGECKO_API_KEY=your-api-key-here
python main.py
```

**Linux/Mac:**
```bash
export COINGECKO_API_KEY="your-api-key-here"
python main.py
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

python main.py
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

This ensures market cap accurately reflects price movements even when API supply data is corrupted.

### Tabs

- **Charts Tab**: Interactive charts with full controls (Smoothing, View, Correlation, Selection)
- **Latest Data Tab**: Table showing latest Price, Q Supply, and Market Cap for all coins
  - Sortable columns (numeric sorting)
  - Filterable/searchable
  - Pagination (20 rows per page)
  - Controls panel automatically hidden on this tab

### Views

- **Market Cap (Log)**: Raw market cap values on logarithmic scale
- **Normalized (Linear)**: All coins start at 100, linear scale
- **Normalized (Log)**: All coins start at 100, logarithmic scale

### Smoothing Options

- **No smoothing**: Raw daily data
- **7D SMA**: 7-day simple moving average
- **14D EMA**: 14-day exponential moving average
- **30D SMA**: 30-day simple moving average

### Selection Controls

- **Select All**: Select all coins available in the current view
- **Unselect All**: Deselect all coins
- **Legend Toggle**: Click on legend items to toggle individual coins on/off

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

## Recent Updates

### Latest Features (v2.0)
- **Tabbed Interface**: Added Charts and Latest Data tabs for better organization
- **Latest Data Table**: New tab showing Price, Q Supply, and Market Cap for all coins with sorting and filtering
- **Bulk Selection**: Added Select All/Unselect All buttons for quick coin selection
- **Smart Controls**: Controls panel automatically hides on Latest Data tab
- **Improved Table Sorting**: Fixed numeric sorting in data table (works correctly with formatted values)

### Removed Coins
- **DYDX**: Removed due to corrupted API data
- **IMX**: Removed due to corrupted API data
- Total coins: 25 (down from 27)

### UI Improvements
- **Modern Button Design**: Clean, modern button styling with better spacing and visual hierarchy
- **Larger Charts**: Increased chart height to 75vh for better data visibility
- **Improved Layout**: Better color scheme, spacing, and overall visual design
- **Simplified Controls**: Streamlined control panel with organized sections
- **Better Error Handling**: Improved logging and error messages for debugging

### Bug Fixes
- Fixed coin count display when switching between views
- Fixed chart rendering issues on initial page load
- Improved selected coin filtering to match current view/order
- Fixed table sorting to work with numeric values instead of formatted strings

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

