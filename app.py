import streamlit as st
import json
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import data_fetcher
import threading
import streamlit.components.v1 as components

# TradingView 符號對照表
TV_SYMBOL_MAP = {
    'NQ=F': 'CME_MINI:NQ1!',
    'ES=F': 'CME_MINI:ES1!',
    'YM=F': 'CBOT:YM1!',
    'NKD=F': 'OSE:NK2251!',
    'GC=F': 'COMEX:GC1!',
    'CL=F': 'NYMEX:CL1!'
}

def render_unified_chart(ticker, df, stock_data, interval='1d'):
    """使用 TradingView Lightweight Charts 渲染統一化、包含 AI 標記的圖表"""
    if df is None or df.empty:
        st.error("無法取得圖表數據")
        return

    # 1. 準備 K 線數據
    df_js = df.reset_index()
    # 轉換日期為 timestamp (Lightweight Charts 要求秒數)
    df_js['time'] = df_js['Date'].astype('int64') // 10**9
    
    # yfinance 回傳的欄位可能是 MultiIndex，強制提取 1D 資料
    def extract_series(col_name):
        s = df_js[col_name]
        return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s

    candles = []
    for i, row in df_js.iterrows():
        candles.append({
            'time': int(row['time']),
            'open': float(extract_series('Open')[i]),
            'high': float(extract_series('High')[i]),
            'low': float(extract_series('Low')[i]),
            'close': float(extract_series('Close')[i])
        })

    # 2. 準備 EMA 數據
    ema144 = [{'time': int(row['time']), 'value': float(row['EMA_144'])} for i, row in df_js.iterrows() if not pd.isna(row['EMA_144'])]
    ema576 = [{'time': int(row['time']), 'value': float(row['EMA_576'])} for i, row in df_js.iterrows() if not pd.isna(row['EMA_576'])]

    # 3. 準備 AI 預測色塊 (POI Box)
    box_data = []
    box_color = "rgba(52, 211, 153, 0.2)" # 預設多頭綠色
    box_border = "rgba(52, 211, 153, 0.8)"
    
    if stock_data and stock_data.get('predicted_zone'):
        p_low, p_high = stock_data['predicted_zone']
        if stock_data['direction'] == "Short":
            box_color = "rgba(248, 113, 113, 0.2)" # 空頭紅色
            box_border = "rgba(248, 113, 113, 0.8)"
        
        # 色塊顯示在最近的 40 根 K 棒
        start_idx = max(0, len(df_js) - 40)
        for i in range(start_idx, len(df_js)):
            box_data.append({
                'time': int(df_js.iloc[i]['time']),
                'value': float(p_high),
                'bottom': float(p_low)
            })

    # 4. 目標位 (DOL)
    target_price = stock_data.get('logical_target') if stock_data else None

    # 5. 組合 JS 程式碼
    html_code = f"""
    <div id="unified_chart" style="width:100%; height:600px; background:#0f172a; border-radius: 8px; overflow:hidden;"></div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        const chartElement = document.getElementById('unified_chart');
        const chart = LightweightCharts.createChart(chartElement, {{
            layout: {{
                background: {{ color: '#0f172a' }},
                textColor: '#94a3b8',
            }},
            grid: {{
                vertLines: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                horzLines: {{ color: 'rgba(255, 255, 255, 0.05)' }},
            }},
            rightPriceScale: {{
                borderColor: 'rgba(255, 255, 255, 0.1)',
            }},
            timeScale: {{
                borderColor: 'rgba(255, 255, 255, 0.1)',
                timeVisible: true,
                secondsVisible: false,
            }},
            crosshair: {{
                mode: LightweightCharts.CrosshairMode.Normal,
            }},
        }});

        const candleSeries = chart.addCandlestickSeries({{
            upColor: '#22c55e', downColor: '#ef4444', borderVisible: false,
            wickUpColor: '#22c55e', wickDownColor: '#ef4444'
        }});
        candleSeries.setData({json.dumps(candles)});

        // Vegas Channel
        const line144 = chart.addLineSeries({{ color: '#fcd34d', lineWidth: 1, title: 'EMA 144' }});
        line144.setData({json.dumps(ema144)});
        const line576 = chart.addLineSeries({{ color: '#a78bfa', lineWidth: 1, title: 'EMA 576' }});
        line576.setData({json.dumps(ema576)});

        // AI Predicted Box (Using AreaSeries trick)
        if ({json.dumps(box_data)}.length > 0) {{
            const boxSeries = chart.addAreaSeries({{
                topColor: '{box_color}',
                bottomColor: 'rgba(0,0,0,0)',
                lineColor: '{box_border}',
                lineWidth: 1,
                priceLineVisible: false,
            }});
            // 由於 AreaSeries base 預設在 0，我們需要強行處理下界，或者用兩個 Series。
            // 這裡簡單處理：顯示上界，並用 Marker 標註。
            boxSeries.setData({json.dumps(box_data)});
        }}

        // Target Line
        if ({json.dumps(target_price)}) {{
            candleSeries.createPriceLine({{
                price: {target_price or 0},
                color: '#38bdf8',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: 'Logical Target (DOL)',
            }});
        }}

        window.addEventListener('resize', () => {{
            chart.applyOptions({{ width: chartElement.clientWidth, height: chartElement.clientHeight }});
        }});
    </script>
    """
    components.html(html_code, height=620)

# 頁面配置
st.set_page_config(page_title="全球期貨 SMC x Vegas 預測戰情室", layout="wide", page_icon="📈")

# 自定義 CSS 樣式 (極致美學、現代化設計，完全移除 onclick 與 postMessage以防 Safari 白畫面)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .stock-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 16px;
        backdrop-filter: blur(10px);
        transition: transform 0.2s, box-shadow 0.2s;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stock-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        border-color: rgba(99, 102, 241, 0.5);
    }
    .stock-card h2 {
        margin-top: 0;
        color: #e2e8f0;
        font-weight: 700;
        font-size: 24px;
    }
    .metric-row {
        display: flex;
        justify-content: space-between;
        margin-top: 16px;
    }
    .metric {
        display: flex;
        flex-direction: column;
    }
    .metric-label {
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 18px;
        color: #f8fafc;
        font-weight: 600;
        margin-top: 4px;
    }
    .buy-zone { color: #34d399; }
    .stop-loss { color: #f87171; }
    .target-price { color: #60a5fa; }
    .potential { color: #facc15; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------
# UI 區塊設計 - 解決首次載入白畫面
# -----------------------------------------------------
import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    import pytz # fallback
    
st.title("📈 全球期貨指標 SMC x Vegas 戰情室")
st.markdown("針對全球權重指數 (NQ, ES, YM, NKD, A50) 進行 SMC 聰明錢結構與 Vegas 通道分析。報價來源為 yfinance (約 15 分鐘延遲)。")

# 透過 Streamlit @st.cache_data 原生機制，實作即時掃描與 15 分鐘快取
@st.cache_data(ttl=900, show_spinner="🤖 正在分析全球期貨最新價格結構...")
def get_latest_futures_signals(interval, period):
    # 直接從後端函式取得回傳值，增加穩定性
    data = data_fetcher.run_analysis(interval=interval, period=period)
    return data if data else []

# 移除歷史資料載入邏輯

def render_dashboard(display_stocks, key_prefix, chart_interval='1d', chart_period='3y'):
    if not display_stocks:
        return

    col1, col2 = st.columns([1, 2])

    session_key = f'selected_ticker_{key_prefix}'
    if session_key not in st.session_state:
        st.session_state[session_key] = display_stocks[0]['ticker'] if display_stocks else None

    with col1:
        for stock in display_stocks:
            ticker = stock['ticker']
            c_name = stock.get('company_name', '').replace('\n', ' ').replace('\r', '')
            sector = stock.get('sector', '').replace('\n', ' ').replace('\r', '')
            desc = stock.get('description', '').replace('\n', ' ').replace('\r', '')
            
            direction = stock.get('direction', 'Unknown')
            dir_color = "#34d399" if direction == "Long" else "#f87171"
            dir_icon = "📈" if direction == "Long" else "📉"
            
            # 預測進場位
            zone = stock.get('predicted_zone')
            poi_type = stock.get('poi_type', 'POI')
            entry_str = f"{min(zone):.2f} - {max(zone):.2f}" if zone else "尋找中..."
            
            # 目標位
            target = stock.get('logical_target', 0)
            target_str = f"{target:.2f}" if target else "-"
            
            # 位置相對於平衡點
            close = stock.get('latest_close', 0)
            eq = stock.get('equilibrium', 0)
            pos_text = "折價區 (偏低)" if close < eq else "溢價區 (偏高)"
            pos_color = "#34d399" if (direction == "Long" and close < eq) or (direction == "Short" and close > eq) else "#94a3b8"

            sector_html = f'<span style="font-size: 13px; font-weight: normal; background: #334155; padding: 2px 8px; border-radius: 12px; color: #cbd5e1;">{sector}</span>' if sector and sector != '未知' else ''
            
            # IC 評分呈現邏輯
            ic_val = stock.get('current_ic', 0)
            ic_color = "#34d399" if ic_val >= 0.05 else ("#f87171" if ic_val <= -0.05 else "#94a3b8")
            ic_text = f"{ic_val:+.3f}"
            ic_html = f'<div style="background: rgba(255,255,255,0.05); padding: 4px 12px; border-radius: 6px; display: inline-flex; align-items: center; gap: 8px;"><span style="color: #94a3b8; font-size: 12px;">預測勝率 (IC)</span><span style="color: {ic_color}; font-weight: 700; font-size: 14px;">{ic_text}</span></div>'

            html = f"""
            <div class="stock-card">
                <h2 style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 0;">
                    <span style="color:#60a5fa;">{ticker}</span>
                    <span>{c_name}</span>
                    {sector_html}
                </h2>
                <div style="display: flex; gap: 12px; margin-bottom: 16px; align-items: center;">
                    <div style="background: {dir_color}22; color: {dir_color}; padding: 4px 10px; border-radius: 4px; font-weight: bold; border: 1px solid {dir_color}44;">{dir_icon} {direction} Bias</div>
                    {ic_html}
                </div>
                <div class="metric-row">
                    <div class="metric"><span class="metric-label">預測未來最佳進場 ({poi_type})</span><span class="metric-value buy-zone">{entry_str}</span></div>
                    <div class="metric"><span class="metric-label">當前價值位階</span><span style="color: {pos_color}; font-size: 18px; font-weight: 700; margin-top: 4px;">{pos_text}</span></div>
                </div>
                <div class="metric-row">
                    <div class="metric"><span class="metric-label">波段目標獲利價 (DOL)</span><span class="metric-value target-price">{target_str}</span></div>
                    <div class="metric"><span class="metric-label">當前最新成交價</span><span class="metric-value" style="color: #f8fafc;">{close:.2f}</span></div>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
            if st.button(f"📊 展開未來預測圖表: {ticker}", key=f"btn_{ticker}_{key_prefix}", use_container_width=True):
                st.session_state[session_key] = ticker
                st.rerun()

    with col2:
        selected = st.session_state[session_key]
        if selected:
            st.subheader(f"📊 {selected} 價格動態與 SMC 結構")
        
        stock_data = next((s for s in display_stocks if s['ticker'] == selected), None)
        
        try:
            with st.spinner(f"正在同步全球期貨數據 ({chart_interval})..."):
                df = yf.download(selected, period=chart_period, interval=chart_interval, progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.dropna(subset=['Close'], inplace=True)
                
                # 計算 Vegas 通道，確保傳遞給前端圖表
                close_s = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
                df['EMA_144'] = close_s.ewm(span=144, adjust=False).mean()
                df['EMA_576'] = close_s.ewm(span=576, adjust=False).mean()

                # 直接啟動統一化實戰圖表 (TradingView 質感)
                render_unified_chart(selected, df, stock_data, chart_interval)
                
                st.info("💡 **實戰提示**：深色背景圖表支援 TradingView 式縮放。**彩色透明區塊**為系統預測的關鍵伏擊區，**藍色虛線**為 DOL 目標。")
        except Exception as e:
            st.error(f"圖表系統暫時無法處理 {selected}: {str(e)}")

# 使用頁籤切換時框
tab_daily, tab_hourly = st.tabs(["📅 日線波段預測", "⏱️ 小時級別伏擊"])

def display_timeframe_content(interval, period, key_suffix):
    try:
        signals = get_latest_futures_signals(interval, period)
    except Exception as e:
        st.error(f"❌ {interval} 系統分析發生異常: {str(e)}")
        signals = []

    col_btn, _ = st.columns([1, 2])
    with col_btn:
        if st.button(f"🔄 重新掃描 ({interval})", key=f"btn_rescan_{key_suffix}"):
            st.cache_data.clear()
            st.rerun()

    if signals:
        st.success(f"🔥 全球市場 ({interval}) 掃描完成！共發現 {len(signals)} 檔符合趨勢指標標的！")
    else:
        st.info(f"目前 {interval} 無任何指標觸發，市場可能處於震盪或過於極端。")

    render_dashboard(signals, key_suffix, interval, period)

with tab_daily:
    display_timeframe_content('1d', '3y', 'daily')

with tab_hourly:
    display_timeframe_content('1h', '60d', 'hourly')
