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

def render_tradingview_widget(ticker, interval='D'):
    """嵌入 TradingView 高級圖表小組件"""
    tv_symbol = TV_SYMBOL_MAP.get(ticker, ticker)
    # 將 Yahoo interval 轉換為 TradingView interval
    tv_interval = 'D' if interval == '1d' else '60'
    
    html_code = f"""
    <div class="tradingview-widget-container" style="height:600px; width:100%;">
      <div id="tradingview_widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{tv_symbol}",
        "interval": "{tv_interval}",
        "timezone": "Asia/Taipei",
        "theme": "dark",
        "style": "1",
        "locale": "zh_tw",
        "toolbar_bg": "#1e293b",
        "enable_publishing": false,
        "hide_top_toolbar": false,
        "hide_legend": false,
        "save_image": true,
        "container_id": "tradingview_widget"
      }});
      </script>
    </div>
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
        
        chart_tab1, chart_tab2 = st.tabs(["🤖 AI 預測結構", "📊 TradingView 實戰圖"])
        
        with chart_tab1:
            with st.spinner(f"繪製 {chart_interval} K 線圖中..."):
                df = yf.download(selected, period=chart_period, interval=chart_interval, progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                    
                df.dropna(subset=['Close'], inplace=True)
                
                # ... (EMA and Plotly logic) ...
                close_s = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
                df['EMA_144'] = close_s.ewm(span=144, adjust=False).mean()
                df['EMA_169'] = close_s.ewm(span=169, adjust=False).mean()
                df['EMA_576'] = close_s.ewm(span=576, adjust=False).mean()
                df['EMA_676'] = close_s.ewm(span=676, adjust=False).mean()

                df['Future_Return'] = close_s.shift(-5) / close_s - 1
                df['Vegas_Strength'] = (df['EMA_144'] - df['EMA_576']) / df['EMA_576']
                rolling_ic = df['Vegas_Strength'].rolling(window=60).corr(df['Future_Return'])
                df['Rolling_Rank_IC'] = rolling_ic.fillna(0)

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.03, row_heights=[0.75, 0.25])

                open_s = df['Open'].iloc[:, 0] if isinstance(df['Open'], pd.DataFrame) else df['Open']
                high_s = df['High'].iloc[:, 0] if isinstance(df['High'], pd.DataFrame) else df['High']
                low_s = df['Low'].iloc[:, 0] if isinstance(df['Low'], pd.DataFrame) else df['Low']

                fig.add_trace(go.Candlestick(
                    x=df.index, open=open_s, high=high_s, low=low_s, close=close_s,
                    name='價格', increasing_line_color='#22c55e', decreasing_line_color='#ef4444'
                ), row=1, col=1)

                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_144'], mode='lines', name='EMA 144', line=dict(color='#fcd34d', width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_169'], mode='lines', name='EMA 169', line=dict(color='#fbbf24', width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_576'], mode='lines', name='EMA 576', line=dict(color='#a78bfa', width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_676'], mode='lines', name='EMA 676', line=dict(color='#8b5cf6', width=1.5)), row=1, col=1)

                ic_colors = ['#22c55e' if val >= 0 else '#ef4444' for val in df['Rolling_Rank_IC']]
                fig.add_trace(go.Bar(
                    x=df.index, y=df['Rolling_Rank_IC'], name='Rank IC (5日勝率)',
                    marker_color=ic_colors, opacity=0.8
                ), row=2, col=1)
                fig.add_hline(y=0.05, line_dash="dash", line_color="rgba(34,197,94,0.5)", row=2, col=1)
                fig.add_hline(y=-0.05, line_dash="dash", line_color="rgba(239,68,68,0.5)", row=2, col=1)

                if stock_data:
                    rh = stock_data.get('range_high')
                    rl = stock_data.get('range_low')
                    eq = stock_data.get('equilibrium')
                    
                    if rh and rl:
                        fig.add_shape(type="line", x0=df.index[-120] if len(df) > 120 else df.index[0], y0=rh, x1=df.index[-1], y1=rh, line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"), row=1, col=1)
                        fig.add_shape(type="line", x0=df.index[-120] if len(df) > 120 else df.index[0], y0=rl, x1=df.index[-1], y1=rl, line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"), row=1, col=1)
                        fig.add_shape(type="line", x0=df.index[-120] if len(df) > 120 else df.index[0], y0=eq, x1=df.index[-1], y1=eq, line=dict(color="rgba(255,255,255,0.2)", width=2, dash="dash"), row=1, col=1)
                        fig.add_annotation(x=df.index[-60] if len(df) > 60 else df.index[0], y=eq, text="Equilibrium (50%)", showarrow=False, font=dict(color="gray", size=10), row=1, col=1)

                    if stock_data.get('predicted_zone'):
                        p_low, p_high = stock_data['predicted_zone']
                        p_color = "rgba(52, 211, 153, 0.3)" if stock_data['direction'] == "Long" else "rgba(248, 113, 113, 0.3)"
                        fig.add_shape(type="rect", x0=df.index[-40] if len(df) > 40 else df.index[0], y0=p_low, x1=df.index[-1], y1=p_high, fillcolor=p_color, line=dict(width=0), layer="below", row=1, col=1)
                        fig.add_annotation(x=df.index[-20] if len(df) > 20 else df.index[0], y=p_high, text=f"Predicted {stock_data.get('poi_type')}", showarrow=True, arrowhead=1, font=dict(color="white", size=10), row=1, col=1)

                    if stock_data.get('logical_target'):
                        fig.add_hline(y=stock_data['logical_target'], line_dash="dash", line_color="#38bdf8", annotation_text="Logical Target (DOL)", row=1, col=1)

                fig.update_layout(
                    template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis_rangeslider_visible=False, xaxis2_rangeslider_visible=False,
                    margin=dict(l=0, r=0, t=30, b=0),
                    hovermode='x unified', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )

                st.plotly_chart(fig, use_container_width=True)

        with chart_tab2:
            render_tradingview_widget(selected, chart_interval)

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
