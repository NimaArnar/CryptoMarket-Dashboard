# Telegram Bot Features

## ✅ Implemented Features

### Dashboard Control
- `/run` - Start the dashboard server
- `/stop` - Stop the dashboard server
- `/status` - Check if dashboard is running

### Data Queries
- `/price <SYMBOL>` - Get latest price for a coin (e.g., `/price BTC`)
- `/marketcap <SYMBOL>` - Get market cap for a coin (e.g., `/marketcap ETH`)
- `/coins` - List all available coins grouped by category
- `/latest` - Get latest prices for all coins (top 10 by market cap)
- `/info <SYMBOL>` - Get detailed information for a coin

## 🚀 Planned Features

### Charts & Images
- [ ] `/chart <SYMBOL1> <SYMBOL2>` - Send chart image of selected coins
- [ ] `/correlation <SYMBOL1> <SYMBOL2>` - Get correlation data and scatter plot
- [ ] `/export` - Send Excel file with market cap data

### Alerts & Notifications
- [ ] `/alert <SYMBOL> <OPERATOR> <PRICE>` - Set price alerts (e.g., `/alert BTC > 50000`)
- [ ] `/alerts` - List all active alerts
- [ ] `/notify on/off` - Enable/disable notifications

### Advanced Analysis
- [ ] `/compare <SYMBOL1> <SYMBOL2> ...` - Compare multiple coins
- [ ] `/trend <SYMBOL>` - Show price trend analysis
- [ ] `/corr <SYMBOL1> <SYMBOL2>` - Correlation analysis with beta calculation
- [ ] `/stats` - Show overall statistics

### Data Management
- [ ] `/refresh` - Force refresh data from API
- [ ] `/cache` - Check cache status and age
- [ ] `/export <SYMBOL>` - Export specific coin data

## 📝 Usage Examples

```
/price BTC          # Get BTC price
/marketcap ETH      # Get ETH market cap
/coins              # List all coins
/latest             # Latest prices
/info DOGE          # Detailed DOGE info
```

## 🔧 Technical Notes

- Data is loaded lazily on first query
- Data manager is cached globally for performance
- All commands handle errors gracefully
- Commands are case-insensitive for coin symbols

