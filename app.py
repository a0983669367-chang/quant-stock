import streamlit as st
import json
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import data_fetcher
import threading
import datetime

# 頁面配置
st.set_page_config(page_title="台股 SMC x Vegas 量化監控系統", layout="wide", page_icon="📈")

# 自定義 CSS 樣式
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

st.title("📈 台股 SMC x Vegas 量化監控系統")
st.markdown("針對台股前 150 大市值標的進行 SMC (Smart Money Concepts) 結構與 Vegas 通道分析，尋找高勝率伏擊點。")

# 透過 Streamlit 原生機制實作即時掃描與快取
@st.cache_data(ttl=3600, show_spinner="🤖 正在執行全市場掃描 (預計 20-30 秒)...")
def get_latest_signals():
    # 執行掃描並取得結果
    data = data_fetcher.run_analysis()
    return data if data else []

# 建立掃描觸發邏輯
def refresh_data():
    st.cache_data.clear()
    st.rerun()

col_btn, _ = st.columns([1, 4])
with col_btn:
    if st.button("🔄 立即重新掃描全市場"):
        refresh_data()

# 取得資料
signals = get_latest_signals()

if not signals:
    st.info("🎯 今日無標的觸發完美 SMC x Vegas 信號，或市場處於盤整期。")
    st.stop()
else:
    st.success(f"🔥 掃描完成！為您精選出 {len(signals)} 檔符合強勢多頭修正結構的標的！")

# 頁面排版
col1, col2 = st.columns([1, 2])

# 初始化選股狀態
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = signals[0]['ticker'] if signals else None

with col1:
    st.subheader("📋 符合信號標的清單")
    for stock in signals:
        ticker = stock['ticker']
        entry = stock.get('entry_zone') or "未成型"
        sl = stock.get('stop_loss') or 0
        target = stock.get('target1') or 0
        upside = stock.get('upside_pct', 0) * 100
        
        sl_str = f"NT$ {sl:.2f}" if sl else "-"
        target_str = f"NT$ {target:.2f}" if target else "-"
        
        # 顯示樣式
        html = f"""
        <div class="stock-card">
            <h2>{ticker}</h2>
            <div class="metric-row">
                <div class="metric">
                    <span class="metric-label">建議進場區間</span>
                    <span class="metric-value buy-zone">{entry}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">潛在報酬空間</span>
                    <span class="metric-value potential">+{upside:.1f}%</span>
                </div>
            </div>
            <div class="metric-row">
                <div class="metric">
                    <span class="metric-label">停利目標位</span>
                    <span class="metric-value target-price">{target_str}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">防守停損位</span>
                    <span class="metric-value stop-loss">{sl_str}</span>
                </div>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
        if st.button(f"📊 點擊查看 {ticker} 結構圖", key=f"btn_{ticker}", use_container_width=True):
            st.session_state.selected_ticker = ticker
            st.rerun()

with col2:
    selected = st.session_state.selected_ticker
    if selected:
        st.subheader(f"📊 {selected} 價格動態與 SMC 預測結構")
        
        stock_data = next((s for s in signals if s['ticker'] == selected), None)
        
        with st.spinner("繪製 K 線圖中..."):
            df = yf.download(selected, period="6mo", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.dropna(subset=['Close'], inplace=True)
            
            close_s = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
            df['EMA_144'] = close_s.ewm(span=144, adjust=False).mean()
            df['EMA_169'] = close_s.ewm(span=169, adjust=False).mean()
            df['EMA_576'] = close_s.ewm(span=576, adjust=False).mean()
            df['EMA_676'] = close_s.ewm(span=676, adjust=False).mean()

            fig = go.Figure()
            open_s = df['Open'].iloc[:, 0] if isinstance(df['Open'], pd.DataFrame) else df['Open']
            high_s = df['High'].iloc[:, 0] if isinstance(df['High'], pd.DataFrame) else df['High']
            low_s = df['Low'].iloc[:, 0] if isinstance(df['Low'], pd.DataFrame) else df['Low']

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df.index, open=open_s, high=high_s, low=low_s, close=close_s,
                name='價格', increasing_line_color='#22c55e', decreasing_line_color='#ef4444'
            ))

            # EMAs
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_144'], mode='lines', name='EMA 144', line=dict(color='#fcd34d', width=1.5)))
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_169'], mode='lines', name='EMA 169', line=dict(color='#fbbf24', width=1.5)))
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_576'], mode='lines', name='EMA 576', line=dict(color='#a78bfa', width=1.5)))
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_676'], mode='lines', name='EMA 676', line=dict(color='#8b5cf6', width=1.5)))

            # SMC Structures
            if stock_data:
                if stock_data.get('ob') and stock_data.get('ob_date'):
                    ob_high, ob_low = stock_data['ob']
                    fig.add_shape(type="rect",
                        x0=stock_data['ob_date'], y0=ob_low, x1=df.index[-1].strftime('%Y-%m-%d'), y1=ob_high,
                        fillcolor="rgba(239, 68, 68, 0.2)", line=dict(width=0), layer="below", name="Bullish OB"
                    )

                if stock_data.get('fvg') and stock_data.get('fvg_date'):
                    fvg_high, fvg_low = stock_data['fvg']
                    fig.add_shape(type="rect",
                        x0=stock_data['fvg_date'], y0=fvg_low, x1=df.index[-1].strftime('%Y-%m-%d'), y1=fvg_high,
                        fillcolor="rgba(34, 197, 94, 0.2)", line=dict(width=0), layer="below", name="Bullish FVG"
                    )

                if stock_data.get('target1'):
                    fig.add_hline(y=stock_data['target1'], line_dash="dash", line_color="#cbd5e1", annotation_text="Target 1 (BSL)")

            fig.update_layout(
                template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=30, b=0),
                hovermode='x unified', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("💡 **結構解讀**：紅色方塊代表強勢 OB 支撐，綠色代表 FVG 真實價值缺口。當價格回測這些區間且位於 Vegas 通道上方時，為高勝率伏擊區。")
