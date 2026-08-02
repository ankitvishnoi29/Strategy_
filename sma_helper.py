import pandas as pd
import yfinance as yf
from datetime import datetime
import watchlists

def get_category_tags(ticker):
    tags = []
    clean = ticker.replace('.NS', '')
    if clean in watchlists.V40: tags.append("V40")
    if clean in watchlists.V40N: tags.append("V40Next")
    if clean in watchlists.V200: tags.append("V200")
    if clean in watchlists.V50: tags.append("V50")
    if clean in watchlists.HIGH_DIV: tags.append("HighDiv")
    if clean in watchlists.MINE: tags.append("Mine")
    return ", ".join(tags) if tags else "-"

def get_screener_url(ticker):
    return f"https://www.screener.in/company/{ticker.replace('.NS', '')}/consolidated/"

def get_tv_url(ticker):
    return f"https://in.tradingview.com/chart/?symbol=NSE:{ticker.replace('.NS', '')}"

def fetch_stock_sma_data(ticker, period_years=3):
    symbol = f"{ticker.upper().strip()}.NS" if not ticker.endswith(".NS") else ticker.upper().strip()
    try:
        df = yf.download(symbol, period=f"{period_years}y", progress=False)
        if df.empty or len(df) < 200:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        df['Next_Open'] = df['Open'].shift(-1)
        df['Next_Date'] = df.index.to_series().shift(-1)
        return df.dropna(subset=['SMA_200'])
    except Exception:
        return None

def run_sma_daily_scanner(tickers=watchlists.GLOBAL_WATCHLIST):
    buys, sells, holdings = [], [], []
    
    for ticker in tickers:
        df = fetch_stock_sma_data(ticker, period_years=2)
        if df is None or df.empty:
            continue
            
        in_position = False
        entry_price = 0.0
        entry_date = None
        
        for row in df.itertuples():
            close = float(row.Close)
            s20, s50, s200 = float(row.SMA_20), float(row.SMA_50), float(row.SMA_200)
            next_open, next_date = row.Next_Open, row.Next_Date
            if pd.isna(next_open): break

            buy_cond = (s200 > s50) and (s50 > s20) and (s20 > close)
            sell_cond = (s200 < s50) and (s50 < s20) and (s20 < close)

            if not in_position and buy_cond:
                in_position = True
                entry_price = float(next_open)
                entry_date = pd.to_datetime(next_date)
            elif in_position and sell_cond and (close > entry_price):
                in_position = False

        last_row = df.iloc[-1]
        close = float(last_row['Close'])
        s20, s50, s200 = float(last_row['SMA_20']), float(last_row['SMA_50']), float(last_row['SMA_200'])
        
        if (s200 > s50) and (s50 > s20) and (s20 > close):
            buys.append({"Ticker": f"{ticker}.NS", "Signal": "BUY TOMORROW OPEN", "Close Price": close})
        elif in_position and (s200 < s50) and (s50 < s20) and (s20 < close) and (close > entry_price):
            sells.append({"Ticker": f"{ticker}.NS", "Signal": "SELL TOMORROW OPEN", "Close Price": close})

        if in_position:
            days_held = (df.index[-1] - entry_date).days
            pnl_pct = ((close - entry_price) / entry_price) * 100
            holdings.append({
                "Ticker": f"{ticker}.NS", "Category": get_category_tags(ticker),
                "Screener": get_screener_url(ticker), "TradingView": get_tv_url(ticker),
                "Entry Date": entry_date.strftime('%d/%m/%Y'), "Days Held": days_held,
                "Entry Price": entry_price, "Current Price": close, "PnL (%)": pnl_pct
            })
            
    return pd.DataFrame(buys), pd.DataFrame(sells), pd.DataFrame(holdings)

def run_sma_single_stock_backtest(ticker, period_years=5):
    df = fetch_stock_sma_data(ticker, period_years=period_years)
    if df is None or df.empty: return pd.DataFrame()
        
    in_position = False
    entry_price = 0.0
    entry_date = None
    historical_trades = []

    for row in df.itertuples():
        close, s20, s50, s200 = float(row.Close), float(row.SMA_20), float(row.SMA_50), float(row.SMA_200)
        next_open, next_date = row.Next_Open, row.Next_Date
        if pd.isna(next_open): continue

        buy_cond = (s200 > s50) and (s50 > s20) and (s20 > close)
        sell_cond = (s200 < s50) and (s50 < s20) and (s20 < close)

        if not in_position and buy_cond:
            in_position = True
            entry_price = float(next_open)
            entry_date = pd.to_datetime(next_date)
        elif in_position and sell_cond and (close > entry_price):
            exit_price = float(next_open)
            exit_date = pd.to_datetime(next_date)
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            
            historical_trades.append({
                "Ticker": f"{ticker.upper()}.NS", "Category": get_category_tags(ticker),
                "Screener": get_screener_url(ticker), "TradingView": get_tv_url(ticker),
                "Entry Date": entry_date.strftime('%d/%m/%Y'), "Exit Date": exit_date.strftime('%d/%m/%Y'),
                "Days Held": (exit_date - entry_date).days, "Entry Price": entry_price,
                "Exit Price": exit_price, "PnL (%)": pnl_pct
            })
            in_position = False

    return pd.DataFrame(historical_trades)