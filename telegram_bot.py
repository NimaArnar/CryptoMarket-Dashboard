"""Telegram bot for Crypto Market Dashboard control."""
import asyncio
import http.client
import os
import socket
import subprocess
import sys
import threading
import time
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.error import Conflict, TimedOut, NetworkError

from src.config import DASH_PORT, PROJECT_ROOT
from src.data_manager import DataManager
from src.utils import setup_logger

logger = setup_logger(__name__)

# User action tracking logger
from datetime import datetime
from pathlib import Path
import logging

USER_LOG_DIR = PROJECT_ROOT / "logs"
USER_LOG_DIR.mkdir(exist_ok=True)
user_action_logger = logging.getLogger("user_actions")
user_action_logger.setLevel(logging.INFO)

# Avoid duplicate handlers
if not user_action_logger.handlers:
    user_log_file = USER_LOG_DIR / f"bot_users_{datetime.now().strftime('%Y%m%d')}.log"
    user_file_handler = logging.FileHandler(user_log_file, encoding='utf-8')
    user_file_handler.setLevel(logging.INFO)
    user_formatter = logging.Formatter(
        '%(asctime)s | %(message)s'
    )
    user_file_handler.setFormatter(user_formatter)
    user_action_logger.addHandler(user_file_handler)
    user_action_logger.propagate = False  # Don't propagate to root logger


def log_user_action(update: Update, action_type: str, action_details: str = ""):
    """
    Log user actions for tracking.
    
    Args:
        update: Telegram Update object
        action_type: Type of action (command, button, etc.)
        action_details: Additional details about the action
    """
    try:
        user = update.effective_user
        user_id = user.id if user else "unknown"
        username = user.username if user and user.username else "no_username"
        first_name = user.first_name if user and user.first_name else "unknown"
        last_name = user.last_name if user and user.last_name else ""
        full_name = f"{first_name} {last_name}".strip()
        
        # Format: UserID | Username | FullName | ActionType | Details
        log_message = (
            f"UserID:{user_id} | "
            f"Username:@{username} | "
            f"Name:{full_name} | "
            f"Action:{action_type} | "
            f"Details:{action_details}"
        )
        
        user_action_logger.info(log_message)
        logger.info(f"User action tracked: {action_type} by @{username} ({user_id})")
    except Exception as e:
        logger.warning(f"Failed to log user action: {e}")

# Lock file for ensuring only one instance runs
LOCK_FILE = PROJECT_ROOT / ".telegram_bot.lock"

# Global variable to track if dashboard is running
dashboard_process: Optional[subprocess.Popen] = None
dashboard_thread: Optional[threading.Thread] = None
data_manager: Optional[DataManager] = None

# Track which user started the dashboard (user_id -> process info)
dashboard_owners: dict[int, dict] = {}  # user_id -> {"process": Popen, "started_at": datetime, "username": str}

# Telegram Bot Token (set via environment variable)
# Strip whitespace to prevent issues with accidental spaces
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def create_main_keyboard() -> InlineKeyboardMarkup:
    """Create the main inline keyboard with command buttons."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Dashboard Control", callback_data="menu_dashboard")
        ],
        [
            InlineKeyboardButton("💰 Data Queries", callback_data="menu_data")
        ],
        [
            InlineKeyboardButton("⚡ Quick Actions", callback_data="menu_quick")
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for dashboard control commands."""
    keyboard = [
        [
            InlineKeyboardButton("▶️ Start Dashboard", callback_data="cmd_run")
        ],
        [
            InlineKeyboardButton("⏹️ Stop Dashboard", callback_data="cmd_stop")
        ],
        [
            InlineKeyboardButton("📊 Status", callback_data="cmd_status")
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_data_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for data query commands."""
    keyboard = [
        [
            InlineKeyboardButton("📋 List All Coins", callback_data="cmd_coins")
        ],
        [
            InlineKeyboardButton("📈 Latest Prices", callback_data="cmd_latest")
        ],
        [
            InlineKeyboardButton("💵 Price (BTC)", callback_data="price_BTC"),
            InlineKeyboardButton("💵 Price (ETH)", callback_data="price_ETH")
        ],
        [
            InlineKeyboardButton("💎 Market Cap (BTC)", callback_data="marketcap_BTC"),
            InlineKeyboardButton("💎 Market Cap (ETH)", callback_data="marketcap_ETH")
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_quick_actions_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for quick actions (popular coins)."""
    keyboard = [
        [
            InlineKeyboardButton("₿ BTC", callback_data="price_BTC"),
            InlineKeyboardButton("Ξ ETH", callback_data="price_ETH"),
            InlineKeyboardButton("BNB", callback_data="price_BNB")
        ],
        [
            InlineKeyboardButton("🔗 LINK", callback_data="price_LINK"),
            InlineKeyboardButton("🔷 ARB", callback_data="price_ARB"),
            InlineKeyboardButton("🔺 AVAX", callback_data="price_AVAX")
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callback queries."""
    query = update.callback_query
    
    if not query:
        logger.error("telegram_bot - button_callback called without callback_query")
        return
    
    try:
        await query.answer()  # Acknowledge the callback
    except Exception as e:
        logger.warning(f"telegram_bot - Error answering callback: {e}")
        # Continue anyway - the callback might have been processed
    
    data = query.data
    
    if not data:
        logger.error("telegram_bot - button_callback called without callback data")
        return
    
    # Log button click for debugging
    logger.info(f"telegram_bot - Button clicked: {data}")
    
    # Track user action
    log_user_action(update, "button_click", data)
    
    # Menu navigation - delete previous button message and send new one to avoid crowding
    chat_id = query.message.chat_id
    
    if data == "menu_main":
        # Delete the message that contains the buttons
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")
        
        welcome_message = (
            "🤖 *Crypto Market Dashboard Bot*\n\n"
            "Select an option from the menu below:"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_message,
            parse_mode="Markdown",
            reply_markup=create_main_keyboard()
        )
        return
    
    elif data == "menu_dashboard":
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="📊 *Dashboard Control*\n\nControl your dashboard server:",
            parse_mode="Markdown",
            reply_markup=create_dashboard_keyboard()
        )
        return
    
    elif data == "menu_data":
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="💰 *Data Queries*\n\nGet real-time cryptocurrency data:",
            parse_mode="Markdown",
            reply_markup=create_data_keyboard()
        )
        return
    
    elif data == "menu_quick":
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚡ *Quick Actions*\n\nQuick access to popular coins:",
            parse_mode="Markdown",
            reply_markup=create_quick_actions_keyboard()
        )
        return
    
    elif data == "help":
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")
        
        help_text = (
            "📚 *Help - Crypto Market Dashboard Bot*\n\n"
            "📊 *Dashboard Control:*\n"
            "*/run* - Start the dashboard server\n"
            "*/stop* - Stop the dashboard server\n"
            "*/status* - Check if dashboard is running\n\n"
            "💰 *Data Queries:*\n"
            "*/price <SYMBOL>* - Get latest price (e.g., /price BTC)\n"
            "*/marketcap <SYMBOL>* - Get market cap (e.g., /marketcap ETH)\n"
            "*/coins* - List all available coins\n"
            "*/latest* - Latest prices for all coins\n"
            "*/info <SYMBOL>* - Detailed coin information\n\n"
            f"🌐 Dashboard: http://127.0.0.1:{DASH_PORT}/"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode="Markdown",
            reply_markup=create_main_keyboard()
        )
        return
    
    # Command execution - create a new Update object with the message from callback query
    # Update objects are immutable, so we need to create a new one
    from telegram import Update as UpdateClass
    
    # Command execution
    if data == "cmd_run":
        # Create new Update with message from callback query
        cmd_update = UpdateClass(update_id=update.update_id, message=query.message)
        await run_command(cmd_update, context)
        return
    
    elif data == "cmd_stop":
        cmd_update = UpdateClass(update_id=update.update_id, message=query.message)
        await stop_command(cmd_update, context)
        return
    
    elif data == "cmd_status":
        cmd_update = UpdateClass(update_id=update.update_id, message=query.message)
        await status_command(cmd_update, context)
        return
    
    elif data == "cmd_coins":
        cmd_update = UpdateClass(update_id=update.update_id, message=query.message)
        await coins_command(cmd_update, context)
        return
    
    elif data == "cmd_latest":
        cmd_update = UpdateClass(update_id=update.update_id, message=query.message)
        await latest_command(cmd_update, context)
        return
    
    # Price and marketcap commands with symbol
    elif data.startswith("price_"):
        symbol = data.split("_")[1]
        context.args = [symbol]
        cmd_update = UpdateClass(update_id=update.update_id, message=query.message)
        await price_command(cmd_update, context)
        return
    
    elif data.startswith("marketcap_"):
        symbol = data.split("_")[1]
        context.args = [symbol]
        cmd_update = UpdateClass(update_id=update.update_id, message=query.message)
        await marketcap_command(cmd_update, context)
        return


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_message = (
        "🤖 *Crypto Market Dashboard Bot*\n\n"
        "Welcome! Use the buttons below to control your dashboard and get crypto data.\n\n"
        "You can also use commands directly:\n"
        "/run, /stop, /status, /price, /marketcap, /coins, /latest, /info, /help"
    )
    
    keyboard = create_main_keyboard()
    logger.info(f"telegram_bot - /start command received. Creating keyboard with {len(keyboard.inline_keyboard)} rows")
    logger.info(f"telegram_bot - Keyboard buttons: {[row[0].text for row in keyboard.inline_keyboard]}")
    
    # Track user action
    log_user_action(update, "command", "/start")
    
    try:
        await update.message.reply_text(
            welcome_message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        logger.info("telegram_bot - /start message sent successfully with keyboard")
    except Exception as e:
        logger.error(f"telegram_bot - Error sending /start message: {e}")
        raise


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    # Track user action
    log_user_action(update, "command", "/help")
    """Handle /help command."""
    help_text = (
        "📚 *Help - Crypto Market Dashboard Bot*\n\n"
        "📊 *Dashboard Control:*\n"
        "*/run* - Start the dashboard server\n"
        "*/stop* - Stop the dashboard server\n"
        "*/status* - Check if dashboard is running\n\n"
        "💰 *Data Queries:*\n"
        "*/price <SYMBOL>* - Get latest price (e.g., /price BTC)\n"
        "*/marketcap <SYMBOL>* - Get market cap (e.g., /marketcap ETH)\n"
        "*/coins* - List all available coins\n"
        "*/latest* - Latest prices for all coins\n"
        "*/info <SYMBOL>* - Detailed coin information\n\n"
        f"🌐 Dashboard: http://127.0.0.1:{DASH_PORT}/"
    )
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /run command - start the dashboard."""
    # Track user action
    log_user_action(update, "command", "/run")
    
    global dashboard_process, dashboard_thread, dashboard_owners
    
    user = update.effective_user
    user_id = user.id if user else None
    
    if not user_id:
        await update.message.reply_text("❌ Could not identify user.")
        return
    
    # Check if this user already has a dashboard running
    if user_id in dashboard_owners:
        owner_info = dashboard_owners[user_id]
        if owner_info["process"] and owner_info["process"].poll() is None:
            await update.message.reply_text(
                "⚠️ *You already have a dashboard running!*\n\n"
                "Use /stop to stop your dashboard first."
            )
            return
    
    # Check if any dashboard is running (port check)
    if _check_dashboard_running():
        # Find who started it
        running_owner = None
        for uid, info in dashboard_owners.items():
            if info["process"] and info["process"].poll() is None:
                running_owner = info
                break
        
        if running_owner:
            owner_username = running_owner.get("username", "another user")
            await update.message.reply_text(
                f"⚠️ *Dashboard is already running*\n\n"
                f"Started by: @{owner_username}\n"
                f"Only one dashboard can run at a time.\n"
                f"Ask them to stop it with /stop, or wait for it to finish."
            )
        else:
            await update.message.reply_text(
                "⚠️ *Dashboard is already running*\n\n"
                "Another dashboard instance is active.\n"
                "Only one dashboard can run at a time."
            )
        return
    
    try:
        loading_msg = await update.message.reply_text("🔄 Starting dashboard...")
        
        # Start dashboard in a separate process with network access enabled
        env = os.environ.copy()
        env["DASH_HOST"] = "0.0.0.0"  # Allow access from other devices on network
        
        dashboard_process = subprocess.Popen(
            ["python", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        # Track this user as the owner
        username = user.username if user and user.username else "unknown"
        dashboard_owners[user_id] = {
            "process": dashboard_process,
            "started_at": datetime.now(),
            "username": username
        }
        
        # Wait a moment to check if process started
        time.sleep(2)
        
        if dashboard_process.poll() is not None:
            # Process exited immediately - there was an error
            stderr = dashboard_process.stderr.read() if dashboard_process.stderr else "Unknown error"
            await loading_msg.edit_text(
                f"❌ Failed to start dashboard:\n{stderr[:500]}"
            )
            dashboard_process = None
            # Clean up owner tracking if process failed
            if user_id and user_id in dashboard_owners:
                del dashboard_owners[user_id]
            return
        
        # Wait for dashboard to be ready (check if port responds)
        await loading_msg.edit_text("🔄 Starting dashboard...\n⏳ Waiting for dashboard to load data...")
        
        import socket
        import http.client
        import threading
        import queue
        
        max_wait = 480  # Maximum wait time in seconds (8 minutes for data loading)
        wait_interval = 2  # Check every 2 seconds
        waited = 0
        
        # Queue to collect log lines
        log_queue = queue.Queue()
        last_progress = "Starting..."
        coins_fetched = set()
        current_batch = None
        total_batches = None
        
        # Function to read logs in background
        def read_logs():
            nonlocal last_progress, coins_fetched, current_batch, total_batches
            try:
                # Read from both stdout and stderr
                import select
                import sys
                
                # On Windows, we need to use a different approach
                import queue as q
                import threading
                
                def read_stream(stream, stream_name):
                    try:
                        for line in iter(stream.readline, ''):
                            if not line:
                                break
                            line = line.strip()
                            if line:
                                log_queue.put((stream_name, line))
                    except:
                        pass
                
                # Start threads to read stdout and stderr
                stdout_thread = threading.Thread(target=read_stream, args=(dashboard_process.stdout, 'stdout'), daemon=True)
                stderr_thread = threading.Thread(target=read_stream, args=(dashboard_process.stderr, 'stderr'), daemon=True)
                stdout_thread.start()
                stderr_thread.start()
                
                # Process log lines
                while dashboard_process.poll() is None:
                    try:
                        stream_name, line = log_queue.get(timeout=0.5)
                        
                        # Parse progress information
                        if "Starting data fetch" in line:
                            last_progress = "🔄 Starting data fetch..."
                        elif "Fetching batch" in line:
                            # Extract batch info: "Fetching batch 1/5 (5 coins)"
                            import re
                            match = re.search(r'batch (\d+)/(\d+)', line)
                            if match:
                                current_batch = int(match.group(1))
                                total_batches = int(match.group(2))
                                last_progress = f"📦 Fetching batch {current_batch}/{total_batches}"
                        elif "Fetching" in line and "(" in line:
                            # Extract coin: "Fetching BTC (bitcoin)"
                            import re
                            match = re.search(r'Fetching (\w+)', line)
                            if match:
                                coin = match.group(1)
                                coins_fetched.add(coin)
                                last_progress = f"💰 Fetching {coin}... ({len(coins_fetched)} coins)"
                        elif "Successfully fetched and cached" in line:
                            # Extract coin: "bitcoin: Successfully fetched and cached data"
                            import re
                            match = re.search(r'(\w+): Successfully fetched', line)
                            if match:
                                coin_id = match.group(1)
                                last_progress = f"✅ Fetched {coin_id} ({len(coins_fetched)} coins)"
                        elif "Successfully loaded" in line:
                            # Extract coin: "✅ Successfully loaded BTC"
                            import re
                            match = re.search(r'loaded (\w+)', line)
                            if match:
                                coin = match.group(1)
                                last_progress = f"✅ Loaded {coin} ({len(coins_fetched)} coins)"
                        elif "Using sequential fetching" in line:
                            last_progress = "🔄 Using sequential fetching..."
                        elif "HTTP 429" in line:
                            last_progress = "⏳ Rate limited, waiting..."
                        elif "Creating app" in line or "Starting server" in line:
                            last_progress = "🚀 Starting web server..."
                    except queue.Empty:
                        continue
                    except Exception as e:
                        logger.debug(f"Error processing log: {e}")
            except Exception as e:
                logger.debug(f"Error reading logs: {e}")
        
        # Start log reading thread
        log_thread = threading.Thread(target=read_logs, daemon=True)
        log_thread.start()
        
        while waited < max_wait:
            # Check if process is still running
            if dashboard_process.poll() is not None:
                stderr = dashboard_process.stderr.read() if dashboard_process.stderr else "Unknown error"
                await loading_msg.edit_text(
                    f"❌ Dashboard process exited:\n{stderr[:500]}"
                )
                dashboard_process = None
                # Clean up owner tracking if process failed
                if user_id and user_id in dashboard_owners:
                    del dashboard_owners[user_id]
                return
            
            # Check if port is open and responding
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', DASH_PORT))
                sock.close()
                
                if result == 0:
                    # Port is open, try to get HTTP response and verify content
                    try:
                        conn = http.client.HTTPConnection('127.0.0.1', DASH_PORT, timeout=3)
                        conn.request('GET', '/')
                        response = conn.getresponse()
                        response_data = response.read().decode('utf-8', errors='ignore')
                        conn.close()
                        
                        # Check if response is valid (dashboard should return HTML or JSON)
                        # Accept any 200 response with reasonable content length
                        if response.status == 200:
                            # Check if it's HTML or has substantial content
                            is_valid = (
                                '<html' in response_data.lower() or 
                                'dash' in response_data.lower() or 
                                len(response_data) > 500 or
                                'text/html' in response.getheader('Content-Type', '').lower()
                            )
                            
                            if is_valid:
                                # Dashboard is ready! Get local IP for network access
                                local_ip = _get_local_ip()
                                access_urls = f"🌐 Local: http://127.0.0.1:{DASH_PORT}/\n"
                                if local_ip:
                                    access_urls += f"🌐 Network: http://{local_ip}:{DASH_PORT}/"
                                
                                await loading_msg.edit_text(
                                    f"✅ Dashboard started successfully!\n"
                                    f"{access_urls}\n"
                                    f"⏱️ Ready in {waited} seconds"
                                )
                                return
                            else:
                                # Got 200 but content seems incomplete, keep waiting
                                logger.debug(f"Got 200 but content seems incomplete (length: {len(response_data)})")
                    except http.client.HTTPException as e:
                        # HTTP error, but port is open - keep waiting
                        logger.debug(f"HTTP exception (will retry): {e}")
                        pass
                    except (ConnectionError, socket.timeout, OSError) as e:
                        # Connection/timeout error - port might not be ready yet
                        logger.debug(f"Connection error (will retry): {e}")
                        pass
                    except Exception as e:
                        # Other HTTP error, but port is open - keep waiting
                        logger.debug(f"HTTP check failed (will retry): {e}")
                        pass
            except Exception as e:
                # Socket connection error - keep waiting
                logger.debug(f"Socket check failed (will retry): {e}")
                pass
            
            # Update progress message with latest log info
            progress_text = f"🔄 Starting dashboard...\n⏳ {last_progress}\n"
            if coins_fetched:
                progress_text += f"📊 Progress: {len(coins_fetched)} coins fetched\n"
            if current_batch and total_batches:
                progress_text += f"📦 Batch {current_batch}/{total_batches}\n"
            progress_text += f"⏱️ Elapsed: {waited}s"
            
            try:
                await loading_msg.edit_text(progress_text)
            except:
                pass  # Message might be too long or edit failed
            
            # Wait before next check
            await asyncio.sleep(wait_interval)
            waited += wait_interval
        
        # Timeout - dashboard might still be starting
        # Check one more time if port is at least open
        port_open = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', DASH_PORT))
            port_open = (result == 0)
            sock.close()
        except:
            pass
        
        # Check process status one more time
        process_exited = dashboard_process.poll() is not None
        if process_exited:
            stderr = ""
            try:
                if dashboard_process.stderr:
                    stderr = dashboard_process.stderr.read()
            except:
                pass
            await loading_msg.edit_text(
                f"❌ Dashboard process exited unexpectedly.\n"
                f"💡 Check the dashboard logs for errors.\n"
                f"{'Error: ' + stderr[:200] if stderr else ''}"
            )
            dashboard_process = None
            # Clean up owner tracking if process failed
            if user_id and user_id in dashboard_owners:
                del dashboard_owners[user_id]
        elif port_open:
            local_ip = _get_local_ip()
            access_urls = f"🌐 Local: http://127.0.0.1:{DASH_PORT}/\n"
            if local_ip:
                access_urls += f"🌐 Network: http://{local_ip}:{DASH_PORT}/\n"
            
            await loading_msg.edit_text(
                f"⚠️ Dashboard process is running but HTTP check timed out.\n"
                f"{access_urls}"
                f"💡 The page may still be loading data. Try accessing it in your browser.\n"
                f"⏱️ Waited {waited} seconds"
            )
        else:
            await loading_msg.edit_text(
                f"❌ Dashboard process started but port {DASH_PORT} is not responding.\n"
                f"💡 Check the dashboard logs for errors.\n"
                f"⏱️ Waited {waited} seconds"
            )
            
    except Exception as e:
        logger.error(f"Error starting dashboard: {e}")
        try:
            await loading_msg.edit_text(f"❌ Error: {str(e)}")
        except:
            await update.message.reply_text(f"❌ Error: {str(e)}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop command - stop the dashboard."""
    # Track user action
    log_user_action(update, "command", "/stop")
    
    global dashboard_process, dashboard_owners
    
    user = update.effective_user
    user_id = user.id if user else None
    
    if not user_id:
        await update.message.reply_text("❌ Could not identify user.")
        return
    
    stopped_any = False
    tracked_pid = None
    
    # Check if this user owns a running dashboard
    user_owns_dashboard = False
    if user_id in dashboard_owners:
        owner_info = dashboard_owners[user_id]
        dashboard_process = owner_info["process"]
        if dashboard_process and dashboard_process.poll() is None:
            tracked_pid = dashboard_process.pid
            user_owns_dashboard = True
    
    # If user doesn't own a dashboard, check if any dashboard is running
    if not user_owns_dashboard and _check_dashboard_running():
        # Find who owns the running dashboard
        running_owner = None
        for uid, info in dashboard_owners.items():
            if info["process"] and info["process"].poll() is None:
                running_owner = info
                break
        
        if running_owner:
            owner_username = running_owner.get("username", "another user")
            await update.message.reply_text(
                f"⚠️ *You don't own the running dashboard*\n\n"
                f"Started by: @{owner_username}\n"
                f"Only the owner can stop it with /stop."
            )
            return
        else:
            await update.message.reply_text(
                "⚠️ *Dashboard is running, but you don't own it*\n\n"
                "The dashboard was started by another user or manually.\n"
                "Only the owner can stop it."
            )
            return
    
    # Stop the tracked process if it exists
    if tracked_pid:
        try:
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()
            stopped_any = True
        except Exception as e:
            logger.error(f"Error stopping tracked process: {e}")
        finally:
            dashboard_process = None
            # Remove from owners dict
            if user_id in dashboard_owners:
                del dashboard_owners[user_id]
    
    # Also check for and stop manually started main.py processes
    import psutil
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'main.py' in ' '.join(cmdline):
                    proc_pid = proc.info['pid']
                    # Skip if this is the bot's tracked process (already handled above)
                    if tracked_pid and proc_pid == tracked_pid:
                        continue
                    try:
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        stopped_any = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.warning(f"Could not stop process {proc_pid}: {e}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.error(f"Error checking for processes: {e}")
    
    # Send response
    if stopped_any:
        await update.message.reply_text("🛑 Dashboard stopped successfully!")
    else:
        # Double-check if port is still in use
        import socket
        port_in_use = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', DASH_PORT))
            port_in_use = (result == 0)
            sock.close()
        except:
            pass
        
        if port_in_use:
            await update.message.reply_text(
                "⚠️ Dashboard appears to be running but could not be stopped.\n"
                "💡 Try stopping it manually or check process permissions."
            )
        else:
            await update.message.reply_text("⚠️ Dashboard is not running!")


# Track processed updates to prevent duplicates (use set to handle multiple instances)
_processed_updates = set()

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - check dashboard status."""
    # Track user action
    log_user_action(update, "command", "/status")
    
    global dashboard_process, _processed_updates, dashboard_owners
    
    user = update.effective_user
    user_id = user.id if user else None
    
    # Prevent duplicate responses to the same update
    update_key = f"status_{update.update_id}"
    if update_key in _processed_updates:
        logger.warning(f"Ignoring duplicate status command for update_id {update.update_id}")
        return
    _processed_updates.add(update_key)
    
    # Clean up old entries (keep only last 100)
    if len(_processed_updates) > 100:
        _processed_updates = set(list(_processed_updates)[-50:])
    
    # Check if any dashboard is running
    any_dashboard_running = _check_dashboard_running()
    
    # Find who owns the running dashboard (if any)
    running_owner = None
    running_process = None
    if any_dashboard_running:
        for uid, info in dashboard_owners.items():
            if info["process"] and info["process"].poll() is None:
                running_owner = {"user_id": uid, "username": info.get("username", "unknown"), "started_at": info.get("started_at")}
                running_process = info["process"]
                break
    
    # Check if this user owns the running dashboard
    # Only true if the running owner is the current user
    user_owns_dashboard = False
    user_process = None
    if running_owner and running_owner["user_id"] == user_id:
        # Current user owns the running dashboard
        user_owns_dashboard = True
        user_process = running_process
    elif user_id and user_id in dashboard_owners:
        # User has a dashboard entry, but it's not the one running
        owner_info = dashboard_owners[user_id]
        user_process = owner_info["process"]
        # Check if their process is still running (might be stale)
        if user_process and user_process.poll() is not None:
            # Process is dead, remove from owners
            del dashboard_owners[user_id]
            user_process = None
    
    # Determine if the current user owns the running dashboard
    bot_started = user_owns_dashboard and (running_owner is not None and running_owner["user_id"] == user_id)
    
    # Also check if dashboard is running on the port (even if not started by bot)
    import socket
    port_in_use = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', DASH_PORT))
        port_in_use = (result == 0)
        sock.close()
    except:
        pass
    
    # Check for main.py processes - collect all PIDs (excluding bot's tracked process)
    import psutil
    main_py_pids = []
    # Use the running process PID if we found one, otherwise use user's process if they own it
    tracked_pid = None
    if user_owns_dashboard and user_process:
        tracked_pid = user_process.pid
    elif running_process:
        tracked_pid = running_process.pid
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'main.py' in ' '.join(cmdline):
                    proc_pid = proc.info['pid']
                    # Skip if this is the bot's tracked process
                    if tracked_pid and proc_pid == tracked_pid:
                        continue
                    main_py_pids.append(proc_pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except:
        # psutil not available, skip this check
        pass
    
    # Build status message (only one message)
    # Get local IP for network access
    local_ip = _get_local_ip()
    
    if bot_started or port_in_use or main_py_pids:
        status_text = "✅ *Dashboard Status: RUNNING*\n\n"
        status_text += f"🌐 Local: http://127.0.0.1:{DASH_PORT}/\n"
        if local_ip:
            status_text += f"🌐 Network: http://{local_ip}:{DASH_PORT}/\n"
        
        # Show ownership information
        # Only show "Started by you" if running_owner exists and matches current user
        if running_owner and running_owner["user_id"] == user_id:
            # User owns the running dashboard
            if running_process:
                status_text += f"📊 Process ID: {running_process.pid}\n"
            status_text += "✅ *Started by you*\n"
            if running_owner.get("started_at"):
                started_time = running_owner["started_at"].strftime("%Y-%m-%d %H:%M:%S")
                status_text += f"🕐 Started at: {started_time}\n"
            # Also show manually started processes if any
            if main_py_pids:
                if len(main_py_pids) == 1:
                    status_text += f"\n⚠️ Also running (manual): PID {main_py_pids[0]}"
                else:
                    status_text += f"\n⚠️ Also running (manual): PIDs {', '.join(map(str, main_py_pids))}"
        elif running_owner and running_owner["user_id"] != user_id:
            # Dashboard is running but owned by someone else
            owner_username = running_owner.get("username", "another user")
            status_text += f"👤 Started by: @{owner_username}\n"
            if running_owner.get("started_at"):
                started_time = running_owner["started_at"].strftime("%Y-%m-%d %H:%M:%S")
                status_text += f"🕐 Started at: {started_time}\n"
            status_text += "\n⚠️ *You don't own this dashboard*\n"
            status_text += "💡 Only the owner can stop it with /stop"
            if running_process:
                status_text += f"\n📊 Process ID: {running_process.pid}"
        elif main_py_pids:
            # Show all PIDs if multiple, or just one
            if len(main_py_pids) == 1:
                status_text += f"📊 Process ID: {main_py_pids[0]}\n"
            else:
                status_text += f"📊 Process IDs: {', '.join(map(str, main_py_pids))}\n"
            status_text += "⚠️ Started manually (not by bot)"
        elif port_in_use:
            status_text += "⚠️ Port in use (process may be running)\n"
            status_text += "💡 Use /run to start via bot"
    else:
        status_text = (
            "❌ *Dashboard Status: STOPPED*\n\n"
            f"💡 Use /run to start the dashboard\n"
            f"🌐 Will run on: http://127.0.0.1:{DASH_PORT}/"
        )
    
    # Send only one message
    await update.message.reply_text(status_text, parse_mode="Markdown")


def _load_data_manager() -> DataManager:
    """Load data manager (lazy loading with caching)."""
    global data_manager
    if data_manager is None:
        # Load data synchronously (this is called from executor, so no event loop needed)
        data_manager = _load_data_sync()
    return data_manager


def _load_data_sync() -> DataManager:
    """Load data synchronously (run in thread to avoid event loop issues)."""
    dm = DataManager()
    dm.load_all_data()
    return dm


def _get_local_ip() -> str:
    """Get the local IP address for network access."""
    try:
        import socket
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # Doesn't actually connect, just determines local IP
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = None
        finally:
            s.close()
        return ip
    except Exception:
        return None


def _load_single_coin_data(symbol: str) -> tuple:
    """Load data for a single coin only (faster for price/marketcap commands)."""
    from src.config import CACHE_DIR, DAYS_HISTORY, VS_CURRENCY
    from src.constants import COINS
    from src.data.fetcher import fetch_market_caps_retry
    import json
    
    # Find the coin_id for this symbol
    coin_id = None
    cat = None
    grp = None
    for cid, sym, c, g in COINS:
        if sym.upper() == symbol.upper():
            coin_id = cid
            cat = c
            grp = g
            break
    
    if not coin_id:
        return None, None, None
    
    # Load market cap data
    try:
        mc_series = fetch_market_caps_retry(coin_id)
    except Exception as e:
        logger.error(f"Failed to load market cap for {symbol}: {e}")
        return None, None, None
    
    # Load price data from cache
    price_series = None
    cache_path = CACHE_DIR / f"{coin_id}_{DAYS_HISTORY}d_{VS_CURRENCY}.json"
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                js = json.load(f)
            
            if "prices" in js and js["prices"]:
                import pandas as pd
                df_prices = pd.DataFrame(js["prices"], columns=["ts", "price"])
                df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
                df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
                price_series = df_prices.set_index("date")["price"].sort_index()
        except Exception as e:
            logger.debug(f"Failed to load price data for {symbol}: {e}")
    
    return mc_series, price_series, (cat, grp)


def _check_dashboard_running() -> bool:
    """Check if dashboard is running (by bot or manually)."""
    global dashboard_process
    
    # Check if bot's tracked process is running
    if dashboard_process and dashboard_process.poll() is None:
        return True
    
    # Check if port is in use
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', DASH_PORT))
        port_in_use = (result == 0)
        sock.close()
        if port_in_use:
            return True
    except:
        pass
    
    # Check for main.py processes
    import psutil
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'main.py' in ' '.join(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except:
        pass
    
    return False


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /price command - get latest price for a coin."""
    # Track user action
    symbol = context.args[0].upper() if context.args and len(context.args) > 0 else "none"
    log_user_action(update, "command", f"/price {symbol}")
    
    if not context.args:
        await update.message.reply_text("❌ Please specify a coin symbol. Example: /price BTC")
        return
    
    # Check if dashboard is running
    if not _check_dashboard_running():
        await update.message.reply_text(
            "⚠️ *Dashboard is offline*\n\n"
            "💡 The dashboard needs to be running to access data.\n"
            "Use /run to start the dashboard first."
        )
        return
    
    symbol = context.args[0].upper()
    loading_msg = None
    
    try:
        # Load only this coin's data (much faster than loading all coins)
        import asyncio
        loop = asyncio.get_event_loop()
        mc_series, price_series, meta = await loop.run_in_executor(None, _load_single_coin_data, symbol)
        
        if mc_series is None:
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
            return
        
        # Get latest market cap
        latest_mc = mc_series.iloc[-1]
        latest_date = mc_series.index[-1]
        
        latest_price = None
        change_24h = None
        change_emoji = ""
        
        if price_series is not None:
            price_series = price_series.dropna()
            if not price_series.empty:
                latest_price = price_series.iloc[-1]
                # Calculate 24h change if possible
                if len(price_series) > 1:
                    prev_price = price_series.iloc[-2]
                    change_24h = ((latest_price - prev_price) / prev_price) * 100
                    change_emoji = "📈" if change_24h >= 0 else "📉"
        
        # If no price data, show market cap only
        if latest_price is None:
            price_text = (
                f"💰 *{symbol} Price*\n\n"
                f"💎 Market Cap: ${latest_mc:,.0f}\n"
                f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
                f"❌ Price data not available\n"
            )
        else:
            price_text = (
                f"💰 *{symbol} Price*\n\n"
                f"💵 Price: ${latest_price:,.2f}\n"
                f"💎 Market Cap: ${latest_mc:,.0f}\n"
                f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
            )
            
            if change_24h is not None:
                price_text += f"{change_emoji} 24h Change: {change_24h:+.2f}%\n"
        
        if meta:
            cat, grp = meta
            price_text += f"📂 Category: {cat}\n"
        
        # Delete loading message and send result
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(price_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def marketcap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /marketcap command - get market cap for a coin."""
    # Track user action
    symbol = context.args[0].upper() if context.args and len(context.args) > 0 else "none"
    log_user_action(update, "command", f"/marketcap {symbol}")
    
    if not context.args:
        await update.message.reply_text("❌ Please specify a coin symbol. Example: /marketcap BTC")
        return
    
    # Check if dashboard is running
    if not _check_dashboard_running():
        await update.message.reply_text(
            "⚠️ *Dashboard is offline*\n\n"
            "💡 The dashboard needs to be running to access data.\n"
            "Use /run to start the dashboard first."
        )
        return
    
    symbol = context.args[0].upper()
    loading_msg = None
    
    try:
        loading_msg = await update.message.reply_text("🔄 Loading data...")
        import asyncio
        loop = asyncio.get_event_loop()
        dm = await loop.run_in_executor(None, _load_data_manager)
        
        if symbol not in dm.series:
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
            return
        
        # Market cap is stored in the series
        series = dm.series[symbol]
        latest_mc = series.iloc[-1]
        latest_date = series.index[-1]
        
        mc_text = (
            f"💎 *{symbol} Market Cap*\n\n"
            f"💰 Market Cap: ${latest_mc:,.0f}\n"
            f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
        )
        
        if symbol in dm.meta:
            cat, grp = dm.meta[symbol]
            mc_text += f"📂 Category: {cat}\n"
        
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(mc_text, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error getting market cap for {symbol}: {e}")
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def coins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /coins command - list all available coins."""
    # Track user action
    log_user_action(update, "command", "/coins")
    
    # Get coins directly from constants (no need to load data)
    from src.constants import COINS, DOM_SYM
    
    try:
        # Extract symbols and sort alphabetically
        symbols = sorted([sym for _, sym, _, _ in COINS])
        symbols.append(DOM_SYM)  # Add USDT.D
        
        coins_text = f"💰 *Available Coins ({len(symbols)})*\n\n"
        
        # Format as a clean list (3 columns for better readability)
        # Split into chunks of 3 for better formatting
        for i in range(0, len(symbols), 3):
            chunk = symbols[i:i+3]
            coins_text += "  ".join(f"`{sym:8s}`" for sym in chunk) + "\n"
        
        coins_text += f"\n💡 Use `/price <SYMBOL>` to get price info"
        
        await update.message.reply_text(coins_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error listing coins: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def latest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /latest command - get latest prices for all coins."""
    # Track user action
    log_user_action(update, "command", "/latest")
    
    # Check if dashboard is running
    if not _check_dashboard_running():
        await update.message.reply_text(
            "⚠️ *Dashboard is offline*\n\n"
            "💡 The dashboard needs to be running to access data.\n"
            "Use /run to start the dashboard first."
        )
        return
    
    loading_msg = None
    try:
        loading_msg = await update.message.reply_text("🔄 Loading data...")
        import asyncio
        loop = asyncio.get_event_loop()
        dm = await loop.run_in_executor(None, _load_data_manager)
        
        if dm.df_raw is None or dm.df_raw.empty:
            await update.message.reply_text("❌ No data available. Try running the dashboard first.")
            return
        
        latest_text = f"📊 *Latest Prices*\n"
        latest_text += f"📅 Date: {dm.df_raw.index[-1].strftime('%Y-%m-%d')}\n\n"
        
        # Get top 10 by market cap or show all if less than 10
        from src.app.callbacks import _load_price_data
        prices_dict = _load_price_data()
        
        if len(dm.symbols_all) <= 10:
            symbols_to_show = dm.symbols_all
        else:
            # Sort by latest market cap
            latest_mcs = {}
            for sym in dm.symbols_all:
                if sym in dm.series:
                    latest_mcs[sym] = dm.series[sym].iloc[-1]
            symbols_to_show = sorted(latest_mcs.keys(), key=lambda x: latest_mcs[x], reverse=True)[:10]
            latest_text += "*Top 10 by Market Cap:*\n\n"
        
        for sym in symbols_to_show:
            if sym in prices_dict:
                price_series = prices_dict[sym].dropna()
                if not price_series.empty:
                    price = price_series.iloc[-1]
                    latest_text += f"💰 {sym}: ${price:,.2f}\n"
                else:
                    # Fallback to market cap if no price
                    if sym in dm.series:
                        mc = dm.series[sym].iloc[-1]
                        latest_text += f"💎 {sym}: MC ${mc:,.0f}\n"
            elif sym in dm.series:
                # Fallback to market cap if no price data
                mc = dm.series[sym].iloc[-1]
                latest_text += f"💎 {sym}: MC ${mc:,.0f}\n"
        
        if len(dm.symbols_all) > 10:
            latest_text += f"\n... and {len(dm.symbols_all) - 10} more coins"
        
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(latest_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting latest prices: {e}")
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /info command - get detailed information for a coin."""
    # Track user action
    symbol = context.args[0].upper() if context.args and len(context.args) > 0 else "none"
    log_user_action(update, "command", f"/info {symbol}")
    
    if not context.args:
        await update.message.reply_text("❌ Please specify a coin symbol. Example: /info BTC")
        return
    
    # Check if dashboard is running
    if not _check_dashboard_running():
        await update.message.reply_text(
            "⚠️ *Dashboard is offline*\n\n"
            "💡 The dashboard needs to be running to access data.\n"
            "Use /run to start the dashboard first."
        )
        return
    
    symbol = context.args[0].upper()
    loading_msg = None
    
    try:
        loading_msg = await update.message.reply_text("🔄 Loading data...")
        import asyncio
        loop = asyncio.get_event_loop()
        dm = await loop.run_in_executor(None, _load_data_manager)
        
        if symbol not in dm.series:
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
            return
        
        info_text = f"📊 *{symbol} Information*\n\n"
        
        # Category and group
        if symbol in dm.meta:
            cat, grp = dm.meta[symbol]
            info_text += f"📂 Category: {cat}\n"
            info_text += f"🏷️ Group: {grp}\n\n"
        
        # Latest data
        series = dm.series[symbol]
        latest_mc = series.iloc[-1]
        latest_date = series.index[-1]
        
        info_text += f"💎 Latest Market Cap: ${latest_mc:,.0f}\n"
        info_text += f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
        
        # Price if available
        from src.app.callbacks import _load_price_data
        prices_dict = _load_price_data()
        if symbol in prices_dict:
            price_series = prices_dict[symbol].dropna()
            if not price_series.empty:
                latest_price = price_series.iloc[-1]
                info_text += f"💵 Latest Price: ${latest_price:,.2f}\n"
        
        # Data points
        info_text += f"📈 Data Points: {len(series)}\n"
        info_text += f"📅 First Date: {series.index[0].strftime('%Y-%m-%d')}\n"
        info_text += f"📅 Last Date: {series.index[-1].strftime('%Y-%m-%d')}\n"
        
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(info_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting info for {symbol}: {e}")
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands."""
    # Track user action
    command = update.message.text if update.message else "unknown"
    log_user_action(update, "command", f"unknown: {command}")
    
    if update.message and update.message.text and update.message.text.startswith("/"):
        command = update.message.text.split()[0] if update.message.text.split() else update.message.text
        await update.message.reply_text(
            f"❌ *Unknown Command*\n\n"
            f"Command `{command}` does not exist.\n\n"
            f"💡 Use /help to see all available commands.",
            parse_mode="Markdown"
        )


def check_and_create_lock() -> bool:
    """
    Check if another instance is running and create lock file if not.
    Returns True if lock was created (no other instance), False if another instance exists.
    """
    if LOCK_FILE.exists():
        # Check if the process in the lock file is still running
        try:
            with open(LOCK_FILE, 'r') as f:
                lock_pid = int(f.read().strip())
            
            # Check if process with this PID exists
            try:
                import psutil
                if psutil.pid_exists(lock_pid):
                    # Check if it's actually our bot process
                    proc = psutil.Process(lock_pid)
                    cmdline = ' '.join(proc.cmdline()) if proc.cmdline() else ''
                    if 'telegram_bot.py' in cmdline:
                        logger.error(f"Another bot instance is already running (PID: {lock_pid})")
                        logger.error(f"Command: {cmdline}")
                        return False
            except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
                # Process doesn't exist or we can't access it - lock file is stale
                logger.warning(f"Stale lock file found (PID: {lock_pid} no longer exists). Removing it...")
                LOCK_FILE.unlink()
        except (ValueError, IOError) as e:
            logger.warning(f"Could not read lock file: {e}. Removing it...")
            LOCK_FILE.unlink()
    
    # Create lock file with current PID
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        logger.debug(f"Lock file created: {LOCK_FILE} (PID: {os.getpid()})")
        return True
    except IOError as e:
        logger.error(f"Could not create lock file: {e}")
        return False


def remove_lock() -> None:
    """Remove the lock file."""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            logger.debug("Lock file removed")
    except Exception as e:
        logger.warning(f"Could not remove lock file: {e}")


async def main_async() -> None:
    """Async main function to start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        logger.error("Please set it with: export TELEGRAM_BOT_TOKEN='your-token'")
        return
    
    # Validate token format (should be numeric:alphanumeric)
    if ":" not in TELEGRAM_BOT_TOKEN:
        logger.error("Invalid token format! Token should be in format: '123456789:ABCdefGHIjklMNOpqrsTUVwxyz'")
        logger.error("Make sure there are no extra spaces in the token.")
        return
    
    # Check if another instance is running
    if not check_and_create_lock():
        logger.error("Cannot start bot: Another instance is already running!")
        logger.error("To start anyway, stop the other instance first or delete the lock file:")
        logger.error(f"  Remove: {LOCK_FILE}")
        return
    
    # Ensure lock is removed on exit
    import atexit
    atexit.register(remove_lock)
    
    # Delete any existing webhook to ensure clean polling state
    from telegram import Bot
    from telegram.error import TimedOut, NetworkError
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        # Add timeout for webhook check
        try:
            webhook_info = await asyncio.wait_for(bot.get_webhook_info(), timeout=10.0)
            if webhook_info.url:
                logger.info(f"Found existing webhook: {webhook_info.url}. Deleting it...")
                await asyncio.wait_for(bot.delete_webhook(drop_pending_updates=True), timeout=10.0)
                logger.info("Webhook deleted. Ready for polling.")
        except (TimedOut, NetworkError, asyncio.TimeoutError) as e:
            logger.warning(f"Network timeout checking webhook (this is OK): {e}")
        except Exception as e:
            logger.warning(f"Could not check/delete webhook: {e}. Continuing anyway...")
        finally:
            try:
                await bot.close()
            except:
                pass
    except Exception as e:
        logger.warning(f"Could not initialize bot for webhook check: {e}. Continuing anyway...")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register callback query handler (for buttons) - must be before command handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("run", run_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Data query handlers
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("marketcap", marketcap_command))
    application.add_handler(CommandHandler("coins", coins_command))
    application.add_handler(CommandHandler("latest", latest_command))
    application.add_handler(CommandHandler("info", info_command))
    
    # Unknown command handler (must be last to catch unhandled commands)
    # This catches any command that starts with / but isn't handled above
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Start the bot using async context manager (recommended for v20+)
    logger.info("Starting Telegram bot...")
    try:
        async with application:
            # Try to start with retry logic for network issues
            max_retries = 3
            retry_delay = 2
            for attempt in range(max_retries):
                try:
                    await application.start()
                    break
                except (TimedOut, NetworkError) as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Connection timeout (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(f"Failed to connect to Telegram API after {max_retries} attempts.")
                        logger.error("This is usually a network connectivity issue.")
                        logger.error("Please check:")
                        logger.error("  1. Your internet connection")
                        logger.error("  2. Firewall/proxy settings")
                        logger.error("  3. Telegram API status")
                        raise
                except Exception as e:
                    logger.error(f"Error starting bot: {e}")
                    raise
            
            await application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            logger.info("Bot is running. Press Ctrl+C to stop.")
            # Keep running until interrupted
            # Use a signal-based approach for clean shutdown
            import signal
            stop_event = asyncio.Event()
            
            def signal_handler():
                logger.info("Shutdown signal received")
                stop_event.set()
            
            # Set up signal handlers for graceful shutdown
            if sys.platform != "win32":
                loop = asyncio.get_event_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(sig, signal_handler)
            
            try:
                await stop_event.wait()
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                stop_event.set()
            finally:
                # Stop polling before exiting context manager
                logger.info("Stopping bot...")
                try:
                    await application.updater.stop()
                except Exception as e:
                    logger.warning(f"Error stopping updater: {e}")
                try:
                    await application.stop()
                except Exception as e:
                    logger.warning(f"Error stopping application: {e}")
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error in bot main loop: {e}")
        raise
    finally:
        # Remove lock file on exit
        remove_lock()


def main() -> None:
    """Start the Telegram bot."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        # Ensure lock is removed even on unexpected exit
        remove_lock()


if __name__ == "__main__":
    main()

