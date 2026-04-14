import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import datetime
import concurrent.futures
import requests
from bs4 import BeautifulSoup

# 精選上市櫃前 150 大流動性佳大中型股
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

def get_tw_stock_info(ticker):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f'https://tw.stock.yahoo.com/quote/{ticker}/profile', headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        strings = list(soup.stripped_strings)
        
        name, sector, desc = '未知', '未知', '無'
        try:
            idx = strings.index('公司名稱')
            name = strings[idx+1]
        except: pass
        
        try:
            idx = strings.index('產業類別')
            sector = strings[idx+1]
        except: pass
        
        try:
            idx = strings.index('主要經營業務')
            desc = strings[idx+1]
            if desc == '配股資訊': desc = '無'
        except: pass
        return {'company_name': name, 'sector': sector, 'description': desc}
    except Exception:
        return {'company_name': '未知', 'sector': '未知', 'description': '無'}

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
    is_vegas_bullish = latest['EMA_144'] > latest['EMA_576']

    recent_lows = get_swing_lows(df_recent, window=3)
    
    valid_ob = None
    ob_start_date = None
    valid_fvg = None
    fvg_start_date = None
    
    # 從最新波段低點開始檢查
    for sl_idx in reversed(recent_lows):
        # 限定: 尋找過去 20 天內的波段低點
        if len(df_recent) - sl_idx > 20:
            continue
            
        # 尋找造成波段低點前的最後一根陰線 (Close < Open) -> OB
        ob_idx = None
        for i in range(sl_idx, max(-1, sl_idx-10), -1):
            if df_recent['Close'].iloc[i] < df_recent['Open'].iloc[i]:
                ob_idx = i
                break
        
        if ob_idx is None:
            continue
            
        ob_high = float(df_recent['High'].iloc[ob_idx])
        ob_low = float(df_recent['Low'].iloc[ob_idx])
        
        # 尋找 OB 之後 3 日內的 Bullish FVG
        # FVG 邏輯: 第 1 根的 High < 第 3 根的 Low
        fvg_found = False
        fvg_high = None
        fvg_low = None
        fvg_idx = None
        
        for j in range(ob_idx, min(len(df_recent)-2, ob_idx + 4)):
            c1_high = df_recent['High'].iloc[j]
            c3_low = df_recent['Low'].iloc[j+2]
            if c3_low > c1_high:
                fvg_found = True
                fvg_high = float(c3_low)
                fvg_low = float(c1_high)
                fvg_idx = j
                break
                
        if fvg_found:
            # 驗證是否與 EMA 144~169 的通道有重疊
            ob_fvg_min = min(ob_low, fvg_low)
            ob_fvg_max = max(ob_high, fvg_high)
            
            ema144 = latest['EMA_144']
            ema169 = latest['EMA_169']
            ema_min = min(ema144, ema169)
            ema_max = max(ema144, ema169)
            
            overlap = max(0, min(ob_fvg_max, ema_max) - max(ob_fvg_min, ema_min))
            if overlap > 0:
                valid_ob = (ob_high, ob_low)
                ob_start_date = df_recent.index[ob_idx].strftime('%Y-%m-%d')
                valid_fvg = (fvg_high, fvg_low)
                fvg_start_date = df_recent.index[fvg_idx].strftime('%Y-%m-%d')
                break

    # 流動性池 Liquidity Pools (未被突破的前高)
    swing_highs = get_swing_highs(df_recent, window=5)
    targets = []
    for sh_idx in reversed(swing_highs):
        sh_val = float(df_recent['High'].iloc[sh_idx])
        if sh_idx == len(df_recent) - 1 or df_recent['High'].iloc[sh_idx+1:].max() <= sh_val:
            targets.append(sh_val)
            
    # 等高點強流動性池 (EQH)
    eqh_pairs = []
    for i in range(len(targets)):
        for j in range(i+1, len(targets)):
            if abs(targets[i] - targets[j]) / targets[i] <= 0.005:
                eqh_pairs.append((targets[i], targets[j]))

    target1 = targets[0] if len(targets) > 0 else None
    target2 = max(eqh_pairs[0]) if eqh_pairs else None

    # 觸發條件
    trigger = False
    stop_loss = None
    entry_zone = None
    
    if is_vegas_bullish and valid_ob:
        if valid_fvg:
            entry_top = max(valid_ob[0], valid_fvg[0])
            entry_bottom = min(valid_ob[1], valid_fvg[1])
            # 檢查最新一根是否跌入區間內且尚未跌破 OB 最低價
            if float(latest['Low']) <= entry_top and float(latest['Close']) >= valid_ob[1]:
                trigger = True
                stop_loss = valid_ob[1]
                entry_zone = f"{entry_bottom:.2f} - {entry_top:.2f}"

    return {
        "ticker": ticker,
        "trigger": trigger,
        "is_vegas_bullish": bool(is_vegas_bullish),
        "ema144": float(latest['EMA_144']),
        "ema576": float(latest['EMA_576']),
        "ob": valid_ob,
        "ob_date": ob_start_date,
        "fvg": valid_fvg,
        "fvg_date": fvg_start_date,
        "target1": target1,
        "target2": target2,
        "stop_loss": stop_loss,
        "entry_zone": entry_zone,
        "latest_close": float(latest['Close'])
    }

def run_analysis():
    print(f"[{datetime.datetime.now()}] Running SMC & Vegas Analysis on {len(UNIVERSE)} symbols...")
    results = []
    
    # 統一透過原生 yfinance 批次下載，避免自己使用 ThreadPoolExecutor 造成的 yfinance 內部資料混淆 (Race Condition) Bug
    print(f"[{datetime.datetime.now()}] 正在批次下載市場行情...")
    df_all = yf.download(UNIVERSE, period='3y', progress=False, group_by='ticker', threads=True)
    
    for ticker in UNIVERSE:
        try:
            # yfinance 批次下載的結構為 MultiIndex [('2330.TW', 'Close'), ...]
            if len(UNIVERSE) > 1:
                # 確保不崩潰如果 ticker 沒成功抓到
                if ticker not in df_all.columns.levels[0]:
                    continue
                df = df_all[ticker].copy()
            else:
                df = df_all.copy()
            
            # yf.download 若部分標的下市可能只有單一 level，這裡確保安全取出
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            res = calculate_smc_and_vegas_df(ticker, df)
            
            if res:
                target = res.get('target1')
                close_price = res.get('latest_close')
                upside_pct = 0
                if target and close_price and target > close_price:
                    upside_pct = (target - close_price) / close_price
                
                # 計算趨勢強度 (短期均線帶動多頭的距離)
                ema_strength = 0
                if res.get('ema144') and res.get('ema576'):
                    ema_strength = (res['ema144'] - res['ema576']) / res['ema576']
                    
                res['upside_pct'] = upside_pct
                res['ema_strength'] = ema_strength
                
                # 過濾掉潛在報酬率小於 10% 的個股
                if upside_pct >= 0.1:
                    results.append(res)
        except Exception as e:
            # print(f"Error {ticker}: {e}")
            continue
                
    # 過濾出正宗觸發股
    triggered = [r for r in results if r.get('trigger')]
    
    final_list = []
    if len(triggered) > 0:
        # 有觸發股，依照預期報酬與趨勢強度挑選最強的前五名
        sorted_results = sorted(triggered, key=lambda x: (x.get('upside_pct', 0), x.get('ema_strength', 0)), reverse=True)
        final_list = sorted_results[:5]
    else:
        # 秋後算帳，沒有觸發股，啟動 Fallback 機制
        fallback_list = []
        
        # 情境 1：SMC 已成型但在等待回測
        smc_wait_list = [r for r in results if r.get('is_vegas_bullish') and r.get('ob') and r.get('fvg') and not r.get('trigger')]
        
        if len(smc_wait_list) > 0:
            # 以預期報酬排序
            smc_wait_list = sorted(smc_wait_list, key=lambda x: x.get('upside_pct', 0), reverse=True)
            for r in smc_wait_list:
                r['is_fallback'] = True
                r['fallback_reason'] = "SMC 買盤結構已佈局完成，長線做多確立。惟目前股價尚未跌入最佳買盤區，強烈建議列為優先伏擊觀察股，待拉回碰觸買區即為飆股候選。"
                fallback_list.append(r)
                
        # 如果情境 1 挑不滿 3 檔，用情境 2 補滿
        if len(fallback_list) < 3:
            # 尋找 Vegas 強勢動能股
            strong_trend_list = [r for r in results if r.get('is_vegas_bullish') and r.get('ticker') not in [f.get('ticker') for f in fallback_list]]
            strong_trend_list = sorted(strong_trend_list, key=lambda x: x.get('ema_strength', 0), reverse=True)
            
            for r in strong_trend_list:
                r['is_fallback'] = True
                r['fallback_reason'] = "目前市場無完美 SMC 買盤成型，此標的為當前 Vegas 均線多頭爆發力最強之個股，屬極強動能觀察名單。"
                fallback_list.append(r)
                if len(fallback_list) >= 3:
                    break
                    
        final_list = fallback_list[:3]

    # 追加中文公司資料 (只針對前幾名)
    for r in final_list:
        info = get_tw_stock_info(r['ticker'])
        r['company_name'] = info['company_name']
        r['sector'] = info['sector']
        r['description'] = info['description']

    os.makedirs('data', exist_ok=True)
    with open('data/signals.json', 'w') as f:
        json.dump(final_list, f, indent=4)
        
    print(f"[{datetime.datetime.now()}] Analysis complete. Saved Top 5 to data/signals.json")

if __name__ == "__main__":
    run_analysis()
