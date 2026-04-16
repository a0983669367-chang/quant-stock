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

# 側邊欄配置
st.sidebar.title("⚙️ 系統設定")

# 策略模式切換
strategy_mode = st.sidebar.selectbox(
    "選擇策略模式",
    ["🟢 穩健型 (Conservative)", "🔵 標準型 (Standard)"],
    help="穩健型會過濾掉趨勢不明顯、盈虧比較差或大戶量能未確認的標的，追求更高的勝率。"
)

is_conservative_only = "穩健型" in strategy_mode

# 透過 Streamlit 原生機制實作即時掃描與快取
@st.cache_data(ttl=3600, show_spinner="🤖 正在執行全市場掃描 (預計 20-30 秒)...")
def get_latest_signals():
    data = data_fetcher.run_analysis()
    return data if data else []

def refresh_data():
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("🔄 立即重新掃描全市場"):
    refresh_data()

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
    ### 策略模式說明
    *   **🟢 穩健型**：額外要求 **EMA 144 斜率向上**、**盈虧比 > 1.5** 且 **近期買盤增量**，適合追求高勝率。
    *   **🔵 標準型**：只要結構符合即發出信號，捕捉更多潛在契機。
    """)

# 取得資料
all_signals = get_latest_signals()

# 根據模式過濾
if is_conservative_only:
    signals = [s for s in all_signals if s.get('is_conservative', False)]
else:
    signals = all_signals

if not signals:
    if is_conservative_only:
        st.warning("🎯 目前無符合「穩健型」條件的標的，建議切換至「標準型」查看，或等待市場結構修正。")
    else:
        st.info("🎯 今日無符合條件之標的。")
    st.stop()
else:
    mode_text = "穩健型" if is_conservative_only else "標準型"
    st.success(f"🔥 {mode_text}掃描完成！為您精選出 {len(signals)} 檔符合結構的標的！")

# 頁面分頁排版
tab1, tab2 = st.tabs(["📊 實時監控", "📂 歷史成形回顧 & 2026 回測成效"])

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
                rr = stock.get('rr_ratio', 0)
                status_text = f":green[已成形]" if stock['status'] == 'Triggered' else f":orange[未成形]"
                label = f"{icon} **{ticker} {name}** | 報酬 **+{upside:.1f}%** | RR **{rr:.1f}** | {status_text}"
                
                with st.expander(label):
                    m1, m2, m3, m4 = st.columns(4)
                    with m1: st.metric("建議進場位", stock.get('entry_zone', 'N/A'))
                    with m2: st.metric("預期報酬率", f"+{upside:.1f}%")
                    with m3: st.metric("盈虧比 (RR)", f"{rr:.1f}")
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
    st.info("※ 歷史統計將根據當前「策略模式」自動過濾結果。")
    
    history_file = 'data/triggered_records.json'
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
            if records:
                raw_df = pd.DataFrame(records)
                # 根據模式過濾
                if is_conservative_only:
                    if 'is_conservative' in raw_df.columns:
                        df_h = raw_df[raw_df['is_conservative'] == True].copy()
                    else:
                        df_h = pd.DataFrame()
                else:
                    df_h = raw_df
                
                if not df_h.empty:
                    wins = len(df_h[df_h['result'] == '🎯 止盈'])
                    losses = len(df_h[df_h['result'] == '🛡️ 止損'])
                    running = len(df_h[df_h['result'] == '⏳ 進行中'])
                    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                    
                    m_c1, m_c2, m_c3, m_c4 = st.columns(4)
                    with m_c1: st.metric("歷史勝率", f"{win_rate:.1f}%")
                    with m_c2: st.metric("累積止盈", f"{wins} 筆")
                    with m_c3: st.metric("累積止損", f"{losses} 筆")
                    with m_c4: st.metric("追蹤中", f"{running} 筆")
                    
                    df_display = df_h[["date", "ticker", "name", "entry_price", "target", "stop_loss", "result"]]
                    df_display.columns = ["日期", "代號", "名稱", "進場價", "目標價", "停損價", "最終成效"]
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    st.warning("⚠️ 目前模式下尚無歷史紀錄。")
            else: st.info("目前尚無紀錄。")
        except Exception as e: st.error(f"讀取紀錄出錯: {e}")
    else:
        st.info("歷史紀錄檔案尚未建立。")
