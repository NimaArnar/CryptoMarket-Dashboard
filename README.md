# Crypto Market Cap Dashboard

An interactive web dashboard for visualizing cryptocurrency market cap data using CoinGecko API.

## Features

- 📊 **Interactive Charts**: View market cap trends with multiple smoothing options (7D SMA, 14D EMA, 30D SMA)
- 📈 **Normalized Views**: Compare coins using normalized indices (linear and log scale)
- 🔍 **Correlation Analysis**: Scatter plots showing returns correlation between pairs of coins with beta calculation
- 📋 **Latest Data Table**: View latest price, Q supply, and market cap for all coins in a sortable, filterable table
- 🎯 **Smart Data Cleaning**: Automatic detection and correction of corrupted circulating supply data
- ⚡ **Fast Data Loading**: Async parallel fetching for faster startup times
- 💾 **Caching**: 24-hour cache to minimize API calls
- 📁 **Excel Export**: Export market cap data to Excel files
- 🎨 **Modern UI**: Clean, intuitive interface with tabbed navigation, improved button styling and larger charts
- ✅ **Bulk Selection**: Select All/Unselect All buttons for quick coin selection
- 🎯 **Active Button Indicators**: Selected buttons highlighted with blue color for clear visual feedback
- 📊 **Smart Correlation Display**: Correlation scatter chart automatically hidden when correlation is off

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

### Quick Start: Web Version (GitHub Pages)

A simplified interactive web version is available on GitHub Pages:
- **Live Demo**: [https://nimaarnar.github.io/CryptoMarket-Dashboard/](https://nimaarnar.github.io/CryptoMarket-Dashboard/)
- **Features**: BTC/ETH charts, market cap table, smoothing, views, and correlation analysis
- **No Installation Required**: Runs entirely in your browser using JavaScript
- **Note**: This is a sample version focusing on BTC and ETH. The full Python application supports 25+ coins with advanced features.

### Telegram Bot (NEW! 🤖)

Control your dashboard remotely via Telegram! The bot allows you to:
- **Start/Stop Dashboard**: Control your dashboard server remotely
- **Multi-User Support**: Per-user dashboard ownership tracking
- **Real-Time Data Queries**: Get prices, market caps, and coin information
- **Network Access**: Dashboard accessible from any device on your network
- **Interactive Buttons**: Navigate commands with inline keyboards
- **User Action Tracking**: Comprehensive logging of all bot interactions
- **Status Monitoring**: Check dashboard status with ownership information
- **Progress Updates**: Real-time progress indicators during dashboard startup

**Quick Start:**
1. Get a bot token from [@BotFather](https://t.me/botfather)
2. Set environment variable: `$env:TELEGRAM_BOT_TOKEN="your-token"`
3. Run: `python telegram_bot.py`
4. Send `/start` to your bot in Telegram

**Key Features:**
- **Dashboard Control**: Start/stop dashboard remotely with per-user ownership tracking
- **Instant Price Queries**: Get real-time prices without dashboard running (`/price BTC`)
- **Timeframe Summaries**: 1d/1w/1m/1y price and market cap summaries (`/summary BTC 1m`)
- **Chart Images**: Generate dual-axis logarithmic charts (price + indexed) for 1w/1m/1y (`/chart BTC 1w`)
- **Coin Information**: Detailed coin data including supply, indexed price, all-time high/low (`/info BTC`)

**Full Documentation:** See [TELEGRAM_BOT.md](TELEGRAM_BOT.md) for complete setup and usage guide.

### Basic Usage (Free API) - Full Python Application

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
├── main.py                          # Entry point (Python application)
├── telegram_bot.py                  # Telegram bot for remote control
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── TELEGRAM_BOT.md                  # Telegram bot complete guide
├── DEPLOYMENT.md                    # Deployment guide
├── .gitignore                      # Git ignore rules
├── scripts/                         # Utility scripts
│   ├── set_bot_description.py      # Set bot description via API
│   └── generate_static_dashboard.py # Generate static dashboard
├── docs/                            # GitHub Pages web version
│   └── index.html                  # Interactive JavaScript dashboard
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

### Correlation Analysis

- **Off**: Correlation analysis disabled (scatter chart hidden)
- **Returns**: Calculate correlation from daily returns (percentage changes)
  - Shows **overall correlation** and beta across all days
  - Shows **split analysis** when 2 coins are selected:
    - **Positive days**: Correlation and beta for days when the first selected coin had positive returns
    - **Negative days**: Correlation and beta for days when the first selected coin had negative returns
    - Example output:
      ```
      Overall: corr=81.6%, beta=1.47 (if BTC +10%, ETH ≈ +14.7%)
      📈 BTC positive days (185 days): corr=67.2%, beta=1.47
      📉 BTC negative days (179 days): corr=78.4%, beta=1.68 (if BTC -10%, ETH ≈ -16.8%)
      ```
  - **Scatter Plot**: Green markers for positive days, red markers for negative days
  - **Beta Calculation**: Shows how much coin B moves when coin A moves 1%
  - **Selection Order Matters**: Selecting BTC then ETH gives beta of ETH relative to BTC. Selecting ETH then BTC gives beta of BTC relative to ETH
  - Correlation uses market cap data with the selected view transformation and smoothing
  - **Note**: Subset correlations (positive/negative days) can differ from overall correlation - this is mathematically valid and reflects different relationship structures in different market conditions

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

### Latest Features (v2.3)
- **GitHub Pages Deployment**: Added interactive web version deployed on GitHub Pages
  - Simplified JavaScript version focusing on BTC and ETH
  - All core features: smoothing, views, correlation analysis
  - Client-side caching for faster loads
  - No installation required - runs in browser
  - Available at: [https://nimaarnar.github.io/CryptoMarket-Dashboard/](https://nimaarnar.github.io/CryptoMarket-Dashboard/)

### Previous Features (v2.2)
- **Split Correlation Analysis**: New feature that calculates separate correlation and beta for positive vs negative return days
  - When 2 coins are selected, shows overall correlation plus correlation for days when the first coin was positive vs negative
  - Scatter plot uses green markers for positive days and red markers for negative days
  - Reveals how correlation structure differs in up vs down markets
- **USDT.D Correlation Fix**: Fixed USDT.D correlation calculation to use raw market cap data instead of normalized data
- **Enhanced Validation**: Added NaN checks and minimum data validation for more robust correlation calculations
- **Improved Documentation**: Added explanatory comments about subset correlations and their mathematical validity

### Previous Features (v2.1)
- **Active Button Styling**: Selected buttons (Smoothing, View, Correlation) now highlighted in blue for clear visual feedback
- **Smart Correlation Display**: Correlation scatter chart automatically hidden when correlation mode is set to "Off"
- **Improved Tab Design**: Tabs now have rounded corners and smaller, more compact size
- **Selection Order Preservation**: Beta calculation now respects the order coins are selected (BTC then ETH vs ETH then BTC gives different beta)
- **Correlation Calculation Fix**: Correlation now correctly uses market cap data with view transformation and selected smoothing

### Previous Features (v2.0)
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
- Fixed correlation calculation to use market cap data with view transformation (not raw data)
- Fixed selection order preservation for consistent beta calculation
- Removed levels correlation mode (now only returns correlation available)

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

