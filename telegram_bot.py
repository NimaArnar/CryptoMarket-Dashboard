"""Telegram bot for Crypto Market Dashboard control."""
import os
import subprocess
import threading
import time
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config import DASH_PORT
from src.data_manager import DataManager
from src.utils import setup_logger

logger = setup_logger(__name__)

# Global variable to track if dashboard is running
dashboard_process: Optional[subprocess.Popen] = None
dashboard_thread: Optional[threading.Thread] = None
data_manager: Optional[DataManager] = None

# Telegram Bot Token (set via environment variable)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_message = (
        "🤖 *Crypto Market Dashboard Bot*\n\n"
        "📊 *Dashboard Control:*\n"
        "/run - Start the dashboard\n"
        "/stop - Stop the dashboard\n"
        "/status - Check dashboard status\n\n"
        "💰 *Data Queries:*\n"
        "/price BTC - Get latest price\n"
        "/marketcap ETH - Get market cap\n"
        "/coins - List all available coins\n"
        "/latest - Latest prices for all coins\n"
        "/info BTC - Detailed coin information\n\n"
        "/help - Show detailed help"
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    
    stopped_any = False
    tracked_pid = None
    
    # Get the tracked process PID before stopping it
    if dashboard_process and dashboard_process.poll() is None:
        tracked_pid = dashboard_process.pid
    
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


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - check dashboard status."""
    global dashboard_process
    
    # Check if our tracked process is running
    bot_started = dashboard_process and dashboard_process.poll() is None
    
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
    tracked_pid = dashboard_process.pid if bot_started else None
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
    if bot_started or port_in_use or main_py_pids:
        status_text = "✅ *Dashboard Status: RUNNING*\n\n"
        status_text += f"🌐 URL: http://127.0.0.1:{DASH_PORT}/\n"
        
        if bot_started:
            status_text += f"📊 Process ID: {dashboard_process.pid}\n"
            status_text += "🤖 Started by bot"
            # Also show manually started processes if any
            if main_py_pids:
                if len(main_py_pids) == 1:
                    status_text += f"\n⚠️ Also running (manual): PID {main_py_pids[0]}"
                else:
                    status_text += f"\n⚠️ Also running (manual): PIDs {', '.join(map(str, main_py_pids))}"
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
    """Load data manager (lazy loading)."""
    global data_manager
    if data_manager is None:
        # Run data loading in executor to avoid event loop conflicts
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_load_data_sync)
            data_manager = future.result()
    return data_manager


def _load_data_sync() -> DataManager:
    """Load data synchronously (run in thread to avoid event loop issues)."""
    dm = DataManager()
    dm.load_all_data()
    return dm


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /price command - get latest price for a coin."""
    if not context.args:
        await update.message.reply_text("❌ Please specify a coin symbol. Example: /price BTC")
        return
    
    symbol = context.args[0].upper()
    loading_msg = None
    
    try:
        # Load data in executor to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()
        dm = await loop.run_in_executor(None, _load_data_manager)
        
        if symbol not in dm.series:
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Use /coins to see available coins.")
            return
        
        # Get latest market cap and calculate price
        series = dm.series[symbol]
        latest_mc = series.iloc[-1]
        latest_date = series.index[-1]
        
        # Load price data if available
        from src.app.callbacks import _load_price_data
        prices_dict = _load_price_data()
        
        latest_price = None
        change_24h = None
        change_emoji = ""
        
        if symbol in prices_dict:
            price_series = prices_dict[symbol].dropna()
            if not price_series.empty:
                latest_price = price_series.iloc[-1]
                # Calculate 24h change if possible
                if len(price_series) > 1:
                    prev_price = price_series.iloc[-2]
                    change_24h = ((latest_price - prev_price) / prev_price) * 100
                    change_emoji = "📈" if change_24h >= 0 else "📉"
        
        # If no price data, calculate from market cap and Q supply
        if latest_price is None:
            # Try to calculate from market cap / Q supply
            if dm.df_raw is not None and symbol in dm.df_raw.columns:
                latest_mc_from_df = dm.df_raw[symbol].iloc[-1]
                # Q supply = MC / Price, so Price = MC / Q
                # We need to get Q from somewhere or estimate
                latest_price = latest_mc_from_df / 1_000_000  # Rough estimate
                price_text = (
                    f"💰 *{symbol} Price*\n\n"
                    f"💵 Estimated Price: ${latest_price:,.2f}\n"
                    f"💎 Market Cap: ${latest_mc:,.0f}\n"
                    f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
                    f"⚠️ Note: Price estimated from market cap\n"
                )
            else:
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
        
        if symbol in dm.meta:
            cat, grp = dm.meta[symbol]
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
    if not context.args:
        await update.message.reply_text("❌ Please specify a coin symbol. Example: /marketcap BTC")
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
    loading_msg = None
    try:
        loading_msg = await update.message.reply_text("🔄 Loading data...")
        import asyncio
        loop = asyncio.get_event_loop()
        dm = await loop.run_in_executor(None, _load_data_manager)
        
        if not dm.symbols_all:
            await update.message.reply_text("❌ No coins loaded. Try running the dashboard first.")
            return
        
        coins_text = f"📋 *Available Coins ({len(dm.symbols_all)})*\n\n"
        
        # Group by category
        by_category = {}
        for sym in dm.symbols_all:
            if sym in dm.meta:
                cat, _ = dm.meta[sym]
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(sym)
        
        for cat, symbols in sorted(by_category.items()):
            coins_text += f"*{cat}:*\n"
            coins_text += ", ".join(symbols) + "\n\n"
        
        # Split if too long (Telegram has 4096 char limit)
        if len(coins_text) > 4000:
            coins_text = coins_text[:4000] + "\n... (truncated)"
        
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(coins_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error listing coins: {e}")
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def latest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /latest command - get latest prices for all coins."""
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
    if not context.args:
        await update.message.reply_text("❌ Please specify a coin symbol. Example: /info BTC")
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
    
    # Data query handlers
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("marketcap", marketcap_command))
    application.add_handler(CommandHandler("coins", coins_command))
    application.add_handler(CommandHandler("latest", latest_command))
    application.add_handler(CommandHandler("info", info_command))
    
    # Start the bot
    logger.info("Starting Telegram bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

