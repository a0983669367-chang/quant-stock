import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import datetime
import concurrent.futures

# 台股前 150 大市值與熱門標的
UNIVERSE = [
    '2330.TW', '2317.TW', '2454.TW', '2308.TW', '2382.TW', '2881.TW', '2882.TW', '2412.TW', '2891.TW', '2886.TW',
    '3231.TW', '2884.TW', '1216.TW', '2002.TW', '2892.TW', '2885.TW', '2303.TW', '2890.TW', '2395.TW', '3711.TW',
    '2880.TW', '2883.TW', '5880.TW', '2887.TW', '2912.TW', '1303.TW', '2357.TW', '2324.TW', '2379.TW', '3045.TW',
    '1301.TW', '2301.TW', '1101.TW', '3034.TW', '2207.TW', '2345.TW', '2356.TW', '4938.TW', '2888.TW', '2603.TW', 
    '2609.TW', '2615.TW', '1590.TW', '5871.TW', '3008.TW', '6669.TW', '3661.TW', '3481.TW', '2409.TW', '1326.TW',
    '2353.TW', '1304.TW', '1402.TW', '2105.TW', '2313.TW', '2352.TW', '2377.TW', '2383.TW', '6415.TW', '1504.TW',
    '3017.TW', '3036.TW', '3324.TW', '3532.TW', '4958.TW', '6269.TW', '6239.TW', '8069.TWO', '8299.TWO', '3105.TWO',
    '6488.TWO', '5483.TWO', '3529.TWO', '5347.TWO', '6147.TWO', '8046.TWO', '6446.TWO', '8436.TW', '9904.TW', '9910.TW',
    '9914.TW', '9921.TW', '9941.TW', '3363.TW', '2354.TW', '6282.TW', '8041.TW', '6138.TW', '6451.TW', '1519.TW',
    '1513.TW', '1514.TW', '1605.TW', '1503.TW', '2360.TW', '2385.TW', '2542.TW', '2618.TW', '2610.TW', '3037.TW'
]

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_swing_lows(df, window=3):
    swing_lows = []
    for i in range(window, len(df) - window):
        current_low = df['Low'].iloc[i]
        if all(current_low < df['Low'].iloc[i-window:i]) and all(current_low <= df['Low'].iloc[i+1:i+window+1]):
            swing_lows.append(i)
    return swing_lows

def get_swing_highs(df, window=5):
    swing_highs = []
    for i in range(window, len(df) - window):
        current_high = df['High'].iloc[i]
        if all(current_high > df['High'].iloc[i-window:i]) and all(current_high >= df['High'].iloc[i+1:i+window+1]):
            swing_highs.append(i)
    return swing_highs

def calculate_smc_and_vegas(ticker):
    try:
        t_obj = yf.Ticker(ticker)
        df = t_obj.history(period='3y', raise_errors=False)
    except:
        return None
        
    if df.empty: return None
        
    # Standardize columns (history() usually returns flat, but let's be robust)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df = df.loc[:, ~df.columns.duplicated()].copy()

    # Ensure necessary columns are Series to avoid downstream issues
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns:
            if isinstance(df[col], pd.DataFrame):
                df[col] = df[col].iloc[:, 0]
    
    if 'Close' not in df.columns: return None
    df.ffill(inplace=True)

    # Technical Indicators
    df['EMA_144'] = df['Close'].ewm(span=144, adjust=False).mean()
    df['EMA_169'] = df['Close'].ewm(span=169, adjust=False).mean()
    df['EMA_576'] = df['Close'].ewm(span=576, adjust=False).mean()
    df['EMA_676'] = df['Close'].ewm(span=676, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()

    df_recent = df.tail(150).copy()
    if len(df_recent) < 20: return None

    latest = df_recent.iloc[-1]
    is_vegas_bullish = latest['EMA_144'] > latest['EMA_576']
    rsi_val = float(latest['RSI'])
    vol_ratio = float(latest['Volume'] / latest['Vol_MA5']) if latest['Vol_MA5'] > 0 else 1.0

    recent_lows = get_swing_lows(df_recent, window=3)
    valid_ob = None
    ob_start_date = None
    valid_fvg = None
    fvg_start_date = None
    
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
        fvg_high, fvg_low, fvg_idx = None, None, None
        for j in range(ob_idx, min(len(df_recent)-2, ob_idx + 5)):
            c1_high = df_recent['High'].iloc[j]
            c3_low = df_recent['Low'].iloc[j+2]
            if c3_low > c1_high:
                fvg_found = True
                fvg_high, fvg_low, fvg_idx = float(c3_low), float(c1_high), j
                break
                
        if fvg_found:
            ob_fvg_min, ob_fvg_max = min(ob_low, fvg_low), max(ob_high, fvg_high)
            ema_min, ema_max = min(latest['EMA_144'], latest['EMA_169']), max(latest['EMA_144'], latest['EMA_169'])
            overlap = max(0, min(ob_fvg_max, ema_max) - max(ob_fvg_min, ema_min))
            if overlap > 0:
                valid_ob = (ob_high, ob_low)
                ob_start_date = df_recent.index[ob_idx].strftime('%Y-%m-%d')
                valid_fvg = (fvg_high, fvg_low)
                fvg_start_date = df_recent.index[fvg_idx].strftime('%Y-%m-%d')
                break

    swing_highs = get_swing_highs(df_recent, window=5)
    targets = [float(df_recent['High'].iloc[sh_idx]) for sh_idx in reversed(swing_highs) if sh_idx == len(df_recent) - 1 or df_recent['High'].iloc[sh_idx+1:].max() <= df_recent['High'].iloc[sh_idx]]
    target1 = targets[0] if targets else None

    # Trigger Logic: "Triggered" (買點成形) vs "Potential" (尚未成形)
    status = "None"
    stop_loss = None
    entry_zone = None
    
    if is_vegas_bullish and valid_ob:
        entry_top = max(valid_ob[0], valid_fvg[0] if valid_fvg else valid_ob[0])
        entry_bottom = min(valid_ob[1], valid_fvg[1] if valid_fvg else valid_ob[1])
        entry_zone = f"{entry_bottom:.2f} - {entry_top:.2f}"
        stop_loss = entry_bottom * 0.98

        if float(latest['Low']) <= entry_top and float(latest['Close']) >= entry_bottom:
            status = "Triggered"
        elif float(latest['Close']) > entry_top:
            status = "Potential"

    if status == "None": return None

    # Fetch Fundamentals for candidates
    pe_ratio, div_yield, name, industry, market_cap = 0, 0, ticker, "N/A", 0
    try:
        info = t_obj.info
        pe_ratio = info.get('trailingPE', 0)
        div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
        name = info.get('longName', ticker)
        industry = info.get('industry', 'N/A')
        market_cap = info.get('marketCap', 0)
    except: pass

    return {
        "ticker": ticker,
        "name": name,
        "industry": industry,
        "market_cap": float(market_cap),
        "status": str(status),
        "is_vegas_bullish": bool(is_vegas_bullish),
        "rsi": float(rsi_val),
        "vol_ratio": float(vol_ratio),
        "pe_ratio": float(pe_ratio),
        "div_yield": float(div_yield),
        "ob": [float(x) for x in valid_ob] if valid_ob else None,
        "fvg": [float(x) for x in valid_fvg] if valid_fvg else None,
        "target1": float(target1) if target1 else None,
        "stop_loss": float(stop_loss) if stop_loss else None,
        "entry_zone": entry_zone,
        "latest_close": float(latest['Close']),
        "upside_pct": float((target1 - latest['Close']) / latest['Close']) if target1 and target1 > latest['Close'] else 0.0
    }

def run_analysis():
    print(f"[{datetime.datetime.now()}] Scanning {len(UNIVERSE)} Taiwan stocks...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(calculate_smc_and_vegas, t): t for t in UNIVERSE}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Sort triggered first, then potential, then by upside
    sorted_res = sorted(results, key=lambda x: (x['status'] == 'Triggered', x['upside_pct']), reverse=True)
    top_picks = sorted_res[:15]

    os.makedirs('data', exist_ok=True)
    # Save current findings
    with open('data/signals.json', 'w', encoding='utf-8') as f:
        json.dump(top_picks, f, indent=4, ensure_ascii=False)
    
    # Update History
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    history = {}
    if os.path.exists('data/history.json'):
        try:
            with open('data/history.json', 'r', encoding='utf-8') as f:
                history = json.load(f)
        except: history = {}
    
    history[today] = top_picks
    # Keep last 30 days
    if len(history) > 30:
        oldest_dates = sorted(history.keys())[:-30]
        for d in oldest_dates: history.pop(d)
        
    with open('data/history.json', 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    print(f"[{datetime.datetime.now()}] Saved {len(top_picks)} picks to signals.json and history.json")
    return top_picks

if __name__ == "__main__":
    run_analysis()
