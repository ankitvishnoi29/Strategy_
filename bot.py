import time
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from nse_helper import generate_chat_table, process_df, get_excel_buffer, get_sma_custom_excel_buffer
from sma_helper import run_sma_daily_scanner, run_sma_single_stock_backtest
import watchlists

try:
    from nselib import capital_market
except ImportError:
    print("nselib is not installed. Please install it using: pip install nselib")
    import sys
    sys.exit(1)

BOT_TOKEN = "8876447777:AAH5kTvJG8iOqUS32U2v7dI48FmC3c__4eA" 
bot = telebot.TeleBot(BOT_TOKEN)

# --- USER DATA MANAGEMENT ---
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_users(users_data):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users_data, f, indent=4)
    except Exception as e:
        print(f"Error saving users: {e}")

user_profiles = load_users()
user_action_data = {}

# Strategy ID to Display Name Mapping
STRATEGY_MAP = {
    # Online Batch Strategies
    "sma": "SMA Dashboard",
    "rob": "Rob Booker - Knoxwill Div",
    "av20": "AV20 Dashboard",
    "rhs": "Reverse Head & Shoulder",
    "cwh": "Cup with Handle",
    "v10": "V10",
    "3x3": "3 Times in 3 years",
    "highdiv": "High Dividend Dashboard",
    # Offline Batch Strategies
    "bv": "Book Value Strategy",
    "2x2": "2 times in 2 years",
    "4x4": "4 times in 4 years",
    "pivot": "One Day (Pivot Points)",
    "t20": "T20 Strategy",
    "tm": "Test Match Strategy",
    # YouTube Strategies
    "stoch": "Stochastic Momentum",
    "52w": "52-Week High/Low Dashboard",
    "st": "Supertrend Indicator",
    "rb": "Range Bound Strategy"
}

# --- MENU MARKUPS ---
def get_main_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("Update Profile", callback_data="update_profile"))
    markup.row(InlineKeyboardButton("🌐 Online Batch Strategies", callback_data="menu_online"))
    markup.row(InlineKeyboardButton("🔌 Offline Batch Strategies", callback_data="menu_offline"))
    markup.row(InlineKeyboardButton("▶️ YouTube Strategies", callback_data="menu_youtube"))
    markup.row(InlineKeyboardButton("Any Stock Testing", callback_data="dev_phase"))
    markup.row(InlineKeyboardButton("NSE Deals Tracker", callback_data="show_bulkdeal_menu"))
    markup.row(InlineKeyboardButton("Company Watchlists", callback_data="show_watchlist_menu"))
    return markup

def get_online_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("SMA Dashboard", callback_data="show_strat_sma"))
    markup.row(InlineKeyboardButton("Rob Booker - Knoxwill Div", callback_data="show_strat_rob"))
    markup.row(InlineKeyboardButton("AV20 Dashboard", callback_data="show_strat_av20"))
    markup.row(InlineKeyboardButton("Reverse Head & Shoulder", callback_data="show_strat_rhs"))
    markup.row(InlineKeyboardButton("Cup with Handle", callback_data="show_strat_cwh"))
    markup.row(InlineKeyboardButton("V10", callback_data="show_strat_v10"))
    markup.row(InlineKeyboardButton("3 Times in 3 years", callback_data="show_strat_3x3"))
    markup.row(InlineKeyboardButton("High Dividend Dashboard", callback_data="show_strat_highdiv"))
    markup.row(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return markup

def get_offline_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("Book Value Strategy", callback_data="show_strat_bv"))
    markup.row(InlineKeyboardButton("2 times in 2 years", callback_data="show_strat_2x2"))
    markup.row(InlineKeyboardButton("4 times in 4 years", callback_data="show_strat_4x4"))
    markup.row(InlineKeyboardButton("One Day (Pivot Points)", callback_data="show_strat_pivot"))
    markup.row(InlineKeyboardButton("T20 Strategy", callback_data="show_strat_t20"))
    markup.row(InlineKeyboardButton("Test Match Strategy", callback_data="show_strat_tm"))
    markup.row(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return markup

def get_youtube_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("Stochastic Momentum", callback_data="show_strat_stoch"))
    markup.row(InlineKeyboardButton("52-Week High/Low Dashboard", callback_data="show_strat_52w"))
    markup.row(InlineKeyboardButton("Supertrend Indicator", callback_data="show_strat_st"))
    markup.row(InlineKeyboardButton("Range Bound Strategy", callback_data="show_strat_rb"))
    markup.row(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return markup

def get_strategy_options_markup(strat_id):
    """The 3 core options for every strategy"""
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("1. 📡 Daily Scan", callback_data=f"scan_wl_select_{strat_id}"))
    markup.row(InlineKeyboardButton("2. 🔬 Back Test", url="https://equityradar.streamlit.app/"))
    markup.row(InlineKeyboardButton("3. 🔍 Check for Strategy", callback_data=f"check_single_stock_{strat_id}"))
    markup.row(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return markup

def get_watchlist_selection_markup(strat_id):
    """Watchlist choice for Daily Scan"""
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("V40 Companies", callback_data=f"run_scan_{strat_id}_v40"))
    markup.row(InlineKeyboardButton("V40 Next Companies", callback_data=f"run_scan_{strat_id}_v40n"))
    markup.row(InlineKeyboardButton("V50 Companies", callback_data=f"run_scan_{strat_id}_v50"))
    markup.row(InlineKeyboardButton("V200 Companies", callback_data=f"run_scan_{strat_id}_v200"))
    markup.row(InlineKeyboardButton("High Dividends", callback_data=f"run_scan_{strat_id}_highdiv"))
    markup.row(InlineKeyboardButton("🔙 Back to Strategy", callback_data=f"show_strat_{strat_id}"))
    return markup

def get_bulkdeal_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📊 NSE Bulkdeal (30 Days)", callback_data="run_30_days"))
    markup.row(InlineKeyboardButton("🔍 Client 10-Year History", callback_data="run_10_years"))
    markup.row(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return markup

def get_watchlist_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("V40 Companies", callback_data="list_v40"))
    markup.row(InlineKeyboardButton("V40 Next Companies", callback_data="list_v40n"))
    markup.row(InlineKeyboardButton("V50 Companies", callback_data="list_v50"))
    markup.row(InlineKeyboardButton("V200 Companies", callback_data="list_v200"))
    markup.row(InlineKeyboardButton("High Dividends", callback_data="list_highdiv"))
    markup.row(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return markup


# --- COMMAND HANDLERS ---
@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    chat_id = str(message.chat.id)
    if chat_id not in user_profiles:
        user_profiles[chat_id] = message.from_user.first_name or "Trader"
        save_users(user_profiles)
        
    user_name = user_profiles.get(chat_id, "Trader")
    text = (
        f"Hello {user_name}! 👋\n\n"
        "Welcome to the **StockOpp Premium Terminal**.\n"
        "Please select a category below:"
    )
    bot.send_message(message.chat.id, text, reply_markup=get_main_menu_markup(), parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def cmd_about(message):
    about_text = (
        "🤖 **About StockOpp Premium Terminal**\n\n"
        "Advanced market scanner and automated technical strategy assistant."
    )
    bot.send_message(message.chat.id, about_text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def cmd_help(message):
    help_text = (
        "📖 **Help & Instructions**\n\n"
        "• /start - Open terminal menu.\n"
        "• /menu - Open main menu options.\n"
        "• /owner - Contact support."
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['owner'])
def cmd_owner(message):
    bot.send_message(message.chat.id, "👤 Admin & Support: `@ankitvishnoi01`", parse_mode="Markdown")


# --- CALLBACK QUERY HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    chat_id_str = str(chat_id)
    
    if call.data == "dev_phase":
        bot.answer_callback_query(call.id, "This feature is currently in developing phase.", show_alert=True)
        
    elif call.data == "update_profile":
        msg = bot.send_message(chat_id, "Please type your name:")
        bot.register_next_step_handler(msg, save_user_profile)
        
    # --- Category Menus ---
    elif call.data == "menu_online":
        bot.edit_message_text("🌐 **Online Batch Strategies**\nPlease select a strategy:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_online_menu_markup(), parse_mode="Markdown")
        
    elif call.data == "menu_offline":
        bot.edit_message_text("🔌 **Offline Batch Strategies**\nPlease select a strategy:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_offline_menu_markup(), parse_mode="Markdown")
        
    elif call.data == "menu_youtube":
        bot.edit_message_text("▶️ **YouTube Strategies**\nPlease select a strategy:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_youtube_menu_markup(), parse_mode="Markdown")

    # --- Strategy Detail Page (3 Options) ---
    elif call.data.startswith("show_strat_"):
        strat_id = call.data.split("_")[2]
        strat_title = STRATEGY_MAP.get(strat_id, "Strategy System")
        bot.edit_message_text(
            f"🚥 **Strategy: {strat_title}**\n\nChoose an action:", 
            chat_id=chat_id, 
            message_id=call.message.message_id, 
            reply_markup=get_strategy_options_markup(strat_id), 
            parse_mode="Markdown"
        )

    # --- Daily Scan Option 1: Watchlist Selection ---
    elif call.data.startswith("scan_wl_select_"):
        strat_id = call.data.split("_")[3]
        strat_title = STRATEGY_MAP.get(strat_id, "Strategy")
        bot.edit_message_text(
            f"📡 **Daily Scan: {strat_title}**\n\nSelect a watchlist to run the scan:",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=get_watchlist_selection_markup(strat_id),
            parse_mode="Markdown"
        )

    # --- Daily Scan Execution ---
    elif call.data.startswith("run_scan_"):
        parts = call.data.split("_")
        strat_id = parts[2]
        wl_code = parts[3]
        
        wl_map = {
            "v40": ("V40", watchlists.V40),
            "v40n": ("V40 Next", watchlists.V40N),
            "v50": ("V50", watchlists.V50),
            "v200": ("V200", watchlists.V200),
            "highdiv": ("High Dividends", watchlists.HIGH_DIV)
        }
        
        wl_name, ticker_list = wl_map.get(wl_code, ("Custom", []))
        execute_strategy_daily_scan(chat_id, strat_id, wl_name, ticker_list)

    # --- Option 3: Check Single Stock for Strategy ---
    elif call.data.startswith("check_single_stock_"):
        strat_id = call.data.split("_")[3]
        strat_title = STRATEGY_MAP.get(strat_id, "Strategy")
        
        msg = bot.send_message(chat_id, f"🔍 **Check Strategy: {strat_title}**\n\nPlease enter the NSE Ticker Name:\n(Example: `RELIANCE`, `TCS`, `INFY`)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_check_single_stock, strat_id)

    # --- Other Navigation & Utilities ---
    elif call.data == "show_bulkdeal_menu":
        bot.edit_message_text("📈 **NSE Bulkdeal Tracker**\nPlease select an option:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_bulkdeal_menu_markup(), parse_mode="Markdown")
        
    elif call.data == "show_watchlist_menu":
        bot.edit_message_text("📋 **Market Watchlists**\nPlease select a category to view:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_watchlist_menu_markup(), parse_mode="Markdown")
        
    elif call.data == "back_to_main":
        bot.edit_message_text(f"Hello, {user_profiles.get(chat_id_str, 'Trader')}! 👋\nPlease select a category:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_main_menu_markup(), parse_mode="Markdown")
        
    elif call.data == "run_30_days":
        bot.send_message(chat_id, "Fetching 30-day market deals from NSE...")
        run_nse_30_days(chat_id)
        
    elif call.data == "run_10_years":
        msg = bot.send_message(chat_id, "Please enter the Client Name to search.\n(Suggestion: `VSPARTANS`)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, run_client_10_years)
        
    elif call.data.startswith("list_"):
        list_map = {
            "list_v40": ("V40 Companies", watchlists.V40),
            "list_v40n": ("V40 Next Companies", watchlists.V40N),
            "list_v50": ("V50 Companies", watchlists.V50),
            "list_v200": ("V200 Companies", watchlists.V200),
            "list_highdiv": ("High Dividends Companies", watchlists.HIGH_DIV)
        }
        if call.data in list_map:
            title, tickers = list_map[call.data]
            formatted_list = ", ".join(tickers)
            bot.send_message(chat_id, f"📋 **{title}**\n\n`{formatted_list}`", parse_mode="Markdown")


# --- CORE FUNCTIONALITY LOGIC ---
def save_user_profile(message):
    chat_id_str = str(message.chat.id)
    name = message.text.strip()
    user_profiles[chat_id_str] = name
    save_users(user_profiles)
    bot.send_message(message.chat.id, f"Profile updated! I will call you {name}. Type /start to see the main menu.")

def execute_strategy_daily_scan(chat_id, strat_id, wl_name, ticker_list):
    """Executes the daily scanner for any strategy and selected watchlist"""
    strat_title = STRATEGY_MAP.get(strat_id, "Strategy")
    bot.send_message(chat_id, f"Running **{strat_title}** scan on **{wl_name}** ({len(ticker_list)} stocks)... This may take a moment.", parse_mode="Markdown")
    
    if strat_id == "sma":
        try:
            df_buys, df_sells, df_holdings = run_sma_daily_scanner(tickers=ticker_list)
            
            if df_buys.empty and df_sells.empty and df_holdings.empty: 
                return bot.send_message(chat_id, f"No SMA signals or active setups found today in **{wl_name}**.", parse_mode="Markdown")
                
            if not df_buys.empty: 
                bot.send_message(chat_id, generate_chat_table(df_buys, title=f"🟢 {wl_name} SMA Buys", cols_to_show=['Ticker', 'Close Price']), parse_mode="Markdown")
            if not df_holdings.empty: 
                bot.send_message(chat_id, generate_chat_table(df_holdings, title=f"💼 {wl_name} Active Holdings", cols_to_show=['Ticker', 'Days Held', 'PnL (%)']), parse_mode="Markdown")

            excel_data = {"New Buys": df_buys, "New Sells": df_sells, "Current Active Setups": df_holdings}
            excel_buffer = get_sma_custom_excel_buffer(excel_data)
            excel_buffer.name = f"SMA_{wl_name}_Scan.xlsx"
            bot.send_document(chat_id, document=excel_buffer, caption=f"Detailed SMA Daily Report for {wl_name}.")
        except Exception as e:
            bot.send_message(chat_id, f"Scanner error: {e}")
    else:
        # Placeholder for other strategy scanners
        bot.send_message(chat_id, f"⚙️ The scanning engine for **{strat_title}** is currently being prepared for production.", parse_mode="Markdown")

def process_check_single_stock(message, strat_id):
    """Checks if a buy signal is active for a single stock ticker"""
    chat_id = message.chat.id
    # Clean the input so it works whether the user types "HDFCBANK" or "HDFCBANK.NS"
    raw_ticker = message.text.strip().upper()
    clean_ticker = raw_ticker.replace('.NS', '')
    
    strat_title = STRATEGY_MAP.get(strat_id, "Strategy")
    
    bot.send_message(chat_id, f"Checking **{strat_title}** setup for `{clean_ticker}`...", parse_mode="Markdown")
    
    if strat_id == "sma":
        try:
            # Pass the clean ticker to the scanner
            df_buys, df_sells, df_holdings = run_sma_daily_scanner(tickers=[clean_ticker])
            
            # Check if there are no active setups at all
            if df_buys.empty and df_sells.empty and df_holdings.empty:
                bot.send_message(chat_id, f"⚪ **No Active Setup:**\n`{clean_ticker}` has no active Buy, Sell, or Holding signals for **{strat_title}** today.", parse_mode="Markdown")
            else:
                # If there's a buy signal, show the table
                if not df_buys.empty:
                    bot.send_message(chat_id, f"🟢 **BUY Signal Active for {clean_ticker}!**", parse_mode="Markdown")
                    bot.send_message(chat_id, generate_chat_table(df_buys, title="Buy Details", cols_to_show=['Ticker', 'Close Price']), parse_mode="Markdown")
                
                # If there's a sell signal, show the table
                if not df_sells.empty:
                    bot.send_message(chat_id, f"🔴 **SELL Signal Active for {clean_ticker}!**", parse_mode="Markdown")
                    bot.send_message(chat_id, generate_chat_table(df_sells, title="Sell Details", cols_to_show=['Ticker', 'Close Price']), parse_mode="Markdown")
                
                # If it's already an active holding, show the table with PnL and Days Held
                if not df_holdings.empty:
                    bot.send_message(chat_id, f"💼 **Currently Holding {clean_ticker}!**", parse_mode="Markdown")
                    bot.send_message(chat_id, generate_chat_table(df_holdings, title="Holding Details", cols_to_show=['Ticker', 'Days Held', 'PnL (%)']), parse_mode="Markdown")

        except Exception as e:
            bot.send_message(chat_id, f"Error checking `{clean_ticker}`: {e}", parse_mode="Markdown")
    else:
        # Placeholder for other strategy rule evaluations
        bot.send_message(chat_id, f"⚙️ Signal evaluation logic for **{strat_title}** on `{clean_ticker}` is currently in development.", parse_mode="Markdown")

def run_nse_30_days(chat_id):
    try:
        days = 30
        today = datetime.now()
        from_date, to_date = (today - timedelta(days=days)).strftime("%d-%m-%Y"), today.strftime("%d-%m-%Y")
        try: df_bulk = process_df(capital_market.bulk_deal_data(from_date=from_date, to_date=to_date))
        except: df_bulk = pd.DataFrame()
        try: df_block = process_df(capital_market.block_deals_data(from_date=from_date, to_date=to_date))
        except: df_block = pd.DataFrame()

        if df_bulk.empty and df_block.empty:
            bot.send_message(chat_id, "No data fetched from NSE for the last 30 days.")
            return

        if not df_bulk.empty: bot.send_message(chat_id, generate_chat_table(df_bulk, title="Bulk Deals Preview"), parse_mode="Markdown")
        if not df_block.empty: bot.send_message(chat_id, generate_chat_table(df_block, title="Block Deals Preview"), parse_mode="Markdown")

        excel_buffer = get_excel_buffer(df_bulk, df_block, "NSE", f"Last {days} Days as of {today.strftime('%d-%b-%Y')}")
        excel_buffer.name = f"NSE_Market_Deals_Last_{days}_Days.xlsx"
        bot.send_document(chat_id, document=excel_buffer, caption="Here is your complete 30-Day NSE Deals Excel Report.")
    except Exception as e:
        bot.send_message(chat_id, f"An error occurred: {e}")

def run_client_10_years(message):
    chat_id = message.chat.id
    client_name = message.text.strip()
    if not client_name: 
        return bot.send_message(chat_id, "Invalid name provided.")
        
    status_msg = bot.send_message(chat_id, f"Searching NSE database for '{client_name.upper()}'...")
    try:
        today = datetime.now()
        all_bulk, all_block = [], []
        
        for i in range(10):
            from_str, to_str = (today - timedelta(days=(i + 1) * 365)).strftime("%d-%m-%Y"), (today - timedelta(days=i * 365)).strftime("%d-%m-%Y")
            bot.edit_message_text(f"Searching Year {i+1}/10 ({from_str} to {to_str})...", chat_id=chat_id, message_id=status_msg.message_id)
            try:
                df_b = capital_market.bulk_deal_data(from_date=from_str, to_date=to_str)
                if not df_b.empty:
                    filtered = df_b[df_b['ClientName'].astype(str).str.contains(client_name, case=False, na=False)]
                    if not filtered.empty: all_bulk.append(filtered)
            except: pass
            try:
                df_bl = capital_market.block_deals_data(from_date=from_str, to_date=to_str)
                if not df_bl.empty:
                    filtered = df_bl[df_bl['ClientName'].astype(str).str.contains(client_name, case=False, na=False)]
                    if not filtered.empty: all_block.append(filtered)
            except: pass
            time.sleep(0.3)
            
        df_bulk_merged = process_df(pd.concat(all_bulk, ignore_index=True) if all_bulk else pd.DataFrame())
        df_block_merged = process_df(pd.concat(all_block, ignore_index=True) if all_block else pd.DataFrame())
        
        if df_bulk_merged.empty and df_block_merged.empty: 
            return bot.send_message(chat_id, f"No historical data found for client: '{client_name}'.")
            
        if not df_bulk_merged.empty: 
            bot.send_message(chat_id, generate_chat_table(df_bulk_merged, title=f"Client '{client_name.upper()}' Bulk Deals"), parse_mode="Markdown")
        if not df_block_merged.empty: 
            bot.send_message(chat_id, generate_chat_table(df_block_merged, title=f"Client '{client_name.upper()}' Block Deals"), parse_mode="Markdown")
            
        excel_buffer = get_excel_buffer(df_bulk_merged, df_block_merged, f"Client: {client_name.upper()}", "10 Year History")
        excel_buffer.name = f"Client_History_{client_name.upper()}.xlsx"
        bot.send_document(chat_id, document=excel_buffer, caption=f"Full 10-Year Excel report for {client_name.upper()}.")
    except Exception as e:
        bot.send_message(chat_id, f"An error occurred: {e}")

try:
    from keep_alive import keep_alive
    keep_alive()
except ImportError:
    pass

print("Bot is polling...")
bot.infinity_polling()
