"""Script to set the Telegram bot description programmatically."""
import asyncio
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    print("❌ Error: python-telegram-bot is not installed.")
    print("Install it with: pip install python-telegram-bot")
    sys.exit(1)


async def set_bot_description():
    """Set the bot description using Telegram Bot API."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
        print("\nSet it with:")
        print("  Windows PowerShell: $env:TELEGRAM_BOT_TOKEN='your-token'")
        print("  Windows CMD: set TELEGRAM_BOT_TOKEN=your-token")
        print("  Linux/Mac: export TELEGRAM_BOT_TOKEN='your-token'")
        sys.exit(1)
    
    # Read description from file (look in project root, not scripts folder)
    import pathlib
    script_dir = pathlib.Path(__file__).parent
    project_root = script_dir.parent
    description_file = project_root / "BOT_DESCRIPTION.txt"
    
    try:
        with open(description_file, "r", encoding="utf-8") as f:
            description = f.read().strip()
    except FileNotFoundError:
        print("❌ Error: BOT_DESCRIPTION.txt not found.")
        print(f"Expected location: {description_file}")
        print("\nCreate BOT_DESCRIPTION.txt in the project root with your bot description.")
        sys.exit(1)
    
    # Check description length (Telegram limit is 512 characters)
    if len(description) > 512:
        print(f"⚠️  Warning: Description is {len(description)} characters (limit: 512)")
        print("Truncating to 512 characters...")
        description = description[:509] + "..."
    
    try:
        bot = Bot(token=token)
        
        # Set description (async)
        await bot.set_my_description(description=description)
        
        print("✅ Bot description set successfully!")
        print(f"\nDescription ({len(description)} characters):")
        print("-" * 50)
        print(description)
        print("-" * 50)
        
    except TelegramError as e:
        print(f"❌ Error setting bot description: {e}")
        print("\nYou can also set it manually via BotFather:")
        print("1. Open @BotFather in Telegram")
        print("2. Send /mybots")
        print("3. Select your bot")
        print("4. Choose 'Bot Settings' → 'Edit Description'")
        print("5. Paste the description from BOT_DESCRIPTION.txt")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(set_bot_description())

