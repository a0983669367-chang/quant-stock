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
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
    }
    /* 全域字體放大 */
    .stMarkdown p, .stMarkdown li {
        font-size: 18px !important;
        line-height: 1.6;
    }
    /* 摺疊面板標題樣式 */
    .st-expanderHeader p {
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
    }
    /* 指標數據放大 */
    [data-testid="stMetricLabel"] p {
        font-size: 16px !important;
        color: #94a3b8 !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
        font-weight: 800 !important;
    }
    /* 骨架強化 */
    .st-expanderContent {
        background: rgba(255, 255, 255, 0.02);
        padding: 20px !important;
        border-radius: 0 0 12px 12px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 台股 SMC x Vegas 量化監控系統")
st.markdown("針對台股前 150 大市值標的進行 SMC (Smart Money Concepts) 結構與 Vegas 通道分析，尋找高勝率伏擊點。")

with st.expander("📖 系統原理與使用說明 (新手必讀)"):
    st.markdown("""
    ### 核心選股邏輯 (SMC x Vegas)
    本系統結合了 **Smart Money Concepts (SMC)** 與 **Vegas Channel** 兩套經典策略，旨在捕捉大戶資金進場後的修正機會。
    
    1. **Vegas Channel (趨勢過濾)**：
       - 使用 144/169 與 576/676 EMA 通道。
       - 只有當 **長線多頭排列** 時（EMA 144 > 576），系統才會發出信號，確保我們始終站在趨勢正確的一方。
    
    2. **SMC 結構分析 (OB / FVG)**：
       - **Order Block (OB, 紅色方塊)**：找出大戶曾經強力買進、並留下「足跡」的支撐區塊。這是價格回測時最穩定的墊腳石。
       - **Fair Value Gap (FVG, 綠色方塊)**：由於大戶進場速度太快導致的「價格缺口」，市場通常會回填這些區間以尋求平衡。
    
    3. **黃金伏擊區 (買點判定)**：
       - 當股價 **回測** 至 OB 或 FVG 的交集區域，且受支撐於 Vegas 通道上方時，即為系統認定的高勝率進場點。
    
    ---
    
    ### 介面燈號與狀態說明
    系統會自動將標的分為兩大類，以便您快速決策：
    
    *   **🟢 已成形 (Triggered)**：
        - 代表股價「正處於」或「剛剛脫離」建議進場區間（黃金伏擊區）。
        - 標的結構最為成熟，目前即是最佳的關注或佈置時機。
        
    *   **🟡 未成形 (Potential)**：
        - 代表股價目前正向建議進場區間「靠近中」，但尚未完全進入。
        - 這類標的就像是「正在拉回的獵物」，適合加入觀察名單進行伏擊。
    
    *   **預期報酬率過濾**：
        - 系統已自動剔除所有預期報酬率 **低於 5%** 的標的，確保您看到的都是具備一定獲利空間的優選股票。
    
    ---
    
    ### 如何開始使用？
    1.  瀏覽下方的自動分類清單，尋找感興趣的標的。
    2.  點擊標題展開 **摺疊選單**，查看詳細的 **本益比/殖利率** 與 **結構圖表**。
    3.  參考圖表中的 **紅色區域 (OB)** 與 **建議進場位**，確認佈局位置。
    4.  務必參考 **防守停損位** 進行風險控制，祝您投資獲利！
    """)

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
triggered = [s for s in signals if s['status'] == 'Triggered']
potential = [s for s in signals if s['status'] == 'Potential']

sections = [
    ("🔥 已觸發進場帶 (Triggered)", triggered, "🟢"),
    ("⏳ 潛在伏擊標的 (Potential)", potential, "🟡")
]

for title, list_stocks, icon in sections:
    if list_stocks:
        st.markdown(f"## {title}")
        for stock in list_stocks:
            ticker = stock['ticker']
            name = stock.get('name', ticker)
            industry = stock.get('industry', 'N/A')
            pe = stock.get('pe_ratio', 0)
            dy = stock.get('div_yield', 0)
            price = stock.get('latest_close', 0)
            entry = stock.get('entry_zone') or "未成型"
            sl = stock.get('stop_loss') or 0
            target = stock.get('target1') or 0
            upside = stock.get('upside_pct', 0) * 100
            
            # 建立摺疊標籤文字 (使用彩色 Markdown 與粗體)
            status_text = f":green[已成形]" if stock['status'] == 'Triggered' else f":orange[未成形]"
            label = f"{icon} **{ticker} {name}** | 現價 **{price:.2f}** | 預期報酬 **+{upside:.1f}%** | {status_text}"
            
            with st.expander(label):
                # 內部排版：上方顯示詳細指標，下方顯示圖表
                m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                with m_col1:
                    st.metric("建議進場位", entry)
                with m_col2:
                    st.metric("預期報酬率", f"+{upside:.1f}%")
                with m_col3:
                    st.metric("停利修正位", f"{target:.1f}" if target else "-")
                with m_col4:
                    st.metric("防守停損位", f"{sl:.1f}" if sl else "-")
                
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    st.info(f"🏷️ 產業類別: {industry}")
                with f_col2:
                    st.info(f"📊 本益比: {pe:.1f}" if pe > 0 else "📊 本益比: -")
                with f_col3:
                    st.info(f"💰 殖利率: {dy:.1f}%" if dy > 0 else "💰 殖利率: -")

                with st.spinner(f"正在載入 {ticker} 結構分析圖..."):
                    # 重新取得該股的完整 DataFrame
                    t_obj = yf.Ticker(ticker)
                    df = t_obj.history(period='2y') 
                    if not df.empty:
                        # 標準化
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        df = df.loc[:, ~df.columns.duplicated()].copy()
                        
                        df['EMA_144'] = df['Close'].ewm(span=144, adjust=False).mean()
                        df['EMA_169'] = df['Close'].ewm(span=169, adjust=False).mean()
                        df['EMA_576'] = df['Close'].ewm(span=576, adjust=False).mean()
                        df['EMA_676'] = df['Close'].ewm(span=676, adjust=False).mean()

                        fig = go.Figure()
                        # Candlestick
                        fig.add_trace(go.Candlestick(
                            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                            name='價格', increasing_line_color='#22c55e', decreasing_line_color='#ef4444'
                        ))
                        # EMAs
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_144'], mode='lines', name='EMA 144', line=dict(color='#fcd34d', width=1.5)))
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_169'], mode='lines', name='EMA 169', line=dict(color='#fbbf24', width=1.5)))
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_576'], mode='lines', name='EMA 576', line=dict(color='#a78bfa', width=1.5)))
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_676'], mode='lines', name='EMA 676', line=dict(color='#8b5cf6', width=1.5)))

                        # SMC Shapes
                        if stock.get('ob') and stock.get('ob_date'):
                            fig.add_shape(type="rect", x0=stock['ob_date'], y0=stock['ob'][1], x1=df.index[-1].strftime('%Y-%m-%d'), y1=stock['ob'][0],
                                fillcolor="rgba(239, 68, 68, 0.2)", line=dict(width=0), layer="below")
                        if stock.get('fvg') and stock.get('fvg_date'):
                            fig.add_shape(type="rect", x0=stock['fvg_date'], y0=stock['fvg'][1], x1=df.index[-1].strftime('%Y-%m-%d'), y1=stock['fvg'][0],
                                fillcolor="rgba(34, 197, 94, 0.2)", line=dict(width=0), layer="below")
                        if target:
                            fig.add_hline(y=target, line_dash="dash", line_color="#cbd5e1", annotation_text="目標位")

                        fig.update_layout(
                            template="plotly_dark", height=500, margin=dict(l=0, r=0, t=30, b=0),
                            xaxis_rangeslider_visible=False, hovermode='x unified'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        st.info("💡 **結構解讀**：紅色方塊代表強勢 OB 支撐，綠色代表 FVG 真實價值缺口。當價格回測這些區間且位於 Vegas 通道上方時，為高勝率伏擊區。")
                    else:
                        st.warning("無法載入歷史 K 線圖表。")
