import streamlit as st
import json
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import data_fetcher
import datetime

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
    /* 內容區塊強化 */
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
    
    1. **Vegas Channel (趨勢過濾)**：使用 144/169 與 576/676 EMA 通道。只有當長線多頭排列時，系統才會發出信號。
    2. **SMC 結構分析 (OB / FVG)**：找出大戶足跡 (OB) 與價格缺口 (FVG)。
    3. **黃金伏擊區 (買點判定)**：當股價回測至支撐區域，且受支撐於 Vegas 通道上方時。
    
    ---
    ### 介面燈號與狀態說明
    *   **🟢 已成形 (Triggered)**：標的正處於建議進場區間，適合執行。
    *   **🟡 未成形 (Potential)**：標的正向區間靠近中，適合加觀察清單伏擊。
    *   **預期報酬率過濾**：系統自動剔除報酬率低於 5% 的標的。
    """)

# 數據獲取與快取
@st.cache_data(ttl=3600, show_spinner="🤖 正在執行全市場掃描...")
def get_latest_signals():
    data = data_fetcher.run_analysis()
    return data if data else []

def refresh_data():
    st.cache_data.clear()
    st.rerun()

col_btn, _ = st.columns([1, 4])
with col_btn:
    if st.button("🔄 立即重新掃描全市場"):
        refresh_data()

signals = get_latest_signals()

if not signals:
    st.info("🎯 今日無符合條件之標的。")
    st.stop()
else:
    st.success(f"🔥 掃描完成！為您精選出 {len(signals)} 檔符合結構的標的！")

# 頁面分頁排版
tab1, tab2 = st.tabs(["📊 實時監控", "📂 歷史成形回顧"])

with tab1:
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
                price = stock.get('latest_close', 0)
                upside = stock.get('upside_pct', 0) * 100
                status_text = f":green[已成形]" if stock['status'] == 'Triggered' else f":orange[未成形]"
                label = f"{icon} **{ticker} {name}** | 現價 **{price:.2f}** | 預期報酬 **+{upside:.1f}%** | {status_text}"
                
                with st.expander(label):
                    m1, m2, m3, m4 = st.columns(4)
                    with m1: st.metric("建議進場位", stock.get('entry_zone', 'N/A'))
                    with m2: st.metric("預期報酬率", f"+{upside:.1f}%")
                    with m3: st.metric("停利修正位", f"{stock.get('target1', 0):.1f}")
                    with m4: st.metric("防守停損位", f"{stock.get('stop_loss', 0):.1f}")
                    
                    st.info(f"🏷️ 產業: {stock.get('industry', 'N/A')} | 📊 PE: {stock.get('pe_ratio', 0):.1f} | 💰 殖利率: {stock.get('div_yield', 0):.1f}%")
                    
                    with st.spinner(f"正在載入 {ticker} 分析圖..."):
                        t_obj = yf.Ticker(ticker)
                        df = t_obj.history(period='2y')
                        if not df.empty:
                            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                            df = df.loc[:, ~df.columns.duplicated()].copy()
                            df['EMA_144'] = df['Close'].ewm(span=144, adjust=False).mean()
                            df['EMA_576'] = df['Close'].ewm(span=576, adjust=False).mean()

                            fig = go.Figure()
                            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='價格', increasing_line_color='#22c55e', decreasing_line_color='#ef4444'))
                            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_144'], name='EMA 144', line=dict(color='#fcd34d', width=1.5)))
                            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_576'], name='EMA 576', line=dict(color='#a78bfa', width=1.5)))
                            
                            if stock.get('ob') and stock.get('ob_date'):
                                fig.add_shape(type="rect", x0=stock['ob_date'], y0=stock['ob'][1], x1=df.index[-1].strftime('%Y-%m-%d'), y1=stock['ob'][0], fillcolor="rgba(239, 68, 68, 0.2)", line=dict(width=0))
                            if stock.get('fvg') and stock.get('fvg_date'):
                                fig.add_shape(type="rect", x0=stock['fvg_date'], y0=stock['fvg'][1], x1=df.index[-1].strftime('%Y-%m-%d'), y1=stock['fvg'][0], fillcolor="rgba(34, 197, 94, 0.2)", line=dict(width=0))
                            
                            fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0, r=0, t=30, b=0), xaxis_rangeslider_visible=False, hovermode='x unified')
                            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.markdown("### 📂 歷史成形標的回顧 & 2026 回測成效")
    st.info("此處紀錄了從 2026 年初至今的自動回測數據與實際掃描紀錄。")
    
    history_file = 'data/triggered_records.json'
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
            if records:
                df_h = pd.DataFrame(records)
                
                # 計算統計數據
                total = len(df_h)
                wins = len(df_h[df_h['result'] == '🎯 止盈'])
                losses = len(df_h[df_h['result'] == '🛡️ 止損'])
                running = len(df_h[df_h['result'] == '⏳ 進行中'])
                win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                
                # 顯示美化指標
                m_c1, m_c2, m_c3, m_c4 = st.columns(4)
                with m_c1:
                    st.metric("歷史勝率", f"{win_rate:.1f}%")
                with m_c2:
                    st.metric("累積止盈", f"{wins} 筆")
                with m_c3:
                    st.metric("累積止損", f"{losses} 筆")
                with m_c4:
                    st.metric("追蹤中", f"{running} 筆")
                
                # 格式化表格
                df_display = df_h[["date", "ticker", "name", "entry_price", "target", "stop_loss", "result"]]
                df_display.columns = ["成形日期", "股票代號", "名稱", "當時進價", "目標價", "停損價", "最終成效"]
                
                # 使用顏色標註
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                st.caption("註：勝率計算排除『進行中』的標的。回測邏輯為 SMC x Vegas 完美成形後追蹤後續最高/最低點。")
            else:
                st.info("目前尚無紀錄。")
        except Exception as e:
            st.error(f"讀取紀錄出錯: {e}")
    else:
        st.info("歷史紀錄檔案尚未建立。請點擊『重新掃描』觸發數據更新。")
