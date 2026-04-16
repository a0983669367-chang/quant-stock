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
    'FTW=F'  # 富時中國 A50
]

FUTURES_METADATA = {
    'NQ=F': {'name': '納斯達克 100 期貨 (Nasdaq)', 'sector': '指數期貨', 'desc': '全球科技藍籌股領航指標，波動劇烈適合波段操作。'},
    'ES=F': {'name': '標普 500 期貨 (S&P 500)', 'sector': '指數期貨', 'desc': '全美前 500 大市值權重，全球資產配置最核心指標。'},
    'YM=F': {'name': '道瓊期貨 (Dow Jones)', 'sector': '指數期貨', 'desc': '包含 30 檔具備代表性的商業巨頭，歷史最悠久的成熟市場指標。'},
    'NKD=F': {'name': '日經 225 期貨 (Nikkei)', 'sector': '指數期貨', 'desc': '反應日本主要上市企業表現，亞太區龍頭量化交易標的。'},
    'FTW=F': {'name': '中國 A50 期貨 (A50)', 'sector': '指數期貨', 'desc': '追蹤中國 A 股流通市值最大 50 檔企業，受政策與外資高度影響。'}
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
                    
                # 計算當前預測勝率 (Current IC)
                try:
                    df_ic = df.dropna(subset=['Close']).copy()
                    df_ic['EMA_144'] = df_ic['Close'].ewm(span=144, adjust=False).mean()
                    df_ic['EMA_576'] = df_ic['Close'].ewm(span=576, adjust=False).mean()
                    df_ic['Future_Return'] = df_ic['Close'].shift(-5) / df_ic['Close'] - 1
                    df_ic['Vegas_Strength'] = (df_ic['EMA_144'] - df_ic['EMA_576']) / df_ic['EMA_576']
                    rolling_ic = df_ic['Vegas_Strength'].rolling(window=60).corr(df_ic['Future_Return'])
                    # dropna 以確保取得最近期的那筆有效資料
                    current_ic = float(rolling_ic.dropna().iloc[-1]) if not rolling_ic.dropna().empty else 0.0
                except:
                    current_ic = 0.0
                    
                res['upside_pct'] = upside_pct
                res['ema_strength'] = ema_strength
                res['current_ic'] = current_ic
                
                # 過濾掉潛在報酬率小於 10% 的個股
                if upside_pct >= 0.1:
                    results.append(res)
        except Exception as e:
            # print(f"Error {ticker}: {e}")
            continue
                
    # 為所有掃描成功的標的補充中文資料
    final_list = []
    for res in results:
        t = res['ticker']
        name, sector, desc = get_futures_info(t)
        res['company_name'] = name
        res['sector'] = sector
        res['description'] = desc
        
        # 期貨波動大，如果沒有觸發 trigger，我們依然把它放進 list 供觀察，只是標註為 fallback
        if not res.get('trigger'):
            res['is_fallback'] = True
            res['fallback_reason'] = "SMC 買盤區間已算出，目前股價尚未進入最佳買點，建議列為優先伏擊對象。"
            
        final_list.append(res)
    
    # 依照預期報酬排序
    final_list = sorted(final_list, key=lambda x: x.get('upside_pct', 0), reverse=True)
    
    os.makedirs('data', exist_ok=True)
    with open('data/signals.json', 'w') as f:
        json.dump(final_list, f, indent=4)
        
    print(f"[{datetime.datetime.now()}] Futures Analysis complete. Saved to data/signals.json")

if __name__ == "__main__":
    run_analysis()
