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

NAME_MAP = {
    '2330.TW': '台積電', '2317.TW': '鴻海', '2454.TW': '聯發科', '2308.TW': '台達電', '2382.TW': '廣達',
    '2881.TW': '富邦金', '2882.TW': '國泰金', '2412.TW': '中華電', '2891.TW': '中信金', '2886.TW': '兆豐金',
    '3231.TW': '緯創', '2884.TW': '玉山金', '1216.TW': '統一', '2002.TW': '中鋼', '2892.TW': '第一金',
    '2885.TW': '元大金', '2303.TW': '聯電', '2890.TW': '永豐金', '2395.TW': '研華', '3711.TW': '日月光投控',
    '2880.TW': '華南金', '2883.TW': '凱基金', '5880.TW': '合庫金', '2887.TW': '台新金', '2912.TW': '統一超',
    '1303.TW': '南亞', '2357.TW': '華碩', '2324.TW': '仁寶', '2379.TW': '瑞昱', '3045.TW': '台灣大',
    '1301.TW': '台塑', '2301.TW': '光寶科', '1101.TW': '台泥', '3034.TW': '聯詠', '2207.TW': '和泰車',
    '2345.TW': '智邦', '2356.TW': '英業達', '4938.TW': '和碩', '2888.TW': '新光金', '2603.TW': '長榮',
    '2609.TW': '陽明', '2615.TW': '萬海', '1590.TW': '亞德客-KY', '5871.TW': '中租-KY', '3008.TW': '大立光',
    '6669.TW': '緯穎', '3661.TW': '世芯-KY', '3481.TW': '群創', '2409.TW': '友達', '1326.TW': '台化',
    '2353.TW': '宏碁', '1304.TW': '台聚', '1402.TW': '遠東新', '2105.TW': '正新', '2313.TW': '華通',
    '2352.TW': '佳世達', '2377.TW': '微星', '2383.TW': '台光電', '6415.TW': '矽力*-KY', '1504.TW': '東元',
    '3017.TW': '奇鋐', '3036.TW': '文曄', '3324.TW': '雙鴻', '3532.TW': '台勝科', '4958.TW': '臻鼎-KY',
    '6269.TW': '台郡', '6239.TW': '力成', '8069.TWO': '元太', '8299.TWO': '群聯', '3105.TWO': '穩懋',
    '6488.TWO': '環球晶', '5483.TWO': '中美晶', '3529.TWO': '力旺', '5347.TWO': '世界', '6147.TWO': '頎邦',
    '8046.TWO': '南電', '6446.TWO': '藥華藥', '8436.TW': '大江', '9904.TW': '寶成', '9910.TW': '豐泰',
    '9914.TW': '美利達', '9921.TW': '巨大', '9941.TW': '裕融', '3363.TW': '上詮', '2354.TW': '鴻準',
    '6282.TW': '康舒', '8041.TW': '永道', '6138.TW': '茂達', '6451.TW': '訊芯-KY', '1519.TW': '華城',
    '1513.TW': '中興電', '1514.TW': '亞力', '1605.TW': '華新', '1503.TW': '士電', '2360.TW': '致茂',
    '2385.TW': '群光', '2542.TW': '興富發', '2618.TW': '長榮航', '2610.TW': '華航', '3037.TW': '欣興'
}

INDUSTRY_MAP = {
    'Semiconductors': '半導體',
    'Electrical Equipment & Parts': '電力重電',
    'Electronic Components': '電子零組件',
    'Computers - IT Services': '電腦資訊工程',
    'Consumer Electronics': '消費性電子',
    'Auto Manufacturers': '汽車工業',
    'Steel': '鋼鐵工業',
    'Banks': '金融銀行',
    'Insurance - Life': '人壽保險',
    'Insurance - Property & Casualty': '產物保險',
    'Shipping': '航運業',
    'Chemicals': '化學工業',
    'Building Materials': '建材營造',
    'Oil & Gas Integrated': '油氣工業',
    'Telecommunications Services': '電信服務',
    'Food Confectioners': '食品加工',
    'Textile Manufacturing': '紡織纖維',
    'Footwear & Accessories': '鞋業配件',
    'Industrial Conglomerates': '綜合工業',
    'Semiconductor Equipment & Materials': '半導體設備',
    'Computer Hardware': '電腦硬體',
    'Electronic Gaming & Multimedia': '電子遊戲多媒體',
    'Biotechnology': '生物科技',
    'Packaging & Containers': '包裝容器',
    'Real Estate - General': '房地產',
    'Airlines': '航空業'
}

def calculate_rsi(df_or_series, window=14):
    """支持傳入 DataFrame 或 Series"""
    if isinstance(df_or_series, pd.DataFrame):
        series = df_or_series['Close']
    else:
        series = df_or_series
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(df):
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

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
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()

    df_recent = df.tail(150).copy()
    if len(df_recent) < 20: return None

    latest = df_recent.iloc[-1]
    is_vegas_bullish = latest['EMA_144'] > latest['EMA_576']
    
    # Trend Quality: Slope of EMA 144 over 5 days
    prev_5 = df_recent.iloc[-6]['EMA_144'] if len(df_recent) >= 6 else latest['EMA_144']
    ema_slope = (latest['EMA_144'] - prev_5) / prev_5 * 100

    rsi_val = float(latest['RSI'])
    vol_ratio = float(latest['Volume'] / latest['Vol_MA5']) if latest['Vol_MA5'] > 0 else 1.0
    rel_vol_20 = float(latest['Volume'] / latest['Vol_MA20']) if latest['Vol_MA20'] > 0 else 1.0

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

    # Technical Indicators
    rsi = calculate_rsi(df_recent)
    macd, macd_signal = calculate_macd(df_recent)
    
    current_rsi = rsi.iloc[-1]
    last_macd = macd.iloc[-1]
    last_signal = macd_signal.iloc[-1]
    prev_macd = macd.iloc[-2] if len(macd) > 1 else last_macd
    prev_signal = macd_signal.iloc[-2] if len(macd_signal) > 1 else last_signal

    # MACD Golden Cross within last 7 days (Relaxed from 3)
    macd_cross = False
    for i in range(-1, -8, -1):
        if i < -len(macd): break
        if macd.iloc[i] > macd_signal.iloc[i] and (i-1 >= -len(macd)) and macd.iloc[i-1] <= macd_signal.iloc[i-1]:
            macd_cross = True
            break
            
    swing_highs = get_swing_highs(df_recent, window=5)
    targets = [float(df_recent['High'].iloc[sh_idx]) for sh_idx in reversed(swing_highs) if sh_idx == len(df_recent) - 1 or df_recent['High'].iloc[sh_idx+1:].max() <= df_recent['High'].iloc[sh_idx]]
    target1 = targets[0] if targets else None

    # Trigger Logic
    status = "None"
    stop_loss = None
    entry_zone = None
    rr_ratio = 0
    
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

    # Calculate RR Ratio based on current price
    if target1 and stop_loss:
        price = float(latest['Close'])
        risk = price - stop_loss
        reward = target1 - price
        if risk > 0: rr_ratio = reward / risk

    # Conservative Filters
    is_conservative = False
    if status != "None":
        # Rule 1: RSI < 55 (Relaxed from 45)
        # Rule 2: MACD Golden Cross (Momentum confirmed)
        # Rule 3: Volume Spike (Vol > 1.1 * Vol MA20) - Proxy for Institutional Buying (Relaxed from 1.2)
        # Rule 4: EMA 144 Slope > 0 (Overall Bullish)
        
        vol_spike = latest['Volume'] > (latest['Vol_MA20'] * 1.1) if 'Vol_MA20' in latest else False
        if current_rsi < 55 and macd_cross and vol_spike and ema_slope > 0:
            is_conservative = True

    # Fetch Fundamentals for candidates
    # Use ticker as default name/industry if not in map
    pe_ratio, div_yield, market_cap = 0, 0, 0
    name = NAME_MAP.get(ticker, ticker)
    industry = "N/A"
    
    try:
        info = t_obj.info
        pe_ratio = info.get('trailingPE', 0)
        div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
        raw_industry = info.get('industry', 'N/A')
        industry = INDUSTRY_MAP.get(raw_industry, raw_industry)
        market_cap = info.get('marketCap', 0)
        # If longName is present and we don't have it in our map, we could still use ticker or English
        if name == ticker:
            name = info.get('shortName', ticker)
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
        "ob_date": ob_start_date,
        "fvg": [float(x) for x in valid_fvg] if valid_fvg else None,
        "fvg_date": fvg_start_date,
        "target1": float(target1) if target1 else None,
        "stop_loss": float(stop_loss) if stop_loss else None,
        "entry_zone": entry_zone,
        "latest_close": float(latest['Close']),
        "upside_pct": float((target1 - latest['Close']) / latest['Close']) if target1 and target1 > latest['Close'] else 0.0,
        "rr_ratio": float(rr_ratio),
        "ema_slope": float(ema_slope),
        "is_conservative": bool(is_conservative),
        "date": datetime.datetime.now().strftime('%Y-%m-%d')
    }

def update_triggered_history(new_signals, repair=False):
    """
    更新歷史紀錄庫。
    new_signals: 掃描到的訊號列表
    repair: 是否為修補模式（若是，則會比對日期與 Ticker 避免重複）
    """
    history_file = 'data/triggered_records.json'
    records = []
    
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except: pass

    existing_keys = set([f"{r['date']}_{r['ticker']}" for r in records])
    updated = False

    for s in new_signals:
        # 只處理觸發標的
        if s.get('status') == 'Triggered':
            key = f"{s['date']}_{s['ticker']}"
            if key not in existing_keys:
                new_record = {
                    "ticker": s['ticker'],
                    "name": s['name'],
                    "target": s['target1'],
                    "stop_loss": s['stop_loss'],
                    "entry_price": s['latest_close']
                })
                new_count += 1
                
    if new_count > 0:
        # 按日期降序排列
        records.sort(key=lambda x: x['date'], reverse=True)
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=4)
        print(f"新增了 {new_count} 筆成形紀錄到 {history_file}")

def run_analysis():
    print(f"[{datetime.datetime.now()}] Scanning {len(UNIVERSE)} Taiwan stocks...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(calculate_smc_and_vegas, t): t for t in UNIVERSE}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Filter by upside (at least 5%)
    filtered_results = [res for res in results if res.get('upside_pct', 0) >= 0.05]
    
    # Sort triggered first, then potential, then by upside
    sorted_res = sorted(filtered_results, key=lambda x: (x['status'] == 'Triggered', x['upside_pct']), reverse=True)
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
        
    # -- 新增功能：更新已成型歷史紀錄 --
    update_triggered_history(top_picks)

    print(f"[{datetime.datetime.now()}] Saved {len(top_picks)} picks to signals.json and history.json")
    return top_picks

if __name__ == "__main__":
    run_analysis()
