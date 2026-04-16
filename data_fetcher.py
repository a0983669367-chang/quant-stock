import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import datetime
import concurrent.futures
import requests
from bs4 import BeautifulSoup

# 全球指標性海外期貨 (yfinance 延遲 15min)
UNIVERSE = [
    'NQ=F',  # 納斯達克 100
    'ES=F',  # 標普 500
    'YM=F',  # 道瓊工業
    'NKD=F', # 日經 225
    'GC=F',  # 黃金期貨
    'CL=F'   # 原油期貨
]

FUTURES_METADATA = {
    'NQ=F': {'name': '納斯達克 100 期貨 (Nasdaq)', 'sector': '指數期貨', 'desc': '全球科技藍籌股領航指標，波動劇烈適合波段操作。'},
    'ES=F': {'name': '標普 500 期貨 (S&P 500)', 'sector': '指數期貨', 'desc': '全美前 500 大市值權重，全球資產配置最核心指標。'},
    'YM=F': {'name': '道瓊期貨 (Dow Jones)', 'sector': '指數期貨', 'desc': '包含 30 檔具備代表性的商業巨頭，歷史最悠久的成熟市場指標。'},
    'NKD=F': {'name': '日經 225 期貨 (Nikkei)', 'sector': '指數期貨', 'desc': '反應日本主要上市企業表現，亞太區龍頭量化交易標的。'},
    'GC=F': {'name': '黃金期貨 (Gold)', 'sector': '金屬期貨', 'desc': '避險資產王者，在市場不確定性高時具備強大的保值預測力。'},
    'CL=F': {'name': '輕原油期貨 (Crude Oil)', 'sector': '能源期貨', 'desc': '反映全球經濟擴張與能源需求，波動巨大適合趨勢追蹤。'}
}

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

def get_futures_info(ticker):
    meta = FUTURES_METADATA.get(ticker, {'name': ticker, 'sector': '未知', 'desc': '無'})
    return meta['name'], meta['sector'], meta['desc']

def calculate_smc_and_vegas_df(ticker, df):
    if df.empty:
        return None

    # 確保資料有 High, Low, Close
    if 'Close' not in df.columns:
        return None
    
    # 填補空缺值
    df.ffill(inplace=True)

    # 計算 Vegas 通道
    df['EMA_144'] = df['Close'].ewm(span=144, adjust=False).mean()
    df['EMA_169'] = df['Close'].ewm(span=169, adjust=False).mean()
    df['EMA_576'] = df['Close'].ewm(span=576, adjust=False).mean()
    df['EMA_676'] = df['Close'].ewm(span=676, adjust=False).mean()

    # 擷取近期的 K 棒供運算 (約半年)
    df_recent = df.tail(150).copy()
    if len(df_recent) < 20:
        return None

    latest = df_recent.iloc[-1]
    
    # --- 1. 趨勢判定 (Vegas Bias) ---
    is_bullish = latest['EMA_144'] > latest['EMA_576']
    direction = "Long" if is_bullish else "Short"
    
    # --- 2. 交易區間 (Trading Range & equilibrium) ---
    # 鎖定近 120 根 K 棒的高低點作為當前的戰場平衡位
    range_df = df_recent.tail(120)
    range_high = float(range_df['High'].max())
    range_low = float(range_df['Low'].min())
    equilibrium = (range_high + range_low) / 2
    
    # --- 3. 預測伏擊區 (Predicted Entry Zone - POIs) ---
    # 多頭趨勢：在折價區 (Discount < 50%) 尋找最強 FVG 或 OB
    # 空頭趨勢：在溢價區 (Premium > 50%) 尋找最強 FVG 或 OB
    predicted_zone = None
    poi_type = None
    
    if is_bullish:
        # 尋找 Discount 區間內的 Bullish FVG (第1根High < 第3根Low)
        # 優先尋找距離現在最近且尚未被碰觸的
        for i in range(len(range_df)-3, 5, -1):
            c1_h = range_df['High'].iloc[i]
            c3_l = range_df['Low'].iloc[i+2]
            if c3_l > c1_h: # Bullish FVG
                fvg_avg = (c3_l + c1_h) / 2
                if fvg_avg < equilibrium: # 必須在折價區
                    predicted_zone = (float(c1_h), float(c3_l))
                    poi_type = "Discount FVG"
                    break
        
        # 如果沒找到 FVG，尋找 OB
        if not predicted_zone:
            recent_lows = get_swing_lows(range_df, window=3)
            for sl_idx in reversed(recent_lows):
                if range_df['Low'].iloc[sl_idx] < equilibrium:
                    # 尋找前一波陰線 (OB)
                    for k in range(sl_idx, max(0, sl_idx-5), -1):
                        if range_df['Close'].iloc[k] < range_df['Open'].iloc[k]:
                            predicted_zone = (float(range_df['Low'].iloc[k]), float(range_df['High'].iloc[k]))
                            poi_type = "Discount OB"
                            break
                if predicted_zone: break
    else:
        # 空頭趨勢：尋找 Premium 區間內的 Bearish FVG (第1根Low > 第3根High)
        for i in range(len(range_df)-3, 5, -1):
            c1_l = range_df['Low'].iloc[i]
            c3_h = range_df['High'].iloc[i+2]
            if c1_l > c3_h: # Bearish FVG
                fvg_avg = (c3_h + c1_l) / 2
                if fvg_avg > equilibrium: # 必須在溢價區
                    predicted_zone = (float(c3_h), float(c1_l))
                    poi_type = "Premium FVG"
                    break
                    
        if not predicted_zone:
            recent_highs = get_swing_highs(range_df, window=3)
            for sh_idx in reversed(recent_highs):
                if range_df['High'].iloc[sh_idx] > equilibrium:
                    for k in range(sh_idx, max(0, sh_idx-5), -1):
                        if range_df['Close'].iloc[k] > range_df['Open'].iloc[k]:
                            predicted_zone = (float(range_df['Low'].iloc[k]), float(range_df['High'].iloc[k]))
                            poi_type = "Premium OB"
                            break
                if predicted_zone: break

    # --- 4. 目標止贏位 (Logical Target - Draw on Liquidity) ---
    # 多頭目標：區間高點；空頭目標：區間低點
    logical_target = range_high if is_bullish else range_low
    
    # --- 5. 計算預測勝率 (Current IC) ---
    current_ic = 0.0
    try:
        df_ic = df.dropna(subset=['Close']).copy()
        df_ic['Future_Return'] = df_ic['Close'].shift(-5) / df_ic['Close'] - 1
        df_ic['Vegas_Strength'] = (df_ic['EMA_144'] - df_ic['EMA_576']) / df_ic['EMA_576']
        rolling_ic = df_ic['Vegas_Strength'].rolling(window=60).corr(df_ic['Future_Return'])
        valid_ics = rolling_ic.dropna()
        if not valid_ics.empty:
            current_ic = float(valid_ics.iloc[-1])
    except:
        pass

    return {
        "ticker": ticker,
        "direction": direction,
        "range_high": range_high,
        "range_low": range_low,
        "equilibrium": equilibrium,
        "predicted_zone": predicted_zone,
        "poi_type": poi_type,
        "logical_target": logical_target,
        "latest_close": float(latest['Close']),
        "current_ic": current_ic,
        "ema144": float(latest['EMA_144']),
        "ema576": float(latest['EMA_576'])
    }

def run_analysis():
    print(f"[{datetime.datetime.now()}] Running SMC & Vegas Analysis on {len(UNIVERSE)} symbols...")
    results = []
    
    # 統一透過原生 yfinance 批次下載，避免自己使用 ThreadPoolExecutor 造成的 yfinance 內部資料混淆 (Race Condition) Bug
    print(f"[{datetime.datetime.now()}] 正在批次下載市場行情...")
    df_all = yf.download(UNIVERSE, period='3y', progress=False, group_by='ticker', threads=True)
    
    for ticker in UNIVERSE:
        try:
            # 兼容不同 yfinance 回傳結構 (確保能帶入正確的 Ticker 資料)
            if ticker in df_all.columns.get_level_values(0):
                df = df_all[ticker].copy()
            else:
                # 嘗試單獨下載 (做為最後防線)
                df = yf.download(ticker, period='2y', progress=False)
                
            if df.empty: continue
            
            # yf.download 回傳若有多重欄位則簡化
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            res = calculate_smc_and_vegas_df(ticker, df)
            if res:
                results.append(res)
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            continue
                
    # 為所有掃描成功的標的補充中文資料
    final_list = []
    for res in results:
        t = res['ticker']
        name, sector, desc = get_futures_info(t)
        res['company_name'] = name
        res['sector'] = sector
        res['description'] = desc
        final_list.append(res)
    
    os.makedirs('data', exist_ok=True)
    print(f"[{datetime.datetime.now()}] Futures Prediction complete. {len(final_list)} items found.")
    return final_list

if __name__ == "__main__":
    run_analysis()
