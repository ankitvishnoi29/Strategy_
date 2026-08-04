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

BOT_TOKEN = "8858205576:AAF3QFD6rQkmyxAn9OGenaeKxqeJ-rKrZQ4" 
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
user_backtest_data = {} # Temporary storage for ticker and strategy data during backtest setup

# --- MENU MARKUPS ---
def get_main_menu_markup():
    markup = InlineKeyboardMarkup()
    
    markup.row(InlineKeyboardButton("Update Profile", callback_data="update_profile"))
    markup.row(InlineKeyboardButton("Strategy: SMA Dashboard", callback_data="show_strat_sma"))
    markup.row(InlineKeyboardButton("Strategy: 52-Week High/Low Dashboard", callback_data="show_strat_52w"))
    markup.row(InlineKeyboardButton("Strategy: AV20 Dashboard", callback_data="show_strat_av20"))
    markup.row(InlineKeyboardButton("Strategy: High Dividend Dashboard", callback_data="show_strat_highdiv"))
    markup.row(InlineKeyboardButton("Stochastic Momentum Dashboard", callback_data="show_strat_stoch"))
    markup.row(InlineKeyboardButton("Strategy: Pivot Points Dashboard", callback_data="show_strat_pivot"))
    markup.row(InlineKeyboardButton("Any Stock Testing", callback_data="dev_phase"))
    markup.row(InlineKeyboardButton("NSE Deals Tracker", callback_data="show_bulkdeal_menu"))
    markup.row(InlineKeyboardButton("Company Watchlists", callback_data="show_watchlist_menu"))
    
    return markup

def get_strategy_menu_markup(strat_id):
    markup = InlineKeyboardMarkup()
    
    if strat_id == "sma":
        markup.row(InlineKeyboardButton("📡 Daily Scanner", callback_data="run_sma_scanner"))
    else:
        markup.row(InlineKeyboardButton("📡 Daily Scanner", callback_data="dev_phase"))
        
    markup.row(InlineKeyboardButton("🔬 Single Stock Backtest", callback_data=f"prompt_backtest_{strat_id}"))
    markup.row(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
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
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = str(message.chat.id)
    
    # Auto-capture new users
    if chat_id not in user_profiles:
        user_profiles[chat_id] = message.from_user.first_name or "Trader"
        save_users(user_profiles)
        
    user_name = user_profiles.get(chat_id, "Trader")
    welcome_text = (
        f"Hello {user_name}! 👋\n\n"
        "Welcome to the **StockOpp Premium Terminal**.\n"
        "Link your account to receive exclusive daily alerts, V40 breakouts, and custom strategy scans directly on Telegram.\n\n"
        "Click **MENU** below or use the buttons to navigate."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu_markup(), parse_mode="Markdown")

@bot.message_handler(commands=['menu'])
def cmd_menu(message):
    chat_id = str(message.chat.id)
    user_name = user_profiles.get(chat_id, "Trader")
    bot.send_message(message.chat.id, f"Hello, {user_name}! 👋\nPlease select an option:", reply_markup=get_main_menu_markup(), parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def cmd_about(message):
    about_text = (
        "🤖 **About StockOpp Premium Terminal**\n\n"
        "The StockOpp Premium Terminal is an advanced market intelligence assistant designed to deliver fast, "
        "accurate, and personalized trading insights directly to your Telegram account.\n\n"
        "* **Exclusive Daily Alerts**: Receive automated daily buy and sell alerts for your portfolio delivered precisely at 7:00 PM IST.\n"
        "* **Diverse Strategy Scans**: Track specialized technical setups and breakouts across popular categories like V40, V40 Next, and V200.\n"
        "* **Advanced Indicator Support**: Monitor custom strategy alerts utilizing V20, Simple Moving Average (SMA), and Envelope strategies.\n"
        "* **Custom Stock Tracking**: Personalize your terminal experience by configuring custom alerts for your own preferred watchlist of stocks."
    )
    bot.send_message(message.chat.id, about_text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def cmd_help(message):
    help_text = (
        "📖 **Help & Instructions**\n\n"
        "Here is how you can use the bot:\n"
        "• /start - Open the main interactive terminal menu.\n"
        "• /menu - Open main menu options.\n"
        "• /about - Learn more about the bot's features.\n"
        "• /settings - Customize your bot preferences.\n"
        "• /owner - Get contact information for support.\n"
        "• /users - Get full table of registered users & chat IDs (Admin only).\n"
        "• /vspartans - Instantly fetch 10-year trade history for VSPARTANS (Admin only)."
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['settings'])
def cmd_settings(message):
    settings_text = (
        "⚙️ **Bot Settings**\n\n"
        "Manage your terminal configurations:\n"
        "• **Alert Timing**: 7:00 PM IST (Default)\n"
        "• **Active Strategy**: SMA & V40 Breakouts\n"
        "• **Notifications**: Enabled"
    )
    bot.send_message(message.chat.id, settings_text, parse_mode="Markdown")

@bot.message_handler(commands=['owner'])
def cmd_owner(message):
    owner_text = (
        "👤 **Owner & Support**\n\n"
        "This bot is managed and operated by the StockOpp Team / Ankit.\n"
        "For business inquiries or technical support, please contact the owner directly:\n\n"
        "💬 Admin: `@Ankit209ee`"
    )
    bot.send_message(message.chat.id, owner_text, parse_mode="Markdown")

@bot.message_handler(commands=['users'])
def cmd_users(message):
    if message.from_user.username == "Ankit209ee":
        if not user_profiles:
            bot.send_message(message.chat.id, "👥 **No registered users found.**")
            return
            
        df_users = pd.DataFrame(list(user_profiles.items()), columns=['Chat ID', 'Name'])
        table_text = f"👥 **Registered Users ({len(df_users)} total):**\n```\n{df_users.to_string(index=False)}\n```"
        bot.send_message(message.chat.id, table_text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "⛔ Unauthorized access.")

@bot.message_handler(commands=['vspartans'])
def cmd_vspartans(message):
    """Direct command to fetch 10-year history for VSPARTANS instantly without menus"""
    if message.from_user.username == "Ankit209ee":
        dummy_msg = message
        dummy_msg.text = "VSPARTANS"
        run_client_10_years(dummy_msg)
    else:
        bot.send_message(message.chat.id, "⛔ Unauthorized access. This command is restricted.")


# --- CALLBACK QUERY HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    chat_id_str = str(chat_id)
    
    if call.data == "dev_phase":
        bot.send_message(chat_id, "This feature is in developing phase.")
        
    elif call.data == "update_profile":
        msg = bot.send_message(chat_id, "Please type your name:")
        bot.register_next_step_handler(msg, save_user_profile)
        
    elif call.data.startswith("show_strat_"):
        strat_id = call.data.split("_")[2]
        titles = {
            "sma": "SMA Reversal Strategy System",
            "52w": "52-Week High/Low Strategy System",
            "av20": "AV20 Strategy System",
            "highdiv": "High Dividend Strategy System",
            "stoch": "Stochastic Momentum Strategy System",
            "pivot": "Pivot Points Strategy System"
        }
        title = titles.get(strat_id, "Strategy System")
        bot.edit_message_text(f"🚥 **{title}**\nPlease select an option:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_strategy_menu_markup(strat_id), parse_mode="Markdown")

    elif call.data == "show_bulkdeal_menu":
        bot.edit_message_text("📈 **NSE Bulkdeal Tracker**\nPlease select an option:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_bulkdeal_menu_markup(), parse_mode="Markdown")
        
    elif call.data == "show_watchlist_menu":
        bot.edit_message_text("📋 **Market Watchlists**\nPlease select a category to view:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_watchlist_menu_markup(), parse_mode="Markdown")
        
    elif call.data == "back_to_main":
        bot.edit_message_text(f"Hello, {user_profiles.get(chat_id_str, 'Trader')}! 👋\nPlease select an option:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_main_menu_markup(), parse_mode="Markdown")
        
    elif call.data == "run_30_days":
        bot.send_message(chat_id, "Fetching 30-day market deals from NSE...")
        run_nse_30_days(chat_id)
        
    elif call.data == "run_10_years":
        msg = bot.send_message(chat_id, "Please enter the Client Name to search.\n(Suggestion: `VSPARTANS`)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, run_client_10_years)
        
    elif call.data == "run_sma_scanner":
        bot.send_message(chat_id, "Running SMA Daily Scanner across V40 & V40 Next watchlists...")
        execute_sma_scanner(chat_id)
        
    elif call.data.startswith("prompt_backtest_"):
        strat_id = call.data.split("_")[2]
        titles = {
            "sma": "SMA",
            "52w": "52-Week High/Low",
            "av20": "AV20",
            "highdiv": "High Dividend",
            "stoch": "Stochastic Momentum",
            "pivot": "Pivot Points"
        }
        strat_name = titles.get(strat_id, "Strategy")
        msg = bot.send_message(chat_id, f"Please enter the Ticker Name for {strat_name} Backtest.\n(Example: `ACC`)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ask_years_for_backtest, strat_id)
        
    elif call.data.startswith("bt_years_"):
        years = int(call.data.split("_")[2])
        execute_backtest_final(call.message, years)
        
    elif call.data.startswith("list_"):
        list_map = {
            "list_v40": ("V40 Companies", watchlists.V40),
            "list_v40n": ("V40 Next Companies", watchlists.V40N),
            "list_v50": ("V50 Companies", watchlists.V50),
            "list_v200": ("V200 Companies", watchlists.V200),
            "list_highdiv": ("High Dividends Companies", watchlists.HIGH_DIV)
        }
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
    if not client_name: return bot.send_message(chat_id, "Invalid name provided.")
        
    status_msg = bot.send_message(chat_id, f"Searching NSE database (2016-2026) for '{client_name.upper()}'...")
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
        
        if df_bulk_merged.empty and df_block_merged.empty: return bot.send_message(chat_id, f"No historical data found for client: '{client_name}'.")
        if not df_bulk_merged.empty: bot.send_message(chat_id, generate_chat_table(df_bulk_merged, title=f"Client '{client_name.upper()}' Bulk Deals"), parse_mode="Markdown")
        if not df_block_merged.empty: bot.send_message(chat_id, generate_chat_table(df_block_merged, title=f"Client '{client_name.upper()}' Block Deals"), parse_mode="Markdown")
            
        excel_buffer = get_excel_buffer(df_bulk_merged, df_block_merged, f"Client: {client_name.upper()}", "10 Year History")
        excel_buffer.name = f"Client_History_{client_name.upper()}.xlsx"
        bot.send_document(chat_id, document=excel_buffer, caption=f"Full 10-Year Excel report for {client_name.upper()}.")
    except Exception as e:
        bot.send_message(chat_id, f"An error occurred: {e}")

def execute_sma_scanner(chat_id):
    try:
        bot.send_message(chat_id, "Processing V40 & V40 Next watchlists... This may take a minute.")
        
        scan_list = watchlists.V40 + watchlists.V40N
        df_buys, df_sells, df_holdings = run_sma_daily_scanner(tickers=scan_list)
        
        if df_buys.empty and df_sells.empty and df_holdings.empty: return bot.send_message(chat_id, "No SMA signals or active holdings found today.")
        if not df_buys.empty: bot.send_message(chat_id, generate_chat_table(df_buys, title="🟢 SMA Buy Signals", cols_to_show=['Ticker', 'Close Price']), parse_mode="Markdown")
        if not df_holdings.empty: bot.send_message(chat_id, generate_chat_table(df_holdings, title="💼 Active Holdings", cols_to_show=['Ticker', 'Days Held', 'PnL (%)']), parse_mode="Markdown")

        excel_data = {"New Buys": df_buys, "New Sells": df_sells, "Current Active Setups": df_holdings}
        excel_buffer = get_sma_custom_excel_buffer(excel_data)
        excel_buffer.name = "SMA_Daily_Scanner_Results.xlsx"
        bot.send_document(chat_id, document=excel_buffer, caption="Here is your detailed SMA Scanner Report (V40 & V40 Next).")
    except Exception as e:
        bot.send_message(chat_id, f"Scanner error: {e}")

def ask_years_for_backtest(message, strat_id="sma"):
    chat_id = message.chat.id
    ticker = message.text.strip().upper()
    user_backtest_data[chat_id] = {'ticker': ticker, 'strat_id': strat_id}
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("5 Years", callback_data="bt_years_5"), InlineKeyboardButton("10 Years", callback_data="bt_years_10"), InlineKeyboardButton("15 Years", callback_data="bt_years_15"))
    markup.row(InlineKeyboardButton("20 Years", callback_data="bt_years_20"), InlineKeyboardButton("50 Years", callback_data="bt_years_50"))
    
    bot.send_message(chat_id, f"Ticker `{ticker}` saved. How many years of history do you want to backtest?", reply_markup=markup, parse_mode="Markdown")

def execute_backtest_final(message, years):
    chat_id = message.chat.id
    data = user_backtest_data.get(chat_id)
    
    if not data or not isinstance(data, dict) or not data.get('ticker'):
        bot.send_message(chat_id, "Session expired. Please start the backtest again.")
        return
        
    ticker = data['ticker']
    strat_id = data.get('strat_id', 'sma')
    
    if strat_id != "sma":
        bot.send_message(chat_id, f"The execution engine for this strategy's backtest is currently in developing phase.")
        return
        
    status_msg = bot.send_message(chat_id, f"Downloading data & executing SMA backtest for `{ticker}` ({years} Years)...", parse_mode="Markdown")
    try:
        df_trades = run_sma_single_stock_backtest(ticker, period_years=years)
        if df_trades.empty: return bot.edit_message_text(f"No completed trades found for `{ticker}` in {years} years.", chat_id=chat_id, message_id=status_msg.message_id)

        bot.send_message(chat_id, generate_chat_table(df_trades, title=f"Backtest: {ticker} ({years}Y)", cols_to_show=['Ticker', 'Entry Date', 'PnL (%)']), parse_mode="Markdown")
        excel_buffer = get_sma_custom_excel_buffer({f"{ticker} Trades": df_trades})
        excel_buffer.name = f"SMA_Backtest_{ticker}_{years}Y.xlsx"
        bot.send_document(chat_id, document=excel_buffer, caption=f"Here is all executed trade history for {ticker} ({years} Years).")
    except Exception as e:
        bot.send_message(chat_id, f"Backtest error: {e}")
        
from keep_alive import keep_alive
keep_alive()

print("Bot is polling...")
bot.infinity_polling()
