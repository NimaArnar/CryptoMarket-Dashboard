# Enhancement: Add Info button to menus

## Description
The `/info` command exists and works, but there is no button in any menu to access it. Users must type the command manually or know about it from the command list.

## Current Behavior
- `/info` command works when typed directly (e.g., `/info BTC`)
- No Info button exists in:
  - Main menu
  - Data Queries menu
  - Quick Actions menu
  - Help menu

## Expected Behavior
Add an Info button to the appropriate menu(s) so users can easily access coin information:
- **Data Queries menu**: Add "📊 Coin Info" button that prompts for coin symbol
- **Quick Actions menu**: Consider adding quick info buttons for popular coins (BTC, ETH)

## Suggested Implementation

### Option 1: Add to Data Queries menu
Add a button in `create_data_keyboard()`:
```python
[
    InlineKeyboardButton("📊 Coin Info", callback_data="info_prompt")
]
```

When clicked, prompt user to enter coin symbol or show a selection interface.

### Option 2: Add quick info buttons to Quick Actions
Add buttons like:
```python
[
    InlineKeyboardButton("📊 Info (BTC)", callback_data="info_BTC"),
    InlineKeyboardButton("📊 Info (ETH)", callback_data="info_ETH")
]
```

### Option 3: Both
Add to both menus for maximum accessibility.

## Location
- `telegram_bot.py`:
  - `create_data_keyboard()` function (line ~171)
  - `create_quick_actions_keyboard()` function (line ~195)
  - `button_callback()` function - add handler for info button clicks

## Priority
Medium - User Experience

## Related
- Issue #19: Enhanced `/info` command with comprehensive details
- The `/info` command is already implemented and working

