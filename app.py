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
import textwrap

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
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        backdrop-filter: blur(15px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stock-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 24px rgba(0,0,0,0.5);
        border-color: rgba(99, 102, 241, 0.8);
    }
    .stock-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
    }
    .stock-title {
        display: flex;
        flex-direction: column;
    }
    .stock-card h2 {
        margin: 0;
        color: #f8fafc;
        font-weight: 800;
        font-size: 22px;
        letter-spacing: -0.02em;
    }
    .industry-tag {
        font-size: 11px;
        background: rgba(99, 102, 241, 0.25);
        color: #c7d2fe;
        padding: 3px 10px;
        border-radius: 6px;
        margin-top: 6px;
        display: inline-block;
        font-weight: 600;
    }
    .status-badge {
        font-size: 11px;
        padding: 5px 12px;
        border-radius: 8px;
        font-weight: 800;
        text-transform: uppercase;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .bg-triggered { background: linear-gradient(135deg, #10b981, #059669); color: white; border: 1px solid #047857; }
    .bg-potential { background: linear-gradient(135deg, #f59e0b, #d97706); color: white; border: 1px solid #b45309; }
    
    .price-row {
        margin: 12px 0;
        padding: 10px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        display: flex;
        align-items: baseline;
        gap: 8px;
    }
    .price-label { font-size: 12px; color: #94a3b8; }
    .price-value { font-size: 24px; font-weight: 800; color: #ffffff; }

    .metric-row {
        display: flex;
        justify-content: space-between;
        margin-top: 14px;
        gap: 12px;
    }
    .metric {
        flex: 1;
        display: flex;
        flex-direction: column;
    }
    .metric-label {
        font-size: 10px;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .metric-value {
        font-size: 15px;
        color: #f1f5f9;
        font-weight: 700;
        margin-top: 4px;
    }
    .buy-zone { color: #34d399; }
    .stop-loss { color: #f87171; }
    .target-price { color: #60a5fa; }
    .potential-val { color: #fbbf24; }
    
    .fundamental-row {
        display: flex;
        gap: 16px;
        margin-top: 14px;
        padding: 10px 14px;
        background: rgba(255, 255, 255, 0.04);
        border-radius: 8px;
    }
    .f-metric {
        font-size: 12px;
        color: #cbd5e1;
        font-weight: 500;
    }
    .f-val { color: #ffffff; font-weight: 700; margin-left: 4px; }
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
    triggered = [s for s in signals if s['status'] == 'Triggered']
    potential = [s for s in signals if s['status'] == 'Potential']
    
    sections = [
        ("🔥 已觸發進場帶 (Triggered)", triggered, "bg-triggered"),
        ("⏳ 潛在伏擊標的 (Potential)", potential, "bg-potential")
    ]
    
    for title, list_stocks, badge_class in sections:
        if list_stocks:
            st.markdown(f"### {title}")
            for stock in list_stocks:
                ticker = stock['ticker']
                name = stock.get('name', ticker)
                status_cn = "已成形" if stock['status'] == 'Triggered' else "未成形"
                industry = stock.get('industry', 'N/A')
                pe = stock.get('pe_ratio', 0)
                dy = stock.get('div_yield', 0)
                entry = stock.get('entry_zone') or "未成型"
                sl = stock.get('stop_loss') or 0
                target = stock.get('target1') or 0
                upside = stock.get('upside_pct', 0) * 100
                
                sl_str = f"{sl:.1f}" if sl else "-"
                target_str = f"{target:.1f}" if target else "-"
                pe_str = f"{pe:.1f}" if pe > 0 else "-"
                dy_str = f"{dy:.1f}%" if dy > 0 else "-"
                
                # 顯示樣式 (直接靠左對齊，確保 Markdown 不會誤判為程式碼區塊)
                html = f"""<div class="stock-card">
<div class="stock-header">
<div class="stock-title">
<h2>{ticker} {name}</h2>
<div class="industry-tag">🏷️ {industry}</div>
</div>
<span class="status-badge {badge_class}">{status_cn}</span>
</div>
<div class="price-row">
<span class="price-label">目前現價</span>
<span class="price-value">NT$ {stock.get('latest_close', 0):.2f}</span>
</div>
<div class="metric-row">
<div class="metric">
<span class="metric-label">🎯 建議進場位</span>
<span class="metric-value buy-zone">{entry}</span>
</div>
<div class="metric" style="text-align: right;">
<span class="metric-label">🚀 預期報酬率</span>
<span class="metric-value potential-val">+{upside:.1f}%</span>
</div>
</div>
<div class="metric-row">
<div class="metric">
<span class="metric-label">📈 停利修正位</span>
<span class="metric-value target-price">{target_str}</span>
</div>
<div class="metric" style="text-align: right;">
<span class="metric-label">🛡️ 防守停損位</span>
<span class="metric-value stop-loss">{sl_str}</span>
</div>
</div>
<div class="fundamental-row">
<div class="f-metric">📊 本益比 <span class="f-val">{pe_str}</span></div>
<div class="f-metric">💰 殖利率 <span class="f-val">{dy_str}</span></div>
</div>
</div>"""
                st.markdown(html, unsafe_allow_html=True)
                if st.button(f"📊 結構圖 {ticker}", key=f"btn_{ticker}", use_container_width=True):
                    st.session_state.selected_ticker = ticker
                    st.rerun()

with col2:
    selected = st.session_state.selected_ticker
    if selected:
        st.subheader(f"📊 {selected} 價格動態與 SMC 預測結構")
        
        stock_data = next((s for s in signals if s['ticker'] == selected), None)
        
        with st.spinner("繪製 K 線圖中..."):
            t_obj = yf.Ticker(selected)
            df = t_obj.history(period="6mo")
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Clean up duplicated columns and ensure flat structure
            df = df.loc[:, ~df.columns.duplicated()].copy()
            
            # Robustly extract essential columns as Series
            for col in ['Open', 'High', 'Low', 'Close']:
                if col in df.columns:
                    if isinstance(df[col], pd.DataFrame):
                        df[col] = df[col].iloc[:, 0]
            
            if 'Close' not in df.columns or df.empty:
                st.error(f"無法獲取 {selected} 的完整數據")
            else:
                df.dropna(subset=['Close'], inplace=True)
                
                close_s = df['Close']
                df['EMA_144'] = close_s.ewm(span=144, adjust=False).mean()
                df['EMA_169'] = close_s.ewm(span=169, adjust=False).mean()
                df['EMA_576'] = close_s.ewm(span=576, adjust=False).mean()
                df['EMA_676'] = close_s.ewm(span=676, adjust=False).mean()

                fig = go.Figure()
                open_s = df['Open']
                high_s = df['High']
                low_s = df['Low']

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
