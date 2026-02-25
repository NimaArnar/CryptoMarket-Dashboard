"""Telegram bot for Crypto Market Dashboard control."""
import asyncio
import http.client
import json
import logging
import os
import re
import requests
import socket
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Optional, Tuple, Dict

import pandas as pd
import plotly.graph_objects as go
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram import Update as UpdateClass
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.error import Conflict, TimedOut, NetworkError

from src.config import (
    DASH_PORT, 
    PROJECT_ROOT,
    BOT_MAX_DASHBOARD_WAIT,
    BOT_WAIT_INTERVAL,
    BOT_PROCESSED_UPDATES_MAX,
    BOT_MAX_MESSAGE_LENGTH,
    BOT_COINS_PER_PAGE,
    COINGECKO_API_BASE,
    COINGECKO_API_KEY,
    CACHE_DIR,
    DAYS_HISTORY,
    VS_CURRENCY
)
from src.data_manager import DataManager
from src.utils import setup_logger

logger = setup_logger(__name__)

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

# Lock for dashboard operations to prevent race conditions
dashboard_lock = asyncio.Lock()

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
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_help_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for help screen (only about and back buttons)."""
    keyboard = [
        [
            InlineKeyboardButton("ℹ️ What's this bot for?", callback_data="about")
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_about_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for about screen (only back button)."""
    keyboard = [
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
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
            InlineKeyboardButton("🔄 Restart Dashboard", callback_data="cmd_restart")
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
            InlineKeyboardButton("📊 Correlation", callback_data="menu_corr")
        ],
        [
            InlineKeyboardButton("💵 Price", callback_data="price_BTC"),
        ],
        [
            InlineKeyboardButton("📊 Info", callback_data="info_BTC"),
        ],
        [
            InlineKeyboardButton("📊 Summary", callback_data="summary_BTC"),
            InlineKeyboardButton("📈 Chart", callback_data="chartbtn_BTC"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_correlation_keyboard(exclude_symbol: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for correlation: default (BTC vs ETH) + buttons for all coins.
    When exclude_symbol is set (e.g. first coin chosen), that symbol is omitted from the list."""
    from src.constants import COINS, DOM_SYM
    symbols = sorted([sym for _, sym, _, _ in COINS])
    symbols.append(DOM_SYM)
    if exclude_symbol:
        symbols = [s for s in symbols if s != exclude_symbol]
    keyboard = [
        [InlineKeyboardButton("📊 Default", callback_data="corr_default")]
    ]
    # Coin buttons in rows of 4
    row_size = 4
    for i in range(0, len(symbols), row_size):
        row = [
            InlineKeyboardButton(sym, callback_data=f"corr_coin_{sym}")
            for sym in symbols[i : i + row_size]
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Back to Data Queries", callback_data="menu_data")])
    return InlineKeyboardMarkup(keyboard)


async def _send_data_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the Data Queries menu so it becomes the latest message (for UX after Data Queries actions)."""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="💰 *Data Queries*\n\nGet real-time cryptocurrency data:",
            parse_mode="Markdown",
            reply_markup=create_data_keyboard()
        )
    except Exception as e:
        logger.debug(f"Failed to resend Data Queries menu: {e}")


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
    
    elif data == "menu_corr":
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="📊 *Correlation*\n\nChoose default or tap two coins (first, then second):",
            parse_mode="Markdown",
            reply_markup=create_correlation_keyboard()
        )
        return
    
    elif data == "corr_default":
        # Delete the previous Correlation/Data Queries message for a cleaner chat
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete Correlation message: {e}")
        if not _check_dashboard_running():
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Dashboard is offline. Use /run to start it first.",
                parse_mode="Markdown"
            )
            await _send_data_menu(chat_id, context)
            return
        loop = asyncio.get_event_loop()
        try:
            corr_text, chart_path = await loop.run_in_executor(
                None, _compute_and_export_correlation, "BTC", "ETH"
            )
            caption = f"📊 Correlation: BTC vs ETH\n\n{corr_text}"
            if chart_path and chart_path.exists():
                with open(chart_path, "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=caption[:1024] if len(caption) > 1024 else caption,
                    )
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"📊 Correlation\n\n{corr_text}")
            # Issue #40: also send 1-year comparison chart
            chart_1y_path = await loop.run_in_executor(None, _generate_two_coin_1y_chart, "BTC", "ETH")
            if chart_1y_path and chart_1y_path.exists():
                with open(chart_1y_path, "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption="📈 1 Year comparison: BTC vs ETH (index 100 = start)",
                    )
        except Exception as e:
            logger.error(f"Correlation error: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")
        await _send_data_menu(chat_id, context)
        return
    
    elif data.startswith("corr_coin_"):
        sym = data.replace("corr_coin_", "")
        first = context.user_data.get("corr_first")
        if first is None:
            context.user_data["corr_first"] = sym
            # Second selection keyboard excludes the first coin so user cannot pick same coin twice
            try:
                await query.edit_message_text(
                    f"📊 First coin: *{sym}*. Tap the second coin:",
                    parse_mode="Markdown",
                    reply_markup=create_correlation_keyboard(exclude_symbol=sym)
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📊 First coin: {sym}. Tap the second coin:",
                    reply_markup=create_correlation_keyboard(exclude_symbol=sym)
                )
            return
        # exclude_symbol ensures first != sym in UI; this branch is only if state was stale
        if first == sym:
            await query.answer("Pick a different coin as second.", show_alert=True)
            return
        context.user_data.pop("corr_first", None)
        if not _check_dashboard_running():
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Dashboard is offline. Use /run to start it first.",
                parse_mode="Markdown"
            )
            await _send_data_menu(chat_id, context)
            return
        # Delete the previous Correlation selection message for a cleaner chat
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete Correlation message: {e}")
        loop = asyncio.get_event_loop()
        try:
            corr_text, chart_path = await loop.run_in_executor(
                None, _compute_and_export_correlation, first, sym
            )
            caption = f"📊 Correlation: {first} vs {sym}\n\n{corr_text}"
            if chart_path and chart_path.exists():
                with open(chart_path, "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=caption[:1024] if len(caption) > 1024 else caption,
                    )
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"📊 Correlation\n\n{corr_text}")
            # Issue #40: also send 1-year comparison chart
            chart_1y_path = await loop.run_in_executor(None, _generate_two_coin_1y_chart, first, sym)
            if chart_1y_path and chart_1y_path.exists():
                with open(chart_1y_path, "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=f"📈 1 Year comparison: {first} vs {sym} (index 100 = start)",
                    )
        except Exception as e:
            logger.error(f"Correlation error: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")
        await _send_data_menu(chat_id, context)
        return
    
    elif data == "about":
        # Show bot information and purpose
        # Edit the existing message instead of sending new
        await about_command_edit(query, context)
        return
    
    elif data == "help":
        # Check if message already shows help
        message_text = query.message.text or ""
        message_caption = query.message.caption or ""
        full_text = message_text + message_caption
        
        # Check for unique identifier: dashboard URL or port number which only appears in help message
        dashboard_url = f"http://127.0.0.1:{DASH_PORT}/"
        port_str = f":{DASH_PORT}/"
        
        # Check if this is already a help message
        # The dashboard URL is unique to help message - this is the most reliable check
        has_url = dashboard_url in full_text or port_str in full_text or f"127.0.0.1:{DASH_PORT}" in full_text
        
        # Check for help-specific content (title + sections)
        has_help_title = "Help - Crypto Market Dashboard Bot" in full_text
        has_help_sections = "Dashboard Control:" in full_text and "Data Queries:" in full_text
        
        # Only consider it a help message if it has the URL (most reliable) OR both title and sections
        is_help_message = has_url or (has_help_title and has_help_sections)
        
        # Log for debugging
        logger.info(f"Help button - text_len: {len(full_text)}, has_url: {has_url}, has_title: {has_help_title}, has_sections: {has_help_sections}, is_help: {is_help_message}")
        
        # If message is already showing help, don't edit again
        if is_help_message:
            # Already showing help - callback already answered at start of function
            # Just return without doing anything to avoid any message changes
            logger.info("Help: Already showing help, skipping edit")
            return
        
        logger.info("Help: Not showing help yet, editing message")
        
        help_text = (
            "📚 *Help - Crypto Market Dashboard Bot*\n\n"
            "📊 *Dashboard Control:*\n"
            "*/run* - Start the dashboard server\n"
            "*/stop* - Stop the dashboard server\n"
            "*/restart* - Restart the dashboard server\n"
            "*/status* - Check if dashboard is running\n\n"
            "💰 *Data Queries (live, no dashboard needed):*\n"
            "*/price <SYMBOL>* - Instant price (e.g., /price BTC)\n"
            "*/coins* - List all available coins\n"
            "*/latest* - Live prices for all coins\n"
            "*/info <SYMBOL>* - Detailed coin information\n"
            "*/summary <SYMBOL> [1d|1w|1m|1y]* - Timeframe summary\n"
            "*/chart <SYMBOL> [1w|1m|1y]* - Price & index chart image\n"
            "*/corr [COIN1] [COIN2]* - Correlation (default: BTC ETH)\n\n"
            f"🌐 Dashboard: http://127.0.0.1:{DASH_PORT}/"
        )
        
        # Always try to edit the message first
        # Use help_keyboard which doesn't have the help button
        try:
            await query.edit_message_text(
                text=help_text,
                parse_mode="Markdown",
                reply_markup=create_help_keyboard()
            )
            logger.info("Help: Successfully edited message to show help")
        except Exception as e:
            logger.warning(f"Help: Could not edit message (will try to send new): {e}")
            # If edit fails, delete the old message and send a new one
            try:
                await query.message.delete()
            except Exception as del_err:
                logger.debug(f"Help: Could not delete message: {del_err}")
            
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=help_text,
                    parse_mode="Markdown",
                    reply_markup=create_help_keyboard()
                )
                logger.info("Help: Sent new message as fallback")
            except Exception as e2:
                logger.error(f"Help: Failed to send new message: {e2}")
        return
    
    # Command execution - create a new Update object with the message from callback query
    # Update objects are immutable, so we need to create a new one
    def create_update_from_query() -> Update:
        """Helper to create Update object from callback query."""
        return UpdateClass(update_id=update.update_id, message=query.message)
    
    # Command execution
    if data == "cmd_run":
        # Create new Update with message from callback query
        cmd_update = create_update_from_query()
        # Store the callback query user in context for run_command to use
        context.user_data['callback_query_user'] = query.from_user
        await run_command(cmd_update, context)
        return
    
    elif data == "cmd_stop":
        cmd_update = create_update_from_query()
        # Store the callback query user in context for stop_command to use
        context.user_data['callback_query_user'] = query.from_user
        await stop_command(cmd_update, context)
        return
    
    elif data == "cmd_restart":
        cmd_update = create_update_from_query()
        # Store the callback query user in context for restart_command to use
        context.user_data['callback_query_user'] = query.from_user
        await restart_command(cmd_update, context)
        return
    
    elif data == "cmd_status":
        # Create Update object - the message should have from_user from the original message
        # But we'll ensure status_command gets the user from callback_query if needed
        cmd_update = create_update_from_query()
        # Store the callback query user in context for status_command to use
        context.user_data['callback_query_user'] = query.from_user
        await status_command(cmd_update, context)
        return
    
    elif data == "cmd_coins":
        # Edit the existing message instead of sending a new one
        await coins_command_edit(query, context, 1)
        await _send_data_menu(chat_id, context)
        return
    
    elif data == "cmd_latest":
        # Delete the previous Data Queries menu message for a cleaner chat
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete Data Queries message: {e}")
        cmd_update = create_update_from_query()
        await latest_command(cmd_update, context)
        await _send_data_menu(chat_id, context)
        return
    
    # Price and marketcap commands with symbol
    elif data.startswith("price_"):
        symbol = data.split("_")[1]
        # Delete the previous Data Queries menu message for a cleaner chat
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete Data Queries message: {e}")
        # Show section description before sending data
        price_desc = (
            "💵 *Price Section*\n\n"
            "Use /price <SYMBOL> to get instant live prices from CoinGecko.\n"
            "This button shows the current price for the selected coin using live API data."
        )
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=price_desc,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.debug(f"Failed to send price section description: {e}")
        context.args = [symbol]
        cmd_update = create_update_from_query()
        await price_command(cmd_update, context)
        await _send_data_menu(chat_id, context)
        return
    
    elif data.startswith("info_"):
        symbol = data.split("_")[1]
        # Delete the previous Data Queries menu message for a cleaner chat
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete Data Queries message: {e}")
        # Show section description before sending data
        info_desc = (
            "📊 *Info Section*\n\n"
            "Use /info <SYMBOL> to get detailed coin information from the dashboard history.\n"
            "This button shows fundamental and historical metrics for the selected coin."
        )
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=info_desc,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.debug(f"Failed to send info section description: {e}")
        context.args = [symbol]
        cmd_update = create_update_from_query()
        await info_command(cmd_update, context)
        await _send_data_menu(chat_id, context)
        return
    
    # Pagination for coins command
    elif data.startswith("coins_page_"):
        page = data.split("_")[2]
        context.args = [page]
        # Edit the existing message instead of sending a new one
        await coins_command_edit(query, context, int(page))
        return
    
    # Chart timeframe switching
    elif data.startswith("chart_"):
        # Format: chart_SYMBOL_TIMEFRAME
        parts = data.split("_")
        if len(parts) >= 3:
            symbol = parts[1]
            timeframe = parts[2]
            context.args = [symbol, timeframe]
            cmd_update = create_update_from_query()
            await chart_command(cmd_update, context)
            await _send_data_menu(chat_id, context)
        return

    # Summary command with symbol (from menu/button)
    elif data.startswith("summary_"):
        symbol = data.split("_")[1]
        # Delete the previous Data Queries menu message for a cleaner chat
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete Data Queries message: {e}")
        summary_desc = (
            "📊 *Summary Section*\n\n"
            "Use /summary <SYMBOL> [1d|1w|1m|1y] to get timeframe performance for price and market cap.\n"
            "This button shows BTC performance across all standard timeframes."
        )
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=summary_desc,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.debug(f"Failed to send summary section description: {e}")
        context.args = [symbol]
        cmd_update = create_update_from_query()
        await summary_command(cmd_update, context)
        await _send_data_menu(chat_id, context)
        return

    # Chart command from menu/button (default BTC, 1y) with section description
    elif data.startswith("chartbtn_"):
        symbol = data.split("_")[1]
        # Delete the previous Data Queries menu message for a cleaner chat
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete Data Queries message: {e}")
        chart_desc = (
            "📈 *Chart Section*\n\n"
            "Use /chart <SYMBOL> [1w|1m|1y] to get price & index charts with dual logarithmic axes.\n"
            "This button shows a BTC chart using the best available data resolution."
        )
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=chart_desc,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.debug(f"Failed to send chart section description: {e}")
        # Default timeframe handled inside chart_command (1y if not provided)
        context.args = [symbol]
        cmd_update = create_update_from_query()
        await chart_command(cmd_update, context)
        await _send_data_menu(chat_id, context)
        return


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_message = (
        "🤖 *Crypto Market Dashboard Bot*\n\n"
        "Welcome! Use the buttons below to control your dashboard and get crypto data.\n\n"
        "You can also use commands directly:\n"
        "/run, /stop, /restart, /status, /price, /coins, /latest, /info, /summary, /chart, /corr, /help"
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


async def about_command_edit(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle about button by editing existing message."""
    about_text = (
        "🤖 *Crypto Market Dashboard Bot*\n\n"
        "This bot allows you to:\n"
        "• Control your dashboard server remotely\n"
        "• Get real-time cryptocurrency prices\n"
        "• View market cap data\n"
        "• Access detailed coin information\n"
        "• Monitor dashboard status\n\n"
        "📊 *Dashboard Control:*\n"
        "Start, stop, restart, and check status of your dashboard server.\n\n"
        "💰 *Data Queries:*\n"
        "Get prices, market caps, and information for 25+ cryptocurrencies.\n\n"
        "🌐 *Network Access:*\n"
        "Access your dashboard from any device on your network.\n\n"
        "💡 *Getting Started:*\n"
        "Use /start to see the main menu, or /help for command list."
    )
    # Edit the existing message instead of sending new
    # Use about_keyboard which only has back button
    try:
        await query.edit_message_text(
            text=about_text,
            parse_mode="Markdown",
            reply_markup=create_about_keyboard()
        )
    except Exception as e:
        logger.debug(f"Could not edit message: {e}")
        # Don't send new message as fallback - just log the error
        logger.warning(f"About: Failed to edit message: {e}")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /about command."""
    # Track user action
    log_user_action(update, "command", "/about")
    about_text = (
        "🤖 *Crypto Market Dashboard Bot*\n\n"
        "This bot allows you to:\n"
        "• Control your dashboard server remotely\n"
        "• Get real-time cryptocurrency prices\n"
        "• View market cap data\n"
        "• Access detailed coin information\n"
        "• Monitor dashboard status\n\n"
        "📊 *Dashboard Control:*\n"
        "Start, stop, restart, and check status of your dashboard server.\n\n"
        "💰 *Data Queries:*\n"
        "Get prices, market caps, and information for 25+ cryptocurrencies.\n\n"
        "🌐 *Network Access:*\n"
        "Access your dashboard from any device on your network.\n\n"
        "💡 *Getting Started:*\n"
        "Use /start to see the main menu, or /help for command list."
    )
    await update.message.reply_text(
        about_text,
        parse_mode="Markdown",
        reply_markup=create_about_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    # Track user action
    log_user_action(update, "command", "/help")
    help_text = (
        "📚 *Help - Crypto Market Dashboard Bot*\n\n"
        "📊 *Dashboard Control:*\n"
        "*/run* - Start the dashboard server\n"
        "*/stop* - Stop the dashboard server\n"
        "*/restart* - Restart the dashboard server\n"
        "*/status* - Check if dashboard is running\n\n"
        "💰 *Data Queries (live, no dashboard needed):*\n"
        "*/price <SYMBOL>* - Instant price (e.g., /price BTC)\n"
        "*/coins* - List all available coins\n"
        "*/latest* - Live prices for all coins\n"
        "*/info <SYMBOL>* - Detailed coin information\n"
        "*/summary <SYMBOL> [1d|1w|1m|1y]* - Timeframe summary\n"
        "*/chart <SYMBOL> [1w|1m|1y]* - Price & index chart image\n\n"
        f"🌐 Dashboard: http://127.0.0.1:{DASH_PORT}/"
    )
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=create_help_keyboard()
    )


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /run command - start the dashboard."""
    # Track user action
    log_user_action(update, "command", "/run")
    
    global dashboard_process, dashboard_thread, dashboard_owners
    
    # Get user from effective_user, or from callback_query if available
    user = update.effective_user
    # If effective_user is the bot itself (happens when called from button), get user from callback_query
    if user and hasattr(user, 'is_bot') and user.is_bot:
        if update.callback_query and update.callback_query.from_user:
            user = update.callback_query.from_user
            logger.debug(f"Run command - got user from callback_query: {user.id} ({user.username})")
        elif context and context.user_data and 'callback_query_user' in context.user_data:
            user = context.user_data['callback_query_user']
            # Clean up after use
            del context.user_data['callback_query_user']
            logger.debug(f"Run command - got user from context: {user.id} ({user.username})")
    
    user_id = user.id if user else None
    logger.debug(f"Run command - final user_id: {user_id} (type: {type(user_id)})")
    
    if not user_id:
        await update.message.reply_text("❌ Could not identify user.")
        return
    
    # Normalize user_id to int for consistent comparison
    user_id_int = int(user_id) if user_id else None
    
    # Use lock to prevent race conditions
    async with dashboard_lock:
        # Normalize all keys in dashboard_owners to int for comparison
        normalized_owners = {int(k): v for k, v in dashboard_owners.items()}
        
        # Check if this user already has a dashboard running
        if user_id_int in normalized_owners:
            owner_info = dashboard_owners[user_id]
            if owner_info["process"] and owner_info["process"].poll() is None:
                await update.message.reply_text(
                    "⚠️ *You already have a dashboard running!*\n\n"
                    "Use /stop to stop your dashboard first."
                )
                return
        
        # Check if any dashboard is running (port check)
        if _check_dashboard_running():
            # Check if current user owns the running dashboard
            user_owns_running = False
            if user_id_int and user_id_int in normalized_owners:
                # User is in owners list and dashboard is running - they own it
                user_owns_running = True
                logger.debug(f"User {user_id_int} owns running dashboard (found in dashboard_owners)")
            
            if user_owns_running:
                # User owns it, suggest using restart instead
                await update.message.reply_text(
                    "⚠️ *Dashboard is already running*\n\n"
                    "You already have a dashboard running.\n"
                    "Use /restart to restart it, or /stop to stop it."
                )
                return
            
            # Find who started it (if not current user)
            running_owner = None
            running_owner_id = None
            
            # First try to find owner with valid process
            for uid, info in normalized_owners.items():
                if uid == user_id_int:
                    continue  # Skip current user
                process = info.get("process")
                if process and process.poll() is None:
                    running_owner = info
                    running_owner_id = uid
                    break
            
            # If no valid process found, check all owners (process might be stale)
            if not running_owner and normalized_owners:
                for uid, info in normalized_owners.items():
                    if uid == user_id_int:
                        continue  # Skip current user
                    running_owner = info
                    running_owner_id = uid
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
        # Ensure user_id is int for consistent storage
        username = user.username if user and user.username else "unknown"
        dashboard_owners[user_id_int] = {
            "process": dashboard_process,
            "started_at": datetime.now(),
            "username": username
        }
        logger.info(f"Stored dashboard owner: user_id={user_id_int} (username={username})")
        
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
        
        import queue
        
        max_wait = BOT_MAX_DASHBOARD_WAIT  # Maximum wait time in seconds (8 minutes for data loading)
        wait_interval = BOT_WAIT_INTERVAL  # Check every 2 seconds
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
                # Note: select module is not available on Windows, using threading approach
                
                def read_stream(stream, stream_name):
                    try:
                        for line in iter(stream.readline, ''):
                            if not line:
                                break
                            line = line.strip()
                            if line:
                                log_queue.put((stream_name, line))
                    except (OSError, IOError, ValueError) as e:
                        logger.debug(f"Error reading stream {stream_name}: {e}")
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
            except Exception as e:
                logger.debug(f"Could not edit loading message: {e}")
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
        except (OSError, socket.error) as e:
            logger.debug(f"Socket check error: {e}")
            pass
        
        # Check process status one more time
        process_exited = dashboard_process.poll() is not None
        if process_exited:
            stderr = ""
            try:
                if dashboard_process.stderr:
                    stderr = dashboard_process.stderr.read()
            except (OSError, IOError) as e:
                logger.debug(f"Error reading stderr: {e}")
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
        except Exception:
            await update.message.reply_text(f"❌ Error: {str(e)}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop command - stop the dashboard."""
    # Track user action
    log_user_action(update, "command", "/stop")
    
    global dashboard_process, dashboard_owners
    
    # Get user from effective_user, or from callback_query if available
    user = update.effective_user
    # If effective_user is the bot itself (happens when called from button), get user from callback_query
    if user and hasattr(user, 'is_bot') and user.is_bot:
        if update.callback_query and update.callback_query.from_user:
            user = update.callback_query.from_user
            logger.debug(f"Stop command - got user from callback_query: {user.id} ({user.username})")
        elif context and context.user_data and 'callback_query_user' in context.user_data:
            user = context.user_data['callback_query_user']
            # Clean up after use
            del context.user_data['callback_query_user']
            logger.debug(f"Stop command - got user from context: {user.id} ({user.username})")
    
    user_id = user.id if user else None
    logger.debug(f"Stop command - final user_id: {user_id} (type: {type(user_id)})")
    
    if not user_id:
        await update.message.reply_text("❌ Could not identify user.")
        return
    
    # Normalize user_id to int for consistent comparison
    user_id_int = int(user_id) if user_id else None
    
    stopped_any = False
    tracked_pid = None
    
    # Check if this user owns a running dashboard
    user_owns_dashboard = False
    dashboard_running = _check_dashboard_running()
    
    # Normalize all keys in dashboard_owners to int for comparison
    normalized_owners = {int(k): v for k, v in dashboard_owners.items()}
    
    # User owns dashboard if:
    # 1. Dashboard is running on port AND
    # 2. User_id is in dashboard_owners (even if process object is stale)
    if dashboard_running and user_id_int in normalized_owners:
        owner_info = normalized_owners[user_id_int]
        dashboard_process = owner_info.get("process")
        if dashboard_process:
            # Process object exists, check if it's still valid
            if dashboard_process.poll() is None:
                tracked_pid = dashboard_process.pid
                user_owns_dashboard = True
            else:
                # Process object is stale but dashboard is still running on port
                # User still owns it (process might have been restarted externally)
                user_owns_dashboard = True
        else:
            # No process object but user is in owners and dashboard is running
            user_owns_dashboard = True
    
    # If user doesn't own a dashboard, check if any dashboard is running
    if not user_owns_dashboard and dashboard_running:
        # Find who owns the running dashboard
        running_owner = None
        running_owner_id = None
        
        # First try to find owner with valid process
        for uid, info in normalized_owners.items():
            process = info.get("process")
            if process and process.poll() is None:
                running_owner = info
                running_owner_id = uid
                break
        
        # If no valid process found but dashboard is running, check all owners
        if not running_owner and normalized_owners:
            # If only one owner exists and dashboard is running, they likely own it
            if len(normalized_owners) == 1:
                uid = list(normalized_owners.keys())[0]
                running_owner = normalized_owners[uid]
                running_owner_id = uid
            else:
                # Multiple owners - use the first one as fallback
                uid = list(normalized_owners.keys())[0]
                running_owner = normalized_owners[uid]
                running_owner_id = uid
        
        if running_owner:
            owner_username = running_owner.get("username", "another user")
            # Check if it's actually the current user (might be stale process check)
            if running_owner_id == user_id_int:
                # User actually owns it, proceed with stop
                logger.debug(f"User {user_id} owns dashboard (matched by ID in stop)")
                user_owns_dashboard = True
            else:
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
            # Remove from owners dict (check both normalized and original key)
            if user_id_int in dashboard_owners:
                del dashboard_owners[user_id_int]
            elif user_id in dashboard_owners:
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
        port_in_use = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', DASH_PORT))
            port_in_use = (result == 0)
            sock.close()
        except (OSError, socket.error) as e:
            logger.debug(f"Socket check error: {e}")
            pass
        
        if port_in_use:
            await update.message.reply_text(
                "⚠️ Dashboard appears to be running but could not be stopped.\n"
                "💡 Try stopping it manually or check process permissions."
            )
        else:
            await update.message.reply_text("⚠️ Dashboard is not running!")


# Track processed updates to prevent duplicates (use deque with maxlen for automatic cleanup)
_processed_updates: deque = deque(maxlen=BOT_PROCESSED_UPDATES_MAX)

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /restart command - restart the dashboard (stop then start)."""
    # Track user action
    log_user_action(update, "command", "/restart")
    
    global dashboard_process, dashboard_owners
    
    # Get user from effective_user, or from callback_query if available
    user = update.effective_user
    if user and hasattr(user, 'is_bot') and user.is_bot:
        if update.callback_query and update.callback_query.from_user:
            user = update.callback_query.from_user
            logger.debug(f"Restart command - got user from callback_query: {user.id} ({user.username})")
        elif context and context.user_data and 'callback_query_user' in context.user_data:
            user = context.user_data['callback_query_user']
            # Clean up after use
            del context.user_data['callback_query_user']
            logger.debug(f"Restart command - got user from context: {user.id} ({user.username})")
    
    user_id = user.id if user else None
    
    if not user_id:
        await update.message.reply_text("❌ Could not identify user.")
        return
    
    # Normalize user_id to int for consistent comparison
    user_id_int = int(user_id) if user_id else None
    
    # Check if dashboard is running and if user owns it
    dashboard_running = _check_dashboard_running()
    user_owns_dashboard = False
    
    # Log current state for debugging
    logger.info(f"Restart command - user_id: {user_id_int} (original: {user_id}, type: {type(user_id)})")
    logger.info(f"Dashboard running: {dashboard_running}")
    logger.info(f"dashboard_owners keys: {list(dashboard_owners.keys())}")
    logger.info(f"dashboard_owners types: {[type(k) for k in dashboard_owners.keys()]}")
    
    # User owns dashboard if:
    # 1. Dashboard is running on port AND
    # 2. User_id is in dashboard_owners (even if process object is stale)
    if dashboard_running:
        # Normalize all keys in dashboard_owners to int for comparison
        normalized_owners = {int(k): v for k, v in dashboard_owners.items()}
        
        if user_id_int in normalized_owners:
            # User is in owners list and dashboard is running - they own it
            user_owns_dashboard = True
            logger.info(f"User {user_id_int} owns dashboard (found in dashboard_owners)")
        else:
            # Dashboard running but user not in owners - check if anyone else owns it
            logger.warning(f"User {user_id_int} not in dashboard_owners. Keys: {list(normalized_owners.keys())}")
    
    if not dashboard_running:
        # Dashboard not running, just start it
        await update.message.reply_text("🔄 Dashboard is not running. Starting it now...")
        await run_command(update, context)
        return
    
    if not user_owns_dashboard:
        # Dashboard is running but user doesn't own it - find who does
        running_owner = None
        running_owner_id = None
        
        # Normalize all keys to int for comparison
        normalized_owners = {int(k): v for k, v in dashboard_owners.items()}
        
        # First try to find owner with valid process
        for uid, info in normalized_owners.items():
            process = info.get("process")
            if process and process.poll() is None:
                running_owner = info
                running_owner_id = uid
                break
        
        # If no valid process found but dashboard is running, check all owners
        # (process might be stale but dashboard still running)
        if not running_owner and normalized_owners:
            # If only one owner exists and dashboard is running, they likely own it
            if len(normalized_owners) == 1:
                uid = list(normalized_owners.keys())[0]
                running_owner = normalized_owners[uid]
                running_owner_id = uid
            else:
                # Multiple owners - use the first one as fallback
                uid = list(normalized_owners.keys())[0]
                running_owner = normalized_owners[uid]
                running_owner_id = uid
        
        if running_owner:
            owner_username = running_owner.get("username", "another user")
            # Compare normalized IDs
            logger.info(f"Restart: Comparing running_owner_id={running_owner_id} (type: {type(running_owner_id)}) vs user_id_int={user_id_int} (type: {type(user_id_int)})")
            
            if running_owner_id == user_id_int:
                # User actually owns it, proceed with restart
                logger.info(f"User {user_id_int} owns dashboard (matched by ID)")
                user_owns_dashboard = True
                # Don't return - continue to restart logic below
            else:
                logger.warning(f"Restart: Ownership mismatch - running_owner_id={running_owner_id} != user_id_int={user_id_int}")
                await update.message.reply_text(
                    f"⚠️ *You don't own the running dashboard*\n\n"
                    f"Started by: @{owner_username}\n"
                    f"Only the owner can restart it."
                )
                return
        else:
            await update.message.reply_text(
                "⚠️ *Dashboard is running, but you don't own it*\n\n"
                "The dashboard was started by another user or manually.\n"
                "Only the owner can restart it."
            )
            return
    
    # User owns the dashboard, proceed with restart
    restart_msg = await update.message.reply_text("🔄 Restarting dashboard...\n⏹️ Stopping current instance...")
    
    try:
        # Stop the dashboard
        await stop_command(update, context)
        
        # Wait a moment for cleanup
        await asyncio.sleep(2)
        
        # Start the dashboard
        await restart_msg.edit_text("🔄 Restarting dashboard...\n▶️ Starting new instance...")
        await run_command(update, context)
        
    except Exception as e:
        logger.error(f"Error restarting dashboard: {e}")
        try:
            await restart_msg.edit_text(f"❌ Error restarting dashboard: {str(e)}")
        except Exception:
            await update.message.reply_text(f"❌ Error restarting dashboard: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - check dashboard status."""
    # Track user action
    log_user_action(update, "command", "/status")
    
    global dashboard_process, _processed_updates, dashboard_owners
    
    # Get user from effective_user, or from callback_query if available
    user = update.effective_user
    # If effective_user is the bot itself (happens when called from button), get user from callback_query
    if user and hasattr(user, 'is_bot') and user.is_bot:
        if update.callback_query and update.callback_query.from_user:
            user = update.callback_query.from_user
            logger.debug(f"Got user from callback_query: {user.id} ({user.username})")
        elif context and context.user_data and 'callback_query_user' in context.user_data:
            user = context.user_data['callback_query_user']
            # Clean up after use
            del context.user_data['callback_query_user']
            logger.debug(f"Got user from context: {user.id} ({user.username})")
    
    user_id = user.id if user else None
    logger.debug(f"Status command - final user_id: {user_id} (type: {type(user_id)})")
    
    # Prevent duplicate responses to the same update
    update_key = f"status_{update.update_id}"
    if update_key in _processed_updates:
        logger.warning(f"Ignoring duplicate status command for update_id {update.update_id}")
        return
    _processed_updates.append(update_key)
    
    # Check if any dashboard is running
    any_dashboard_running = _check_dashboard_running()
    
    # Find who owns the running dashboard (if any)
    running_owner = None
    running_process = None
    if any_dashboard_running:
        # First try to find owner with valid process object
        for uid, info in dashboard_owners.items():
            if info.get("process") and info["process"].poll() is None:
                running_owner = {"user_id": uid, "username": info.get("username", "unknown"), "started_at": info.get("started_at")}
                running_process = info["process"]
                break
        
        # If no owner found but dashboard is running, check if any user in dashboard_owners
        # (process object might be stale but dashboard still running)
        if not running_owner:
            for uid, info in dashboard_owners.items():
                # Dashboard is running and user is in owners list - they likely own it
                running_owner = {"user_id": uid, "username": info.get("username", "unknown"), "started_at": info.get("started_at")}
                running_process = info.get("process")  # Might be None if stale
                break
    
    # Debug logging
    logger.debug(f"Status check - user_id: {user_id} (type: {type(user_id)}), running_owner: {running_owner}")
    if running_owner:
        logger.debug(f"Running owner user_id: {running_owner.get('user_id')} (type: {type(running_owner.get('user_id'))})")
    logger.debug(f"Dashboard owners keys: {list(dashboard_owners.keys())}")
    
    # Check if this user owns the running dashboard
    # Only true if the running owner is the current user
    user_owns_dashboard = False
    user_process = None
    
    # Explicitly check: only set to True if running_owner exists AND matches current user
    # Use explicit type conversion to ensure comparison works
    if running_owner is not None and user_id is not None:
        running_owner_id = running_owner.get("user_id")
        # Ensure both are same type for comparison
        if int(running_owner_id) == int(user_id):
            # Current user owns the running dashboard
            user_owns_dashboard = True
            user_process = running_process
            logger.info(f"User {user_id} owns the running dashboard")
        else:
            logger.info(f"User {user_id} does NOT own dashboard (owned by {running_owner_id})")
    elif user_id and user_id in dashboard_owners:
        # User has a dashboard entry, but it's not the one running (or no dashboard is running)
        owner_info = dashboard_owners[user_id]
        user_process = owner_info["process"]
        # Check if their process is still running (might be stale)
        if user_process and user_process.poll() is not None:
            # Process is dead, remove from owners
            logger.debug(f"Removing stale dashboard entry for user {user_id}")
            del dashboard_owners[user_id]
            user_process = None
    
    # Determine if the current user owns the running dashboard
    bot_started = user_owns_dashboard and (running_owner is not None and running_owner["user_id"] == user_id)
    
    # Also check if dashboard is running on the port (even if not started by bot)
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
        # Explicit check: running_owner must exist AND user_id must match (with type safety)
        if running_owner is not None and user_id is not None:
            running_owner_id = running_owner.get("user_id")
            if running_owner_id is not None and int(running_owner_id) == int(user_id):
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


def _get_local_ip() -> Optional[str]:
    """Get the local IP address for network access."""
    try:
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


def _build_coins_message(page: int) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Build coins list message and keyboard for a given page."""
    from src.constants import COINS, DOM_SYM
    
    # Extract symbols and sort alphabetically
    symbols = sorted([sym for _, sym, _, _ in COINS])
    symbols.append(DOM_SYM)  # Add USDT.D
    
    # Calculate pagination
    total_coins = len(symbols)
    coins_per_page = BOT_COINS_PER_PAGE
    total_pages = (total_coins + coins_per_page - 1) // coins_per_page
    
    if page > total_pages:
        page = total_pages
    if page < 1:
        page = 1
    
    # Calculate start and end indices
    start_idx = (page - 1) * coins_per_page
    end_idx = min(start_idx + coins_per_page, total_coins)
    page_symbols = symbols[start_idx:end_idx]
    
    # Build message
    coins_text = f"💰 *Available Coins ({total_coins} total)*\n"
    coins_text += f"📄 Page {page}/{total_pages}\n\n"
    
    # Format as a clean list (3 columns for better readability)
    for i in range(0, len(page_symbols), 3):
        chunk = page_symbols[i:i+3]
        coins_text += "  ".join(f"`{sym:8s}`" for sym in chunk) + "\n"
    
    coins_text += f"\n💡 Use `/price <SYMBOL>` to get price info"
    
    # Create navigation keyboard
    keyboard_buttons = []
    
    # Pagination buttons
    if total_pages > 1:
        page_buttons = []
        if page > 1:
            page_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"coins_page_{page-1}"))
        if page < total_pages:
            page_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"coins_page_{page+1}"))
        if page_buttons:
            keyboard_buttons.append(page_buttons)
    
    # Back to Data Queries and Back to Main Menu
    keyboard_buttons.append([InlineKeyboardButton("🔙 Back to Data Queries", callback_data="menu_data")])
    keyboard_buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")])
    
    keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
    
    return coins_text, keyboard


async def coins_command_edit(query, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Handle coins pagination by editing existing message."""
    try:
        coins_text, keyboard = _build_coins_message(page)
        await query.edit_message_text(
            coins_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error editing coins message: {e}")
        await query.answer("❌ Error updating page", show_alert=True)


# Rate limiting for bot commands
user_command_times: dict[int, list[datetime]] = defaultdict(list)


# Rate limiting for bot commands
user_command_times: dict[int, list[datetime]] = defaultdict(list)


def rate_limit(max_calls: int = 10, period: int = 60):
    """
    Decorator to rate limit bot commands.
    
    Args:
        max_calls: Maximum number of calls allowed in the period
        period: Time period in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            if not user:
                return await func(update, context)
            
            user_id = user.id
            now = datetime.now()
            
            # Clean old entries
            user_command_times[user_id] = [
                t for t in user_command_times[user_id]
                if now - t < timedelta(seconds=period)
            ]
            
            # Check rate limit
            if len(user_command_times[user_id]) >= max_calls:
                await update.message.reply_text(
                    f"⏳ *Rate limit exceeded*\n\n"
                    f"You've used this command {max_calls} times in the last {period} seconds.\n"
                    f"Please wait {period} seconds before trying again."
                )
                return
            
            # Record this command
            user_command_times[user_id].append(now)
            
            return await func(update, context)
        return wrapper
    return decorator


@rate_limit(max_calls=20, period=60)
async def coins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /coins command - list all available coins with pagination."""
    # Track user action
    log_user_action(update, "command", "/coins")
    
    try:
        # Parse page number from command args
        page = 1
        if context.args and len(context.args) > 0:
            try:
                page = int(context.args[0])
                if page < 1:
                    page = 1
            except ValueError:
                page = 1
        
        coins_text, keyboard = _build_coins_message(page)
        
        await update.message.reply_text(
            coins_text, 
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error listing coins: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


# In-memory cache for instant prices (coin_id -> {data, timestamp})
_instant_price_cache: Dict[str, dict] = {}
INSTANT_PRICE_CACHE_TTL = 60  # seconds


def _fetch_instant_price(coin_id: str, symbol: str) -> Optional[Dict]:
    """Fetch instant/real-time price from CoinGecko /simple/price endpoint.
    
    Returns dict with price, market_cap, change_24h, last_updated or None on failure.
    Results are cached for INSTANT_PRICE_CACHE_TTL seconds.
    """
    global _instant_price_cache
    
    # Check cache first
    now = time.time()
    cache_key = coin_id
    if cache_key in _instant_price_cache:
        cached = _instant_price_cache[cache_key]
        if now - cached["fetched_at"] < INSTANT_PRICE_CACHE_TTL:
            logger.debug(f"Instant price cache hit for {symbol}")
            return cached["data"]
    
    url = f"{COINGECKO_API_BASE}/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": VS_CURRENCY,
        "include_market_cap": "true",
        "include_24hr_change": "true",
        "include_24hr_vol": "true",
        "include_last_updated_at": "true",
    }
    
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            coin_data = data.get(coin_id, {})
            if not coin_data:
                return None
            
            result = {
                "price": coin_data.get(f"{VS_CURRENCY}"),
                "market_cap": coin_data.get(f"{VS_CURRENCY}_market_cap"),
                "change_24h": coin_data.get(f"{VS_CURRENCY}_24h_change"),
                "volume_24h": coin_data.get(f"{VS_CURRENCY}_24h_vol"),
                "last_updated": coin_data.get("last_updated_at"),
            }
            
            # Cache the result
            _instant_price_cache[cache_key] = {
                "data": result,
                "fetched_at": now,
            }
            
            return result
        elif r.status_code == 429:
            logger.warning("CoinGecko rate limit hit for instant price")
            # Return cached data even if expired
            if cache_key in _instant_price_cache:
                return _instant_price_cache[cache_key]["data"]
            return None
        else:
            logger.debug(f"Failed to fetch instant price for {coin_id}: HTTP {r.status_code}")
            return None
    except Exception as e:
        logger.debug(f"Error fetching instant price for {coin_id}: {e}")
        # Return cached data even if expired on error
        if cache_key in _instant_price_cache:
            return _instant_price_cache[cache_key]["data"]
        return None


def _fetch_coin_details(coin_id: str) -> Optional[Dict]:
    """Fetch coin details (circulating supply, total supply) from CoinGecko API."""
    
    url = f"{COINGECKO_API_BASE}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false"
    }
    
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            market_data = data.get("market_data", {})
            return {
                "circulating_supply": market_data.get("circulating_supply"),
                "total_supply": market_data.get("total_supply"),
            }
        else:
            logger.debug(f"Failed to fetch coin details for {coin_id}: HTTP {r.status_code}")
            return None
    except Exception as e:
        logger.debug(f"Error fetching coin details for {coin_id}: {e}")
        return None


def _find_coin_info(symbol: str) -> Optional[Tuple[str, str, str]]:
    """Find coin_id, category, and group for a symbol."""
    from src.constants import COINS
    for cid, sym, c, g in COINS:
        if sym.upper() == symbol.upper():
            return cid, c, g
    return None


def _load_single_coin_data(symbol: str) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[Tuple[str, str]]]:
    """Load data for a single coin only (faster for price command)."""
    from src.data.fetcher import fetch_market_caps_retry
    
    # Find the coin_id for this symbol
    coin_info = _find_coin_info(symbol)
    if not coin_info:
        return None, None, None
    
    coin_id, cat, grp = coin_info
    
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
                df_prices = pd.DataFrame(js["prices"], columns=["ts", "price"])
                df_prices["date"] = pd.to_datetime(df_prices["ts"], unit="ms").dt.floor("D")
                df_prices = df_prices.sort_values("ts").groupby("date", as_index=False).last()
                price_series = df_prices.set_index("date")["price"].sort_index()
        except Exception as e:
            logger.debug(f"Failed to load price data for {symbol}: {e}")
    
    return mc_series, price_series, (cat, grp)


def validate_symbol(symbol: str) -> bool:
    """Validate coin symbol format."""
    # Allow alphanumeric characters, 1-10 characters long
    return bool(re.match(r'^[A-Z0-9]{1,10}$', symbol.upper()))


def format_timestamp(date_obj) -> str:
    """Format timestamp from date object."""
    if hasattr(date_obj, 'hour'):
        return date_obj.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return date_obj.strftime('%Y-%m-%d') + " (date only)"


async def safe_delete_loading_message(loading_msg) -> None:
    """Safely delete loading message if it exists."""
    if loading_msg:
        try:
            await loading_msg.delete()
        except Exception as e:
            logger.debug(f"Could not delete loading message: {e}")


async def create_loading_message(update: Update) -> Optional:
    """Create and return a loading message."""
    try:
        return await update.message.reply_text("🔄 Loading data...\n⏳ This may take a few seconds...")
    except Exception as e:
        logger.debug(f"Could not create loading message: {e}")
        return None


async def update_loading_progress(loading_msg, delay: float = 2.0) -> asyncio.Task:
    """Create a task to update loading message progress."""
    async def update_progress():
        await asyncio.sleep(delay)
        if loading_msg:
            try:
                await loading_msg.edit_text("🔄 Loading data...\n⏳ Processing cached data...")
            except Exception:
                pass
    
    return asyncio.create_task(update_progress())


def _check_dashboard_running() -> bool:
    """Check if dashboard is running (by bot or manually)."""
    global dashboard_process
    
    # Check if bot's tracked process is running
    if dashboard_process and dashboard_process.poll() is None:
        return True
    
    # Check if port is in use
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', DASH_PORT))
        port_in_use = (result == 0)
        sock.close()
        if port_in_use:
            return True
    except Exception:
        pass
    
    # Check for main.py processes
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'main.py' in ' '.join(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    
    return False


@rate_limit(max_calls=15, period=60)
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /price command - get instant/real-time price for a coin.
    
    Fetches live data directly from CoinGecko API. No dashboard required.
    Falls back to cached historical data if API call fails and dashboard is running.
    """
    # Track user action (use BTC as default when no symbol provided)
    symbol = context.args[0].upper() if context.args and len(context.args) > 0 else "BTC"
    log_user_action(update, "command", f"/price {symbol}")
    
    # Default to BTC if no symbol argument is provided
    if not context.args:
        context.args = ["BTC"]
    
    symbol = context.args[0].upper()
    
    # Validate symbol format
    if not validate_symbol(symbol):
        await update.message.reply_text(
            "❌ Invalid symbol format.\n\n"
            "💡 Symbol must be 1-10 alphanumeric characters.\n"
            "Example: BTC, ETH, DOGE"
        )
        return
    
    # Special case: commodities (Gold XAU, Silver XAG, Copper XCU) via Yahoo Finance
    if symbol in {"XAU", "XAG", "XCU"}:
        from src.data import fetch_latest_commodity_price
        loop = asyncio.get_event_loop()
        price = await loop.run_in_executor(None, fetch_latest_commodity_price, symbol)
        if price is None:
            await update.message.reply_text(
                f"❌ Could not fetch price for {symbol} (commodity).\n\n"
                "💡 The external price source may be temporarily unavailable. Please try again later."
            )
            return
        price_text = (
            f"💰 *{symbol} Price* (commodity)\n\n"
            f"Price: ${price:,.2f}\n\n"
            "Source: Yahoo Finance futures data"
        )
        await update.message.reply_text(price_text, parse_mode="Markdown")
        return
    
    # Find coin_id for this symbol (crypto)
    coin_info = _find_coin_info(symbol)
    if not coin_info:
        await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
        return
    
    coin_id = coin_info[0]
    
    try:
        # Fetch instant price from CoinGecko API (no dashboard needed)
        loop = asyncio.get_event_loop()
        instant_data = await loop.run_in_executor(None, _fetch_instant_price, coin_id, symbol)
        
        if instant_data and instant_data.get("price") is not None:
            # Build response from live data
            price = instant_data["price"]
            market_cap = instant_data.get("market_cap")
            change_24h = instant_data.get("change_24h")
            volume_24h = instant_data.get("volume_24h")
            last_updated_ts = instant_data.get("last_updated")
            
            price_text = f"💰 *{symbol} Price*\n\n"
            price_text += f"Price: ${price:,.2f}\n"
            
            if market_cap:
                if market_cap >= 1e12:
                    mc_str = f"${market_cap / 1e12:.2f}T"
                elif market_cap >= 1e9:
                    mc_str = f"${market_cap / 1e9:.2f}B"
                elif market_cap >= 1e6:
                    mc_str = f"${market_cap / 1e6:.2f}M"
                else:
                    mc_str = f"${market_cap:,.0f}"
                price_text += f"Market Cap: {mc_str}\n"
            
            if volume_24h:
                if volume_24h >= 1e9:
                    vol_str = f"${volume_24h / 1e9:.2f}B"
                elif volume_24h >= 1e6:
                    vol_str = f"${volume_24h / 1e6:.2f}M"
                else:
                    vol_str = f"${volume_24h:,.0f}"
                price_text += f"24h Volume: {vol_str}\n"
            
            if change_24h is not None:
                change_emoji = "📈" if change_24h >= 0 else "📉"
                price_text += f"{change_emoji} 24h Change: {change_24h:+.2f}%\n"
            
            # Format last updated timestamp
            if last_updated_ts:
                updated_dt = datetime.utcfromtimestamp(last_updated_ts)
                price_text += f"\nLast updated: {updated_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            
            await update.message.reply_text(price_text, parse_mode="Markdown")
            return
        
        # Fallback: try cached historical data if dashboard is running
        if _check_dashboard_running():
            mc_series, price_series, meta = await loop.run_in_executor(None, _load_single_coin_data, symbol)
            
            if mc_series is not None:
                latest_mc = mc_series.iloc[-1]
                latest_date = mc_series.index[-1]
                latest_price = None
                change_24h = None
                
                if price_series is not None:
                    price_series = price_series.dropna()
                    if not price_series.empty:
                        latest_price = price_series.iloc[-1]
                        if len(price_series) > 1:
                            prev_price = price_series.iloc[-2]
                            change_24h = ((latest_price - prev_price) / prev_price) * 100
                
                timestamp_str = format_timestamp(latest_date)
                
                price_text = f"💰 *{symbol} Price* _(cached)_\n\n"
                if latest_price is not None:
                    price_text += f"Price: ${latest_price:,.2f}\n"
                price_text += f"Market Cap: ${latest_mc:,.0f}\n"
                if change_24h is not None:
                    change_emoji = "📈" if change_24h >= 0 else "📉"
                    price_text += f"{change_emoji} 24h Change: {change_24h:+.2f}%\n"
                price_text += f"\nLast updated: {timestamp_str}\n"
                
                await update.message.reply_text(price_text, parse_mode="Markdown")
                return
        
        # Both instant and cached failed
        await update.message.reply_text(
            f"❌ Could not fetch price for {symbol}.\n\n"
            "💡 CoinGecko API may be temporarily unavailable.\n"
            "Please try again in a moment."
        )
        
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


def _fetch_all_instant_prices() -> Optional[Dict]:
    """Fetch instant prices for all coins from CoinGecko /simple/price endpoint.
    
    Returns dict of {symbol: {price, market_cap, change_24h}} or None.
    """
    from src.constants import COINS
    
    coin_ids = [cid for cid, _, _, _ in COINS]
    ids_str = ",".join(coin_ids)
    
    url = f"{COINGECKO_API_BASE}/simple/price"
    params = {
        "ids": ids_str,
        "vs_currencies": VS_CURRENCY,
        "include_market_cap": "true",
        "include_24hr_change": "true",
        "include_last_updated_at": "true",
    }
    
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            result = {}
            for cid, sym, _, _ in COINS:
                coin_data = data.get(cid, {})
                if coin_data and coin_data.get(VS_CURRENCY) is not None:
                    result[sym] = {
                        "price": coin_data.get(VS_CURRENCY),
                        "market_cap": coin_data.get(f"{VS_CURRENCY}_market_cap"),
                        "change_24h": coin_data.get(f"{VS_CURRENCY}_24h_change"),
                        "last_updated": coin_data.get("last_updated_at"),
                    }
            return result
        else:
            logger.debug(f"Failed to fetch all instant prices: HTTP {r.status_code}")
            return None
    except Exception as e:
        logger.debug(f"Error fetching all instant prices: {e}")
        return None


@rate_limit(max_calls=10, period=60)
async def latest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /latest command - get latest prices for all coins.
    
    Uses instant CoinGecko data when available, falls back to cached data
    if dashboard is running.
    """
    # Track user action
    log_user_action(update, "command", "/latest")
    
    loading_msg = None
    try:
        loading_msg = await create_loading_message(update)
        loop = asyncio.get_event_loop()
        
        # Try instant prices first (no dashboard needed)
        instant_prices = await loop.run_in_executor(None, _fetch_all_instant_prices)
        
        if instant_prices:
            # Sort by market cap descending
            sorted_coins = sorted(
                instant_prices.items(),
                key=lambda x: x[1].get("market_cap") or 0,
                reverse=True
            )
            
            latest_text = "📊 *Latest Prices*\n\n"
            
            for sym, data in sorted_coins:
                price = data["price"]
                change = data.get("change_24h")
                
                line = f"{sym}: ${price:,.2f}"
                if change is not None:
                    emoji = "📈" if change >= 0 else "📉"
                    line += f"  {emoji} {change:+.1f}%"
                latest_text += line + "\n"
            
            # Timestamp from first coin's last_updated
            first_ts = next(iter(instant_prices.values()), {}).get("last_updated")
            if first_ts:
                updated_dt = datetime.utcfromtimestamp(first_ts)
                latest_text += f"\nLast updated: {updated_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            
            # Send (split if needed)
            await safe_delete_loading_message(loading_msg)
            if len(latest_text) > BOT_MAX_MESSAGE_LENGTH:
                # Split into chunks
                lines = latest_text.split("\n")
                header = lines[0] + "\n\n"
                current_msg = header
                for line in lines[2:]:
                    if len(current_msg) + len(line) + 1 > BOT_MAX_MESSAGE_LENGTH:
                        await update.message.reply_text(current_msg, parse_mode="Markdown")
                        current_msg = line + "\n"
                    else:
                        current_msg += line + "\n"
                if current_msg.strip():
                    await update.message.reply_text(current_msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(latest_text, parse_mode="Markdown")
            return
        
        # Fallback: cached data from dashboard
        if not _check_dashboard_running():
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text(
                "❌ Could not fetch live prices.\n\n"
                "💡 CoinGecko API may be temporarily unavailable.\n"
                "Please try again in a moment."
            )
            return
        
        # Start progress update task
        progress_task = await update_loading_progress(loading_msg)
        
        # Load data in executor (non-blocking)
        dm = await loop.run_in_executor(None, _load_data_manager)
        
        # Cancel progress update if still running
        progress_task.cancel()
        
        if dm.df_raw is None or dm.df_raw.empty:
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text("❌ No data available. Try running the dashboard first.")
            return
        
        latest_text = f"📊 *Latest Prices* _(cached)_\n"
        latest_date = dm.df_raw.index[-1]
        latest_text += f"Date: {latest_date.strftime('%Y-%m-%d')}\n\n"
        
        # Show ALL coins
        from src.app.callbacks import _load_price_data
        prices_dict = _load_price_data()
        
        symbols_to_show = dm.symbols_all
        
        for sym in symbols_to_show:
            if sym in prices_dict:
                price_series = prices_dict[sym].dropna()
                if not price_series.empty:
                    price = price_series.iloc[-1]
                    latest_text += f"{sym}: ${price:,.2f}\n"
                elif sym in dm.series:
                    mc = dm.series[sym].iloc[-1]
                    latest_text += f"{sym}: MC ${mc:,.0f}\n"
            elif sym in dm.series:
                mc = dm.series[sym].iloc[-1]
                latest_text += f"{sym}: MC ${mc:,.0f}\n"
        
        latest_text += f"\nLast updated: {format_timestamp(latest_date)}\n"
        
        await safe_delete_loading_message(loading_msg)
        
        if len(latest_text) > BOT_MAX_MESSAGE_LENGTH:
            lines = latest_text.split("\n")
            header = lines[0] + "\n" + lines[1] + "\n\n"
            current_msg = header
            for line in lines[3:]:
                if len(current_msg) + len(line) + 1 > BOT_MAX_MESSAGE_LENGTH:
                    await update.message.reply_text(current_msg, parse_mode="Markdown")
                    current_msg = line + "\n"
                else:
                    current_msg += line + "\n"
            if current_msg.strip():
                await update.message.reply_text(current_msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(latest_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting latest prices: {e}")
        await safe_delete_loading_message(loading_msg)
        await update.message.reply_text(f"❌ Error: {str(e)}")


@rate_limit(max_calls=15, period=60)
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /info command - get detailed information for a coin."""
    # Track user action (use BTC as default when no symbol provided)
    symbol = context.args[0].upper() if context.args and len(context.args) > 0 else "BTC"
    log_user_action(update, "command", f"/info {symbol}")
    
    # Default to BTC if no symbol argument is provided
    if not context.args:
        context.args = ["BTC"]
    
    symbol = context.args[0].upper()
    
    # Validate symbol format
    if not validate_symbol(symbol):
        await update.message.reply_text(
            "❌ Invalid symbol format.\n\n"
            "💡 Symbol must be 1-10 alphanumeric characters.\n"
            "Example: BTC, ETH, DOGE"
        )
        return
    
    # Special case: commodities - provide basic info without requiring dashboard
    if symbol in {"XAU", "XAG", "XCU"}:
        from src.data import fetch_latest_commodity_price
        loop = asyncio.get_event_loop()
        price = await loop.run_in_executor(None, fetch_latest_commodity_price, symbol)
        if price is None:
            await update.message.reply_text(
                f"ℹ️ *{symbol} Information (Commodity)*\n\n"
                "Basic info is available, but the latest price could not be fetched right now.\n"
                "Please try again later or use /price for a fresh quote.",
                parse_mode="Markdown",
            )
            return

        pretty_name = {
            "XAU": "Gold (XAU)",
            "XAG": "Silver (XAG)",
            "XCU": "Copper (XCU)",
        }.get(symbol, symbol)

        info_text = (
            f"📊 *{pretty_name} Information (Commodity)*\n\n"
            f"Category: Commodity\n"
            f"Group: Metals\n\n"
            f"Latest Price: ${price:,.2f}\n\n"
            "Detailed on-chain metrics and market cap are not available for commodities in this bot yet.\n"
            "Use /chart for a historical price chart."
        )
        await update.message.reply_text(info_text, parse_mode="Markdown")
        return

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
        loading_msg = await create_loading_message(update)
        loop = asyncio.get_event_loop()
        
        # Start progress update task
        progress_task = await update_loading_progress(loading_msg)
        
        # Load data in executor (non-blocking)
        dm = await loop.run_in_executor(None, _load_data_manager)
        
        # Cancel progress update if still running
        progress_task.cancel()
        
        if symbol not in dm.series:
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
            return
        
        # Get coin_id for fetching supply data
        coin_info = _find_coin_info(symbol)
        coin_id = coin_info[0] if coin_info else None
        
        info_text = f"📊 *{symbol} Information*\n\n"
        
        # Category and group
        if symbol in dm.meta:
            cat, grp = dm.meta[symbol]
            info_text += f"Category: {cat}\n"
            info_text += f"Group: {grp}\n\n"
        
        # Latest data
        series = dm.series[symbol]
        latest_mc = series.iloc[-1]
        latest_date = series.index[-1]
        first_mc = series.iloc[0]
        first_date = series.index[0]
        
        info_text += f"Latest Market Cap: ${latest_mc:,.0f}\n"
        info_text += f"Date: {latest_date.strftime('%Y-%m-%d')}\n"
        
        # Price if available
        from src.app.callbacks import _load_price_data
        prices_dict = _load_price_data()
        price_series = None
        if symbol in prices_dict:
            price_series = prices_dict[symbol].dropna()
            if not price_series.empty:
                latest_price = price_series.iloc[-1]
                info_text += f"Latest Price: ${latest_price:,.2f}\n"
        
        info_text += "\n"
        
        # Supply Information
        if coin_id:
            coin_details = await loop.run_in_executor(None, _fetch_coin_details, coin_id)
            if coin_details:
                info_text += "📊 *Supply Information*\n"
                if coin_details.get("circulating_supply"):
                    circ_supply = coin_details["circulating_supply"]
                    # Format large numbers
                    if circ_supply >= 1e9:
                        circ_supply_str = f"{circ_supply / 1e9:.2f}B"
                    elif circ_supply >= 1e6:
                        circ_supply_str = f"{circ_supply / 1e6:.2f}M"
                    elif circ_supply >= 1e3:
                        circ_supply_str = f"{circ_supply / 1e3:.2f}K"
                    else:
                        circ_supply_str = f"{circ_supply:,.0f}"
                    info_text += f"Circulating Supply: {circ_supply_str} {symbol}\n"
                
                if coin_details.get("total_supply"):
                    total_supply = coin_details["total_supply"]
                    if total_supply >= 1e9:
                        total_supply_str = f"{total_supply / 1e9:.2f}B"
                    elif total_supply >= 1e6:
                        total_supply_str = f"{total_supply / 1e6:.2f}M"
                    elif total_supply >= 1e3:
                        total_supply_str = f"{total_supply / 1e3:.2f}K"
                    else:
                        total_supply_str = f"{total_supply:,.0f}"
                    info_text += f"Total Supply: {total_supply_str} {symbol}\n"
                info_text += "\n"
        
        # Price Performance
        if price_series is not None and not price_series.empty:
            first_price = price_series.iloc[0]
            current_price = price_series.iloc[-1]
            
            # Calculate indexed price (first = 100)
            indexed_price = (current_price / first_price) * 100
            price_change_pct = ((current_price - first_price) / first_price) * 100
            
            # All-time high/low
            all_time_high = price_series.max()
            all_time_high_idx = price_series.idxmax()
            all_time_low = price_series.min()
            all_time_low_idx = price_series.idxmin()
            
            info_text += "📈 *Price Performance*\n"
            info_text += f"Current Price: ${current_price:,.2f}\n"
            info_text += f"Indexed Price (Start = 100): {indexed_price:,.2f}\n"
            
            # Format percentage change with directional emoji
            change_sign = "+" if price_change_pct >= 0 else ""
            change_emoji = "📈" if price_change_pct >= 0 else "📉"
            info_text += f"{change_emoji} Change from Start: {change_sign}{price_change_pct:,.2f}%\n"
            
            info_text += f"All-time High: ${all_time_high:,.2f} ({all_time_high_idx.strftime('%Y-%m-%d')})\n"
            info_text += f"All-time Low: ${all_time_low:,.2f} ({all_time_low_idx.strftime('%Y-%m-%d')})\n"
            info_text += "\n"
        
        # Market Cap Performance
        mc_change_pct = ((latest_mc - first_mc) / first_mc) * 100
        info_text += "💎 *Market Cap Performance*\n"
        info_text += f"Current Market Cap: ${latest_mc:,.0f}\n"
        change_sign = "+" if mc_change_pct >= 0 else ""
        change_emoji = "📈" if mc_change_pct >= 0 else "📉"
        info_text += f"{change_emoji} Change from Start: {change_sign}{mc_change_pct:,.2f}%\n"
        info_text += "\n"
        
        # Data Range
        info_text += "📅 *Data Range*\n"
        info_text += f"First Date: {first_date.strftime('%Y-%m-%d')}\n"
        info_text += f"Last Date: {latest_date.strftime('%Y-%m-%d')}\n"
        info_text += f"Data Points: {len(series)}\n"
        
        # Add timestamp at the end
        info_text += f"\nLast updated: {format_timestamp(latest_date)}\n"
        
        await safe_delete_loading_message(loading_msg)
        await update.message.reply_text(info_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting info for {symbol}: {e}")
        await safe_delete_loading_message(loading_msg)
        await update.message.reply_text(f"❌ Error: {str(e)}")


def _compute_timeframe_change(series: Optional[pd.Series], days: int) -> Optional[Dict]:
    """Compute percentage and absolute change over a timeframe.

    Uses the last value in the series as 'current' and compares it to the
    value from approximately `days` ago (or earliest available if not enough data).
    """
    if series is None or series.empty:
        return None

    # Ensure series is sorted by index
    series = series.sort_index()

    end_value = series.iloc[-1]
    end_date = series.index[-1]

    if pd.isna(end_value):
        return None

    target_date = end_date - pd.Timedelta(days=days)

    # Use the last value at or before target_date as the starting point
    subset = series[series.index <= end_date]
    if subset.empty:
        return None

    start_candidates = subset[subset.index <= target_date]
    if not start_candidates.empty:
        start_value = start_candidates.iloc[-1]
        start_date = start_candidates.index[-1]
    else:
        # Not enough history; fall back to earliest available value
        start_value = subset.iloc[0]
        start_date = subset.index[0]

    if pd.isna(start_value) or start_value == 0:
        return None

    abs_change = float(end_value - start_value)
    pct_change = (abs_change / float(start_value)) * 100.0

    # High/low within the period (from start_date to end_date)
    period_series = series[(series.index >= start_date) & (series.index <= end_date)].dropna()
    if period_series.empty:
        high = low = float(end_value)
    else:
        high = float(period_series.max())
        low = float(period_series.min())

    return {
        "start_value": float(start_value),
        "end_value": float(end_value),
        "abs_change": abs_change,
        "pct_change": pct_change,
        "start_date": start_date,
        "end_date": end_date,
        "high": high,
        "low": low,
    }


@rate_limit(max_calls=10, period=60)
async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /summary command - 1d, 1w, 1m, 1y summary for a coin."""
    # Parse args - default to BTC when no symbol is provided
    if not context.args:
        context.args = ["BTC"]

    symbol = context.args[0].upper()
    timeframe_arg = context.args[1].lower() if len(context.args) > 1 else "all"

    # Track user action
    log_user_action(update, "command", f"/summary {symbol} {timeframe_arg}")

    # Validate symbol format
    if not validate_symbol(symbol):
        await update.message.reply_text(
            "❌ Invalid symbol format.\n\n"
            "💡 Symbol must be 1-10 alphanumeric characters.\n"
            "Example: BTC, ETH, DOGE"
        )
        return

    # Validate timeframe
    valid_timeframes = {"1d": 1, "1w": 7, "1m": 30, "1y": 365}
    if timeframe_arg != "all" and timeframe_arg not in valid_timeframes:
        await update.message.reply_text(
            "❌ Invalid timeframe.\n\n"
            "Supported timeframes: 1d, 1w, 1m, 1y, or omit to show all.\n"
            "Examples:\n"
            "/summary BTC\n"
            "/summary BTC 1w"
        )
        return

    # Special case: commodities - summaries are not yet backed by full historical metrics
    if symbol in {"XAU", "XAG", "XCU"}:
        await update.message.reply_text(
            f"📊 *{symbol} Summary (Commodity)*\n\n"
            "Commodities currently support /price for live quotes and /chart for historical price charts.\n"
            "Detailed timeframe summaries (1d/1w/1m/1y) are not implemented for commodities yet.",
            parse_mode="Markdown",
        )
        return

    # Require dashboard data (DataManager)
    if not _check_dashboard_running():
        await update.message.reply_text(
            "⚠️ *Dashboard is offline*\n\n"
            "💡 The dashboard needs to be running to access historical data.\n"
            "Use /run to start the dashboard first."
        )
        return

    loading_msg = None
    try:
        loading_msg = await create_loading_message(update)
        loop = asyncio.get_event_loop()

        # Load data manager in executor (non-blocking)
        dm = await loop.run_in_executor(None, _load_data_manager)

        if symbol not in dm.series:
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
            return

        mc_series = dm.series[symbol]
        latest_mc = mc_series.iloc[-1]
        latest_date = mc_series.index[-1]

        # Load price data
        from src.app.callbacks import _load_price_data

        prices_dict = _load_price_data()
        price_series = prices_dict.get(symbol)
        if price_series is not None:
            price_series = price_series.dropna().sort_index()

        # Determine which timeframes to compute
        if timeframe_arg == "all":
            timeframes = valid_timeframes
        else:
            timeframes = {timeframe_arg: valid_timeframes[timeframe_arg]}

        lines = [f"📊 *{symbol} Summary*"]
        lines.append("")
        lines.append(f"Latest Price/Market Cap as of {latest_date.strftime('%Y-%m-%d')}:")

        # Latest price if available
        latest_price = None
        if price_series is not None and not price_series.empty:
            latest_price = float(price_series.iloc[-1])
            lines.append(f"Price: ${latest_price:,.2f}")
        lines.append(f"Market Cap: ${latest_mc:,.0f}")
        lines.append("")

        # Per-timeframe stats
        for tf_label, days in timeframes.items():
            price_change = _compute_timeframe_change(price_series, days) if price_series is not None else None
            mc_change = _compute_timeframe_change(mc_series, days)

            # Skip timeframe if we have neither price nor MC change
            if price_change is None and mc_change is None:
                continue

            pretty_label = {
                "1d": "1 Day",
                "1w": "1 Week",
                "1m": "1 Month",
                "1y": "1 Year",
            }.get(tf_label, tf_label)

            lines.append(f"⏱ *{pretty_label}*")

            if price_change is not None:
                pct = price_change["pct_change"]
                abs_ch = price_change["abs_change"]
                start_val = price_change["start_value"]
                end_val = price_change["end_value"]
                emoji = "📈" if pct >= 0 else "📉"
                lines.append(
                    f"{emoji} Price: {pct:+.2f}%  "
                    f"(${abs_ch:+,.2f}, {price_change['start_date'].strftime('%Y-%m-%d')} → "
                    f"{price_change['end_date'].strftime('%Y-%m-%d')})"
                )
                lines.append(
                    f"   ${start_val:,.2f} → ${end_val:,.2f}"
                )

                # Only show high/low for 1y by default (to avoid clutter)
                if tf_label == "1y":
                    lines.append(
                        f"   Low (1y): ${price_change['low']:,.2f}  |  "
                        f"High (1y): ${price_change['high']:,.2f}"
                    )

            if mc_change is not None:
                pct = mc_change["pct_change"]
                abs_ch = mc_change["abs_change"]
                start_val = mc_change["start_value"]
                end_val = mc_change["end_value"]
                emoji = "📈" if pct >= 0 else "📉"
                lines.append(
                    f"{emoji} Market Cap: {pct:+.2f}%  "
                    f"(${abs_ch:+,.0f}, {mc_change['start_date'].strftime('%Y-%m-%d')} → "
                    f"{mc_change['end_date'].strftime('%Y-%m-%d')})"
                )
                # Format market cap nicely (B/M/K)
                if start_val >= 1e12:
                    start_str = f"${start_val / 1e12:.2f}T"
                elif start_val >= 1e9:
                    start_str = f"${start_val / 1e9:.2f}B"
                elif start_val >= 1e6:
                    start_str = f"${start_val / 1e6:.2f}M"
                else:
                    start_str = f"${start_val:,.0f}"
                
                if end_val >= 1e12:
                    end_str = f"${end_val / 1e12:.2f}T"
                elif end_val >= 1e9:
                    end_str = f"${end_val / 1e9:.2f}B"
                elif end_val >= 1e6:
                    end_str = f"${end_val / 1e6:.2f}M"
                else:
                    end_str = f"${end_val:,.0f}"
                
                lines.append(
                    f"   {start_str} → {end_str}"
                )

            lines.append("")

        # If nothing was added (very short history)
        if len(lines) <= 4:
            lines.append("⚠️ Not enough historical data to compute summaries for this coin.")

        # Add timestamp at the end
        lines.append(f"Last updated: {format_timestamp(latest_date)}")

        await safe_delete_loading_message(loading_msg)
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error getting summary for {symbol}: {e}")
        await safe_delete_loading_message(loading_msg)
        await update.message.reply_text(f"❌ Error: {str(e)}")


def _fetch_hourly_price_data(coin_id: str, days: int) -> Optional[pd.Series]:
    """Fetch hourly price data from CoinGecko API for chart generation.
    
    CoinGecko returns hourly data automatically when days <= 90.
    
    Args:
        coin_id: CoinGecko coin ID
        days: Number of days to fetch (7 for 1w, 30 for 1m)
    
    Returns:
        Price Series with hourly data (datetime index) or None on error
    """
    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": VS_CURRENCY,
        "days": days,
        # No interval parameter - CoinGecko auto-returns hourly for days <= 90
    }
    
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            prices = data.get("prices", [])
            
            if not prices:
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(prices, columns=["ts", "price"])
            df["date"] = pd.to_datetime(df["ts"], unit="ms")
            df = df.sort_values("date")
            
            # Set datetime index and return price series
            # Ensure price column is float64 to preserve precision for small values
            df["price"] = df["price"].astype("float64")
            price_series = df.set_index("date")["price"].sort_index()
            return price_series
        else:
            logger.debug(f"Failed to fetch hourly data for {coin_id}: HTTP {r.status_code}")
            return None
    except Exception as e:
        logger.debug(f"Error fetching hourly data for {coin_id}: {e}")
        return None


def _generate_chart_image(symbol: str, coin_id: str, price_series: pd.Series, timeframe: str, days: int) -> Optional[Path]:
    """Generate a chart image with dual Y-axes (price on left, indexed on right), both logarithmic.
    
    Uses best resolution available:
    - 1w/1m: Fetches hourly data from CoinGecko (uses hourly data directly)
    - 1y: Uses daily data from DataManager
    
    Args:
        symbol: Coin symbol
        coin_id: CoinGecko coin ID (for fetching hourly data)
        price_series: Daily price series with date index (fallback for 1y)
        timeframe: Label for timeframe ("1w", "1m", "1y")
        days: Number of days to show
    
    Returns:
        Path to generated PNG file or None on error
    """
    try:
        # For 1w and 1m, fetch hourly data and use it directly
        if timeframe in ("1w", "1m"):
            hourly_data = _fetch_hourly_price_data(coin_id, days)
            if hourly_data is None or hourly_data.empty:
                logger.warning(f"Could not fetch hourly data for {symbol}, falling back to daily")
                # Fall back to daily data
                timeframe_data = price_series.sort_index().dropna()
            else:
                # Use hourly data directly (no resampling)
                timeframe_data = hourly_data.sort_index().dropna()
        else:
            # For 1y, use daily data
            if price_series.empty:
                return None
            
            price_series = price_series.sort_index().dropna()
            if price_series.empty:
                return None
            
            end_date = price_series.index[-1]
            start_date = end_date - pd.Timedelta(days=days)
            
            # Filter to timeframe
            timeframe_data = price_series[price_series.index >= start_date].dropna()
        
        if timeframe_data.empty or len(timeframe_data) < 2:
            return None
        
        # Ensure data is float64 to preserve precision for small values
        timeframe_data = timeframe_data.astype("float64")
        
        # Filter out any zero or negative values (data quality check)
        timeframe_data = timeframe_data[timeframe_data > 0]
        if timeframe_data.empty or len(timeframe_data) < 2:
            logger.warning(f"No valid positive price data for {symbol}")
            return None
        
        # Calculate indexed price (normalized to start at 100)
        first_price = timeframe_data.iloc[0]
        indexed_price = (timeframe_data / first_price) * 100
        
        # Determine appropriate decimal precision based on price range
        max_price = timeframe_data.max()
        min_price = timeframe_data.min()
        
        # Log price range for debugging
        logger.debug(f"Chart for {symbol}: min=${min_price:.8f}, max=${max_price:.8f}, count={len(timeframe_data)}")
        
        # Verify we have valid data (not all zeros)
        if timeframe_data.sum() == 0 or all(v == 0 for v in timeframe_data.values):
            logger.error(f"All price values are zero for {symbol} - cannot generate chart")
            return None
        
        # Determine tick format and hover precision based on price magnitude
        if max_price < 0.01:
            # Very small prices (< $0.01): use 6 decimal places
            tick_format = '$,.6f'
            hover_precision = 6
        elif max_price < 0.1:
            # Small prices (< $0.1): use 4 decimal places
            tick_format = '$,.4f'
            hover_precision = 4
        elif max_price < 1:
            # Prices < $1: use 3 decimal places
            tick_format = '$,.3f'
            hover_precision = 3
        elif max_price < 1000:
            # Prices < $1000: use 2 decimal places
            tick_format = '$,.2f'
            hover_precision = 2
        else:
            # Large prices: use 0 decimal places (whole dollars)
            tick_format = '$,.0f'
            hover_precision = 2  # Still show 2 decimals in hover
        
        # Create figure with dual Y-axes
        fig = go.Figure()
        
        # Determine date format based on timeframe
        # For 1w/1m (hourly), show date and time; for 1y (daily), show date only
        if timeframe in ("1w", "1m"):
            date_format = '%Y-%m-%d %H:%M'
            xaxis_title = 'Date & Time'
        else:
            date_format = '%Y-%m-%d'
            xaxis_title = 'Date'
        
        # Add price trace (left Y-axis)
        # Ensure values are float64 and not rounded
        price_values = timeframe_data.values.astype("float64")
        
        fig.add_trace(go.Scatter(
            x=timeframe_data.index,
            y=price_values,  # Use explicitly typed values
            mode='lines',
            name=f'{symbol} Price',
            line=dict(width=2, color='#1f77b4'),
            yaxis='y',
            hovertemplate=f'<b>%{{fullData.name}}</b><br>' +
                         f'Date: %{{x|{date_format}}}<br>' +
                         f'Price: $%{{y:,.{hover_precision}f}}<extra></extra>'
        ))
        
        # Add indexed price trace (right Y-axis)
        fig.add_trace(go.Scatter(
            x=indexed_price.index,
            y=indexed_price.values,
            mode='lines',
            name=f'{symbol} Index',
            line=dict(width=2, color='#ff7f0e', dash='dash'),
            yaxis='y2',
            hovertemplate=f'<b>%{{fullData.name}}</b><br>' +
                         f'Date: %{{x|{date_format}}}<br>' +
                         'Index: %{y:.2f}<extra></extra>'
        ))
        
        # Format timeframe label
        timeframe_labels = {
            "1w": "1 Week",
            "1m": "1 Month",
            "1y": "1 Year"
        }
        timeframe_label = timeframe_labels.get(timeframe, timeframe)
        
        # Update layout with dual Y-axes (both logarithmic)
        fig.update_layout(
            title=dict(
                text=f'{symbol} Price & Index - Last {timeframe_label}',
                font=dict(size=16)
            ),
            xaxis=dict(
                title=xaxis_title,
                type='date',
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)'
            ),
            yaxis=dict(
                title='Price (USD)',
                type='log',
                side='left',
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
                tickformat=tick_format,
                # For very small values, use exponent format which works better with log scales
                exponentformat='power' if max_price < 0.01 else 'none'
            ),
            yaxis2=dict(
                title='Index (100 = start)',
                type='log',
                side='right',
                overlaying='y',
                showgrid=False,
                tickformat='.1f'
            ),
            hovermode='x unified',
            template='plotly_white',
            width=1200,
            height=600,
            margin=dict(l=80, r=80, t=60, b=60),
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='rgba(0,0,0,0.2)',
                borderwidth=1
            )
        )
        
        # Create charts directory if it doesn't exist
        charts_dir = PROJECT_ROOT / "charts"
        charts_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chart_filename = f"{symbol}_{timeframe}_{timestamp}.png"
        chart_path = charts_dir / chart_filename
        
        # Export to PNG (kaleido is default engine)
        try:
            fig.write_image(str(chart_path), width=1200, height=600, scale=2)
            logger.debug(f"Chart saved to {chart_path}")
            return chart_path
        except Exception as e:
            logger.error(f"Failed to export chart image: {e}")
            # Check if kaleido is installed
            try:
                import kaleido
                logger.debug("kaleido is installed but export failed")
            except ImportError:
                logger.error("kaleido not installed. Install with: pip install kaleido")
            return None
            
    except Exception as e:
        logger.error(f"Error generating chart for {symbol}: {e}")
        return None


def _generate_commodity_chart_image(symbol: str, timeframe: str, days: int) -> Optional[Path]:
    """
    Generate a chart image for a commodity (XAU/XAG/XCU) using Yahoo Finance daily data.

    The chart mirrors the crypto chart style: price on left Y-axis (log), indexed series on right Y-axis (log).
    """
    from src.data import fetch_commodity_history

    try:
        # Fetch historical daily data
        price_series = fetch_commodity_history(symbol, days)
        if price_series is None or price_series.empty:
            logger.warning(f"No historical commodity data available for {symbol}")
            return None

        price_series = price_series.sort_index().dropna()
        if price_series.empty:
            return None

        # Ensure we only use the last `days` of data
        end_date = price_series.index[-1]
        start_date = end_date - pd.Timedelta(days=days)
        timeframe_data = price_series[price_series.index >= start_date].dropna()

        if timeframe_data.empty or len(timeframe_data) < 2:
            logger.warning(f"Not enough historical commodity data for {symbol} to generate chart")
            return None

        timeframe_data = timeframe_data.astype("float64")
        timeframe_data = timeframe_data[timeframe_data > 0]
        if timeframe_data.empty or len(timeframe_data) < 2:
            logger.warning(f"No valid positive commodity price data for {symbol}")
            return None

        # Indexed series (start at 100)
        first_price = timeframe_data.iloc[0]
        indexed_price = (timeframe_data / first_price) * 100

        max_price = timeframe_data.max()
        min_price = timeframe_data.min()
        logger.debug(f"Commodity chart for {symbol}: min=${min_price:.8f}, max=${max_price:.8f}, count={len(timeframe_data)}")

        if timeframe_data.sum() == 0 or all(v == 0 for v in timeframe_data.values):
            logger.error(f"All commodity price values are zero for {symbol} - cannot generate chart")
            return None

        # Tick format / precision similar to crypto charts
        if max_price < 0.01:
            tick_format = '$,.6f'
            hover_precision = 6
        elif max_price < 0.1:
            tick_format = '$,.4f'
            hover_precision = 4
        elif max_price < 1:
            tick_format = '$,.3f'
            hover_precision = 3
        elif max_price < 1000:
            tick_format = '$,.2f'
            hover_precision = 2
        else:
            tick_format = '$,.0f'
            hover_precision = 2

        fig = go.Figure()

        # For commodities we always use daily data, so date-only labels are fine
        date_format = '%Y-%m-%d'
        xaxis_title = 'Date'

        # Price trace
        price_values = timeframe_data.values.astype("float64")
        fig.add_trace(go.Scatter(
            x=timeframe_data.index,
            y=price_values,
            mode='lines',
            name=f'{symbol} Price',
            line=dict(width=2, color='#1f77b4'),
            yaxis='y',
            hovertemplate=f'<b>%{{fullData.name}}</b><br>'
                         f'Date: %{{x|{date_format}}}<br>'
                         f'Price: $%{{y:,.{hover_precision}f}}<extra></extra>'
        ))

        # Indexed trace
        fig.add_trace(go.Scatter(
            x=indexed_price.index,
            y=indexed_price.values,
            mode='lines',
            name=f'{symbol} Index',
            line=dict(width=2, color='#ff7f0e', dash='dash'),
            yaxis='y2',
            hovertemplate=f'<b>%{{fullData.name}}</b><br>'
                         f'Date: %{{x|{date_format}}}<br>'
                         'Index: %{y:.2f}<extra></extra>'
        ))

        timeframe_labels = {
            "1w": "1 Week",
            "1m": "1 Month",
            "1y": "1 Year",
        }
        timeframe_label = timeframe_labels.get(timeframe, timeframe)

        fig.update_layout(
            title=dict(
                text=f'{symbol} Price & Index (Commodity) - Last {timeframe_label}',
                font=dict(size=16),
            ),
            xaxis=dict(
                title=xaxis_title,
                type='date',
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
            ),
            yaxis=dict(
                title='Price (USD)',
                type='log',
                side='left',
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
                tickformat=tick_format,
                exponentformat='power' if max_price < 0.01 else 'none',
            ),
            yaxis2=dict(
                title='Index (100 = start)',
                type='log',
                side='right',
                overlaying='y',
                showgrid=False,
                tickformat='.1f',
            ),
            hovermode='x unified',
            template='plotly_white',
            width=1200,
            height=600,
            margin=dict(l=80, r=80, t=60, b=60),
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='rgba(0,0,0,0.2)',
                borderwidth=1,
            ),
        )

        charts_dir = PROJECT_ROOT / "charts"
        charts_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chart_filename = f"{symbol}_commodity_{timeframe}_{timestamp}.png"
        chart_path = charts_dir / chart_filename

        try:
            fig.write_image(str(chart_path), width=1200, height=600, scale=2)
            logger.debug(f"Commodity chart saved to {chart_path}")
            return chart_path
        except Exception as e:
            logger.error(f"Failed to export commodity chart image: {e}")
            try:
                import kaleido  # noqa: F401
                logger.debug("kaleido is installed but export failed for commodity chart")
            except ImportError:
                logger.error("kaleido not installed. Install with: pip install kaleido")
            return None

    except Exception as e:
        logger.error(f"Error generating commodity chart for {symbol}: {e}")
        return None


def _generate_two_coin_1y_chart(symbol_a: str, symbol_b: str) -> Optional[Path]:
    """Generate a 1-year indexed comparison chart for two coins (both normalized to 100 at start). Returns path to PNG or None."""
    from src.app.callbacks import _load_price_data
    prices_dict = _load_price_data()
    pa = prices_dict.get(symbol_a)
    pb = prices_dict.get(symbol_b)
    if pa is None or pa.empty or pb is None or pb.empty:
        return None
    pa = pa.dropna().sort_index()
    pb = pb.dropna().sort_index()
    # Align to common dates (inner join), then take last 365 days
    common = pa.index.intersection(pb.index).sort_values()
    if len(common) < 2:
        return None
    end = common[-1]
    start_365 = end - pd.Timedelta(days=365)
    common = common[common >= start_365]
    if len(common) < 2:
        return None
    pa = pa.reindex(common).ffill().bfill()
    pb = pb.reindex(common).ffill().bfill()
    # Index both to 100 at first date
    base_a = pa.iloc[0]
    base_b = pb.iloc[0]
    if base_a <= 0 or base_b <= 0:
        return None
    idx_a = (pa / base_a) * 100
    idx_b = (pb / base_b) * 100
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=idx_a.index, y=idx_a.values, mode="lines", name=symbol_a,
        line=dict(width=2), hovertemplate=f"{symbol_a}: %{{y:.1f}}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=idx_b.index, y=idx_b.values, mode="lines", name=symbol_b,
        line=dict(width=2), hovertemplate=f"{symbol_b}: %{{y:.1f}}<extra></extra>"
    ))
    fig.update_layout(
        title=dict(text=f"1 Year Comparison — {symbol_a} vs {symbol_b} (Index 100 = start)", font=dict(size=14)),
        xaxis=dict(title="Date", type="date", showgrid=True),
        yaxis=dict(title="Index (100 = start)", showgrid=True, tickformat=".0f"),
        hovermode="x unified",
        template="plotly_white",
        width=900,
        height=500,
        margin=dict(l=60, r=40, t=50, b=50),
        legend=dict(x=0.02, y=0.98),
    )
    charts_dir = PROJECT_ROOT / "charts"
    charts_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = charts_dir / f"corr_1y_{symbol_a}_{symbol_b}_{timestamp}.png"
    try:
        fig.write_image(str(path), width=900, height=500, scale=2)
        return path
    except Exception as e:
        logger.debug(f"Failed to export 1y comparison chart: {e}")
        return None


def _compute_and_export_correlation(symbol_a: str, symbol_b: str) -> Tuple[str, Optional[Path]]:
    """Compute correlation for two symbols and export scatter plot to PNG. Returns (message_text, image_path or None)."""
    from src.app.callbacks import compute_correlation_for_bot
    dm = _load_data_manager()
    if dm.df_raw is None or dm.df_raw.empty:
        return "No market cap data loaded. Use /run to start the dashboard, then try again.", None
    corr_text, fig = compute_correlation_for_bot(dm.df_raw, symbol_a, symbol_b)
    # Check for error responses (dashboard returns these as text)
    if corr_text.startswith("Select exactly") or corr_text.startswith("Not enough") or corr_text.startswith("Cannot") or corr_text.startswith("No market cap"):
        return corr_text, None
    charts_dir = PROJECT_ROOT / "charts"
    charts_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_filename = f"corr_{symbol_a}_{symbol_b}_{timestamp}.png"
    chart_path = charts_dir / chart_filename
    try:
        fig.write_image(str(chart_path), width=900, height=600, scale=2)
        return corr_text, chart_path
    except Exception as e:
        logger.error(f"Failed to export correlation image: {e}")
        return corr_text, None


@rate_limit(max_calls=10, period=60)
async def corr_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /corr command - correlation between two coins (default: BTC and ETH). Full output as main program + chart image."""
    # Default: BTC and ETH
    if not context.args or len(context.args) < 2:
        context.args = ["BTC", "ETH"]
    symbol_a = context.args[0].upper()
    symbol_b = context.args[1].upper()
    log_user_action(update, "command", f"/corr {symbol_a} {symbol_b}")
    if not validate_symbol(symbol_a) or not validate_symbol(symbol_b):
        await update.message.reply_text(
            "❌ Invalid symbol format. Use 1–10 alphanumeric characters.\nExample: /corr BTC ETH"
        )
        return
    if not _check_dashboard_running():
        await update.message.reply_text(
            "⚠️ *Dashboard is offline*\n\nCorrelation uses dashboard market cap data. Use /run to start it first.",
            parse_mode="Markdown"
        )
        return
    loading_msg = None
    try:
        loading_msg = await create_loading_message(update)
        loop = asyncio.get_event_loop()
        corr_text, chart_path = await loop.run_in_executor(
            None, _compute_and_export_correlation, symbol_a, symbol_b
        )
        await safe_delete_loading_message(loading_msg)
        if chart_path and chart_path.exists():
            caption = (
                f"📊 Correlation: {symbol_a} vs {symbol_b}\n\n"
                f"{corr_text}"
            )
            with open(chart_path, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption[:1024] if len(caption) > 1024 else caption,
                )
        else:
            await update.message.reply_text(f"📊 Correlation\n\n{corr_text}")
        # Issue #40: also send 1-year comparison chart of the two coins
        chart_1y_path = await loop.run_in_executor(None, _generate_two_coin_1y_chart, symbol_a, symbol_b)
        if chart_1y_path and chart_1y_path.exists():
            with open(chart_1y_path, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=f"📈 1 Year comparison: {symbol_a} vs {symbol_b} (index 100 = start)",
                )
    except Exception as e:
        logger.error(f"Error in correlation for {symbol_a} vs {symbol_b}: {e}")
        await safe_delete_loading_message(loading_msg)
        await update.message.reply_text(f"❌ Error: {str(e)}")


@rate_limit(max_calls=10, period=60)
async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chart command - generate and send chart image with dual Y-axes (price + indexed)."""
    # Parse args - default to BTC and 1y when no arguments provided
    if not context.args:
        context.args = ["BTC"]
    
    symbol = context.args[0].upper()
    timeframe_arg = context.args[1].lower() if len(context.args) > 1 else "1y"
    
    # Track user action
    log_user_action(update, "command", f"/chart {symbol} {timeframe_arg}")
    
    # Validate symbol format
    if not validate_symbol(symbol):
        await update.message.reply_text(
            "❌ Invalid symbol format.\n\n"
            "💡 Symbol must be 1-10 alphanumeric characters.\n"
            "Example: BTC, ETH, DOGE"
        )
        return
    
    # Validate timeframe
    valid_timeframes = {"1w": 7, "1m": 30, "1y": 365}
    if timeframe_arg not in valid_timeframes:
        await update.message.reply_text(
            "❌ Invalid timeframe.\n\n"
            "Supported timeframes: 1w, 1m, 1y\n"
            "Examples:\n"
            "/chart BTC\n"
            "/chart BTC 1w\n"
            "/chart ETH 1m"
        )
        return
    
    days = valid_timeframes[timeframe_arg]

    # Special case: commodities (Gold XAU, Silver XAG, Copper XCU) via Yahoo Finance
    if symbol in {"XAU", "XAG", "XCU"}:
        loading_msg = None
        try:
            loading_msg = await create_loading_message(update)
            loop = asyncio.get_event_loop()
            # Run blocking history fetch + chart generation in executor
            chart_path = await loop.run_in_executor(
                None,
                _generate_commodity_chart_image,
                symbol,
                timeframe_arg,
                days,
            )
            if chart_path is None or not chart_path.exists():
                await safe_delete_loading_message(loading_msg)
                await update.message.reply_text(
                    f"❌ Failed to generate chart for {symbol} (commodity).\n\n"
                    "💡 The external price source may be temporarily unavailable or missing data. Please try again later."
                )
                return

            # Build caption (simpler than crypto, but consistent)
            timeframe_labels = {"1w": "1 Week", "1m": "1 Month", "1y": "1 Year"}
            timeframe_label = timeframe_labels.get(timeframe_arg, timeframe_arg)

            await safe_delete_loading_message(loading_msg)
            with open(chart_path, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=f"📈 *{symbol} Price & Index (Commodity) - Last {timeframe_label}*",
                    parse_mode="Markdown",
                )
            try:
                chart_path.unlink()
            except Exception as e:
                logger.debug(f"Could not delete commodity chart file: {e}")
        except Exception as e:
            logger.error(f"Error generating commodity chart for {symbol}: {e}")
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text(f"❌ Error generating commodity chart for {symbol}: {str(e)}")
        return

    # Require dashboard data
    if not _check_dashboard_running():
        await update.message.reply_text(
            "⚠️ *Dashboard is offline*\n\n"
            "💡 The dashboard needs to be running to access historical data.\n"
            "Use /run to start the dashboard first."
        )
        return
    
    loading_msg = None
    try:
        loading_msg = await create_loading_message(update)
        loop = asyncio.get_event_loop()
        
        # Load data manager
        dm = await loop.run_in_executor(None, _load_data_manager)
        
        if symbol not in dm.series:
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
            return
        
        # Get coin_id for fetching hourly data
        coin_info = _find_coin_info(symbol)
        if not coin_info:
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
            return
        
        coin_id = coin_info[0]
        
        # Load price data (used as fallback for 1y or if hourly fetch fails)
        from src.app.callbacks import _load_price_data
        
        prices_dict = _load_price_data()
        price_series = prices_dict.get(symbol)
        
        if price_series is None or price_series.empty:
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text(
                f"❌ No price data available for {symbol}.\n\n"
                "💡 Price data may not be loaded yet. Try again after dashboard finishes loading."
            )
            return
        
        price_series = price_series.dropna().sort_index()
        
        # Generate chart image
        await loading_msg.edit_text("🔄 Generating chart...\n⏳ Creating image...")
        
        chart_path = await loop.run_in_executor(
            None, 
            _generate_chart_image, 
            symbol,
            coin_id,
            price_series, 
            timeframe_arg, 
            days
        )
        
        if chart_path is None or not chart_path.exists():
            await safe_delete_loading_message(loading_msg)
            await update.message.reply_text(
                f"❌ Failed to generate chart for {symbol}.\n\n"
                "💡 Make sure kaleido is installed: pip install kaleido"
            )
            return
        
        # Build caption
        timeframe_labels = {"1w": "1 Week", "1m": "1 Month", "1y": "1 Year"}
        timeframe_label = timeframe_labels.get(timeframe_arg, timeframe_arg)
        
        latest_price = price_series.iloc[-1]
        latest_date = price_series.index[-1]
        
        # Calculate date range
        end_date = price_series.index[-1]
        start_date = end_date - pd.Timedelta(days=days)
        timeframe_data = price_series[price_series.index >= start_date].dropna()
        
        # Date format for caption
        if timeframe_arg in ("1w", "1m"):
            date_format = '%Y-%m-%d %H:%M'
            resolution_note = " (hourly data)"
        else:
            date_format = '%Y-%m-%d'
            resolution_note = ""
        
        if not timeframe_data.empty:
            first_price = timeframe_data.iloc[0]
            first_date = timeframe_data.index[0]
            high_price = timeframe_data.max()
            low_price = timeframe_data.min()
            
            # Determine appropriate decimal precision for caption based on price range
            max_price_caption = max(high_price, latest_price, abs(first_price))
            if max_price_caption < 0.01:
                price_format = ',.6f'  # 6 decimal places for very small prices
            elif max_price_caption < 0.1:
                price_format = ',.4f'  # 4 decimal places for small prices
            elif max_price_caption < 1:
                price_format = ',.3f'  # 3 decimal places for prices < $1
            elif max_price_caption < 1000:
                price_format = ',.2f'  # 2 decimal places for normal prices
            else:
                price_format = ',.2f'  # 2 decimal places for large prices (still show cents)
            
            caption = (
                f"📈 *{symbol} Price & Index - Last {timeframe_label}{resolution_note}*\n\n"
                f"📅 {first_date.strftime(date_format)} → {latest_date.strftime(date_format)}\n\n"
                f"💵 Current Price: ${latest_price:{price_format}}\n"
                f"📊 High: ${high_price:{price_format}}  |  Low: ${low_price:{price_format}}\n\n"
                f"📈 Left axis: Price (USD, log scale)\n"
                f"📊 Right axis: Index (100 = start, log scale)\n\n"
                f"Last updated: {format_timestamp(latest_date)}"
            )
        else:
            caption = (
                f"📈 *{symbol} Price & Index - Last {timeframe_label}*\n\n"
                f"Last updated: {format_timestamp(latest_date)}"
            )
        
        # Create keyboard with timeframe options
        keyboard_buttons = []
        timeframe_row = []
        for tf in ["1w", "1m", "1y"]:
            if tf != timeframe_arg:
                timeframe_row.append(InlineKeyboardButton(
                    tf.upper(), 
                    callback_data=f"chart_{symbol}_{tf}"
                ))
        if timeframe_row:
            keyboard_buttons.append(timeframe_row)
        keyboard_buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")])
        keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
        
        # Send chart image
        await safe_delete_loading_message(loading_msg)
        
        with open(chart_path, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        
        # Clean up chart file
        try:
            chart_path.unlink()
        except Exception as e:
            logger.debug(f"Could not delete chart file: {e}")
        
    except Exception as e:
        logger.error(f"Error generating chart for {symbol}: {e}")
        await safe_delete_loading_message(loading_msg)
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
    
    # Clean up stale dashboard owners on startup
    global dashboard_owners
    for user_id, info in list(dashboard_owners.items()):
        if info["process"] and info["process"].poll() is not None:
            logger.info(f"Cleaning up stale dashboard entry for user {user_id}")
            del dashboard_owners[user_id]
    
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
            except Exception as e:
                logger.debug(f"Error closing bot: {e}")
                pass
    except Exception as e:
        logger.warning(f"Could not initialize bot for webhook check: {e}. Continuing anyway...")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register bot commands for command bar (shows when user presses "/")
    try:
        commands = [
            BotCommand("start", "Start the bot and show main menu"),
            BotCommand("help", "Show help and available commands"),
            BotCommand("about", "Learn what this bot does and its features"),
            BotCommand("run", "Start the dashboard server"),
            BotCommand("stop", "Stop the dashboard server"),
            BotCommand("restart", "Restart the dashboard server"),
            BotCommand("status", "Check if dashboard is running"),
            BotCommand("price", "Instant live price for a coin (e.g., /price BTC)"),
            BotCommand("coins", "List all available coins"),
            BotCommand("latest", "Live prices for all coins"),
            BotCommand("info", "Get detailed information for a coin (e.g., /info BTC)"),
            BotCommand("summary", "1d/1w/1m/1y price & market cap summary"),
            BotCommand("chart", "Price & index chart (1w/1m/1y, e.g., /chart BTC 1m)"),
            BotCommand("corr", "Correlation between two coins (default: BTC ETH)"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands registered successfully")
    except Exception as e:
        logger.warning(f"Could not register bot commands: {e}. Continuing anyway...")
    
    # Set bot description and short description
    try:
        await application.bot.set_my_description(
            "🤖 Control your Crypto Market Dashboard remotely via Telegram. "
            "Start/stop dashboard, get real-time prices, market caps, and detailed coin information. "
            "Access your dashboard from anywhere on your network."
        )
        await application.bot.set_my_short_description(
            "Control Crypto Market Dashboard & get crypto data"
        )
        logger.info("Bot description and short description set successfully")
    except Exception as e:
        logger.warning(f"Could not set bot description: {e}. Continuing anyway...")
    
    # Register callback query handler (for buttons) - must be before command handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("run", run_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("restart", restart_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Data query handlers
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("coins", coins_command))
    application.add_handler(CommandHandler("latest", latest_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("chart", chart_command))
    application.add_handler(CommandHandler("corr", corr_command))
    
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

