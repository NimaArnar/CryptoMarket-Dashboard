"""Quick test to verify buttons are created correctly."""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import (
    create_main_keyboard,
    create_dashboard_keyboard,
    create_data_keyboard,
    create_quick_actions_keyboard
)

print("Testing keyboard creation...")
print()

# Test main keyboard
main_kb = create_main_keyboard()
print("[OK] Main keyboard created")
print(f"  Buttons: {len(main_kb.inline_keyboard)} rows")
for i, row in enumerate(main_kb.inline_keyboard):
    print(f"    Row {i+1}: {len(row)} buttons")

# Test dashboard keyboard
dash_kb = create_dashboard_keyboard()
print("[OK] Dashboard keyboard created")
print(f"  Buttons: {len(dash_kb.inline_keyboard)} rows")

# Test data keyboard
data_kb = create_data_keyboard()
print("[OK] Data keyboard created")
print(f"  Buttons: {len(data_kb.inline_keyboard)} rows")

# Test quick actions keyboard
quick_kb = create_quick_actions_keyboard()
print("[OK] Quick actions keyboard created")
print(f"  Buttons: {len(quick_kb.inline_keyboard)} rows")

print()
print("All keyboards created successfully!")
print()
print("To see the buttons in Telegram:")
print("1. Make sure the bot is running")
print("2. Send /start to your bot")
print("3. You should see buttons below the message")

