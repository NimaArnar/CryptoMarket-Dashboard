# Feature: Correlation between 2 coins in Telegram bot (Numerical)

## Description
Add a command to the Telegram bot that calculates and displays the numerical correlation between two coins.

## Command Format
```
/corr <COIN1> <COIN2>
```

## Example Usage
```
User: /corr BTC ETH
Bot: 📊 Correlation Analysis: BTC vs ETH
     📈 Overall Correlation: 0.816 (81.6%)
     📊 Beta: 1.47
     💡 If BTC moves +10%, ETH typically moves +14.7%
```

## Implementation Details
- Use existing correlation calculation from dashboard (`src/app/callbacks.py`)
- Support returns correlation mode
- Calculate beta coefficient
- Show correlation percentage
- Handle cases where coins don't have enough overlapping data

## Technical Notes
- Reuse correlation logic from `create_returns_scatter` function
- Use market cap data with selected smoothing (if applicable)
- Minimum overlapping days: 10 (from `MIN_CORR_DAYS` config)
- Return clear error if insufficient data

## Priority
Medium

## Labels
enhancement, feature, telegram-bot

