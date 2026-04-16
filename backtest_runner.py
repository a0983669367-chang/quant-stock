import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import datetime
from concurrent.futures import ThreadPoolExecutor

# Reuse UNIVERSE and Maps from data_fetcher
from data_fetcher import UNIVERSE, NAME_MAP, INDUSTRY_MAP, calculate_rsi, get_swing_lows, get_swing_highs

def analyze_slice(df_slice, ticker):
    """
    Exactly the same logic as calculate_smc_and_vegas but uses the provided df_slice
    representing 'today' being the last row of df_slice.
    """
    if len(df_slice) < 576: return None
    
    # Technical Indicators (assuming they were calculated on the full DF for speed, 
    # but for accuracy we should check the last row of the slice)
    latest = df_slice.iloc[-1]
    
    # Check Vegas
    is_vegas_bullish = latest['EMA_144'] > latest['EMA_576']
    if not is_vegas_bullish: return None
    
    # Check SMC Structures in recent window
    df_recent = df_slice.tail(100).copy()
    recent_lows = get_swing_lows(df_recent, window=3)
    
    valid_ob = None
    valid_fvg = None
    
    for sl_idx in reversed(recent_lows):
        if len(df_recent) - sl_idx > 25: continue
            
        ob_idx = None
        for i in range(sl_idx, max(-1, sl_idx-10), -1):
            if df_recent['Close'].iloc[i] < df_recent['Open'].iloc[i]:
                ob_idx = i
                break
        
        if ob_idx is None: continue
        ob_high, ob_low = float(df_recent['High'].iloc[ob_idx]), float(df_recent['Low'].iloc[ob_idx])
        
        fvg_found = False
        fvg_high, fvg_low = None, None
        for j in range(ob_idx, min(len(df_recent)-2, ob_idx + 5)):
            c1_high = df_recent['High'].iloc[j]
            c3_low = df_recent['Low'].iloc[j+2]
            if c3_low > c1_high:
                fvg_found = True
                fvg_high, fvg_low = float(c3_low), float(c1_high)
                break
                
        if fvg_found:
            ob_fvg_min, ob_fvg_max = min(ob_low, fvg_low), max(ob_high, fvg_high)
            ema_min, ema_max = min(latest['EMA_144'], latest['EMA_169']), max(latest['EMA_144'], latest['EMA_169'])
            overlap = max(0, min(ob_fvg_max, ema_max) - max(ob_fvg_min, ema_min))
            if overlap > 0:
                valid_ob = (ob_high, ob_low)
                valid_fvg = (fvg_high, fvg_low)
                break

    if not valid_ob: return None

    # Calculate Target
    swing_highs = get_swing_highs(df_recent, window=5)
    targets = [float(df_recent['High'].iloc[sh_idx]) for sh_idx in reversed(swing_highs) if sh_idx == len(df_recent) - 1 or df_recent['High'].iloc[sh_idx+1:].max() <= df_recent['High'].iloc[sh_idx]]
    target1 = targets[0] if targets else None
    
    if not target1: return None

    entry_top = max(valid_ob[0], valid_fvg[0] if valid_fvg else valid_ob[0])
    entry_bottom = min(valid_ob[1], valid_fvg[1] if valid_fvg else valid_ob[1])
    stop_loss = entry_bottom * 0.98

    # Triggered Condition
    if float(latest['Low']) <= entry_top and float(latest['Close']) >= entry_bottom:
        return {
            "ticker": ticker,
            "date": df_slice.index[-1].strftime('%Y-%m-%d'),
            "entry_price": float(latest['Close']),
            "target": target1,
            "stop_loss": stop_loss
        }
    return None

def run_backtest_for_stock(ticker):
    print(f"Backtesting {ticker}...")
    try:
        # Fetch data back to 2023 to ensure EMA 576/676 is stable for 2026
        df = yf.download(ticker, start="2023-01-01", end="2026-04-16", progress=False)
        if df.empty: return []
        
        # 處理 yfinance 可能返回的 MultiIndex 或重複欄位
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()].copy()
        
        # 確保必要的欄位是 Series 而非 DataFrame
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                if isinstance(df[col], pd.DataFrame):
                    df[col] = df[col].iloc[:, 0]
        
        if 'Close' not in df.columns: return []
        df.ffill(inplace=True)
        df.dropna(subset=['Close'], inplace=True)
        if len(df) < 576: 
            print(f"Skipping {ticker}: Not enough data ({len(df)} days)")
            return []

    except Exception as e:
        print(f"Error downloading {ticker}: {e}")
        return []

    # Indicators
    df['EMA_144'] = df['Close'].ewm(span=144, adjust=False).mean()
    df['EMA_169'] = df['Close'].ewm(span=169, adjust=False).mean()
    df['EMA_576'] = df['Close'].ewm(span=576, adjust=False).mean()
    df['EMA_676'] = df['Close'].ewm(span=676, adjust=False).mean()

    results = []
    # Start loop from 2026-01-01
    start_date = pd.Timestamp("2026-01-01")
    trade_active = False
    active_trade_data = None

    indices_2026 = df.index[df.index >= start_date]
    
    for i in range(len(df)):
        current_date = df.index[i]
        if current_date < start_date: continue
        
        # 1. Check if we have an active trade to follow
        if trade_active:
            high, low = df['High'].iloc[i], df['Low'].iloc[i]
            if high >= active_trade_data['target']:
                active_trade_data['result'] = "🎯 止盈"
                results.append(active_trade_data)
                trade_active = False
            elif low <= active_trade_data['stop_loss']:
                active_trade_data['result'] = "🛡️ 止損"
                results.append(active_trade_data)
                trade_active = False
            # Check if trade is too old or market changed? (Optional)
            continue

        # 2. If no active trade, scan for new trigger
        # (Only scan once per few days or if a new structure forms? 
        # Standard backtest: check every day)
        res = analyze_slice(df.iloc[:i+1], ticker)
        if res:
            res['name'] = NAME_MAP.get(ticker, ticker)
            res['result'] = "⏳ 進行中"
            trade_active = True
            active_trade_data = res

    if trade_active:
        results.append(active_trade_data)
        
    return results

def main():
    all_records = []
    # Use 10 threads to speed up yfinance calls
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_backtest_for_stock, t): t for t in UNIVERSE}
        for future in futures:
            stock_results = future.result()
            all_records.extend(stock_results)

    # Sort by date
    all_records.sort(key=lambda x: x['date'], reverse=True)
    
    os.makedirs('data', exist_ok=True)
    with open('data/triggered_records.json', 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=4)
    
    print(f"Backtest complete. Generated {len(all_records)} records.")

if __name__ == "__main__":
    main()
