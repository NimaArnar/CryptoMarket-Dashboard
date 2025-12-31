"""Telegram bot for Crypto Market Dashboard control."""
import os
import subprocess
import threading
import time
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config import DASH_PORT
from src.utils import setup_logger

logger = setup_logger(__name__)

# Global variable to track if dashboard is running
dashboard_process: Optional[subprocess.Popen] = None
dashboard_thread: Optional[threading.Thread] = None

# Telegram Bot Token (set via environment variable)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_message = (
        "🤖 *Crypto Market Dashboard Bot*\n\n"
        "Available commands:\n"
        "/start - Show this message\n"
        "/run - Start the dashboard\n"
        "/stop - Stop the dashboard\n"
        "/status - Check dashboard status\n"
        "/help - Show help message"
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "📚 *Help*\n\n"
        "*/run* - Start the dashboard server\n"
        "*/stop* - Stop the dashboard server\n"
        "*/status* - Check if dashboard is running\n"
        "*/start* - Show welcome message\n\n"
        f"Dashboard runs on: http://127.0.0.1:{DASH_PORT}/"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /run command - start the dashboard."""
    global dashboard_process, dashboard_thread
    
    if dashboard_process and dashboard_process.poll() is None:
        await update.message.reply_text("⚠️ Dashboard is already running!")
        return
    
    try:
        await update.message.reply_text("🔄 Starting dashboard...")
        
        # Start dashboard in a separate process
        dashboard_process = subprocess.Popen(
            ["python", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment to check if it started successfully
        time.sleep(2)
        
        if dashboard_process.poll() is None:
            await update.message.reply_text(
                f"✅ Dashboard started successfully!\n"
                f"🌐 Access at: http://127.0.0.1:{DASH_PORT}/"
            )
        else:
            # Process exited immediately - there was an error
            stderr = dashboard_process.stderr.read() if dashboard_process.stderr else "Unknown error"
            await update.message.reply_text(
                f"❌ Failed to start dashboard:\n{stderr[:500]}"
            )
            dashboard_process = None
            
    except Exception as e:
        logger.error(f"Error starting dashboard: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop command - stop the dashboard."""
    global dashboard_process
    
    if not dashboard_process or dashboard_process.poll() is not None:
        await update.message.reply_text("⚠️ Dashboard is not running!")
        return
    
    try:
        dashboard_process.terminate()
        dashboard_process.wait(timeout=10)
        dashboard_process = None
        await update.message.reply_text("🛑 Dashboard stopped successfully!")
    except subprocess.TimeoutExpired:
        dashboard_process.kill()
        dashboard_process = None
        await update.message.reply_text("🛑 Dashboard force stopped!")
    except Exception as e:
        logger.error(f"Error stopping dashboard: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - check dashboard status."""
    global dashboard_process
    
    if dashboard_process and dashboard_process.poll() is None:
        status_text = (
            "✅ *Dashboard Status: RUNNING*\n\n"
            f"🌐 URL: http://127.0.0.1:{DASH_PORT}/\n"
            f"📊 Process ID: {dashboard_process.pid}"
        )
    else:
        status_text = "❌ *Dashboard Status: STOPPED*"
    
    await update.message.reply_text(status_text, parse_mode="Markdown")


def main() -> None:
    """Start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        logger.error("Please set it with: export TELEGRAM_BOT_TOKEN='your-token'")
        return
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("run", run_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Start the bot
    logger.info("Starting Telegram bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

