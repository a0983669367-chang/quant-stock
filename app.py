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
    /* 內容區塊強化 */
    .st-expanderContent {
        background: rgba(255, 255, 255, 0.015) !important;
        padding: 25px !important;
        border-radius: 0 0 16px 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-top: none !important;
    }
    /* 卡片式視覺 */
    .stock-card {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        padding: 24px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }
    /* 強力數據顯示 */
    .hero-metric-box {
        text-align: center;
        padding: 15px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 12px;
        border-left: 4px solid #3b82f6;
    }
</style>
""", unsafe_allow_html=True)

# 側邊欄配置
st.sidebar.title("⚙️ 系統設定")

# 策略模式切換
strategy_mode = st.sidebar.selectbox(
    "選擇策略模式",
    ["🔵 標準型 (Standard)", "🟢 穩健型 (Conservative)"],
    help="穩健型會過濾掉趨勢不明顯、盈虧比較差或大戶量能未確認的標的，追求更高的勝率。"
)

st.sidebar.info("📢 **數據延遲公告**：本系統報價串接自 Yahoo Finance 免費 API，台股行情通常有 **15 分鐘延遲**，請投資人留意，勿作為當沖即時依據。")

is_conservative_only = "穩健型" in strategy_mode

# 透過 Streamlit 原生機制實作即時掃描與快取
@st.cache_data(ttl=3600, show_spinner="🤖 正在執行全市場掃描 (預計 20-30 秒)...")
def get_latest_signals():
    # 確保資料夾存在
    os.makedirs('data', exist_ok=True)
    if os.path.exists('data/signals.json'):
        try:
            with open('data/signals.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    
    # 若無檔案則執行掃描
    data = data_fetcher.run_analysis()
    return data if data else []

def refresh_data():
    data_fetcher.run_analysis()
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("🔄 立即重新掃描全市場"):
    refresh_data()

st.title("📈 台股 SMC x Vegas 量化監控系統")
st.markdown("針對台股前 150 大市值標的進行 SMC (Smart Money Concepts) 結構與 Vegas 通道分析，尋找高勝率伏擊點。")

# 頁面頂端通知欄
c1, c2 = st.columns([1, 1])
with c1:
    st.info(f"💡 **目前監控模式**：{strategy_mode}")
with c2:
    st.warning("⏱️ **報價延遲說明**：系統數據約有 15 分鐘延遲")

with st.expander("📖 系統原理與使用說明 (新手必讀)"):
    st.markdown("""
    ### 核心選股邏輯 (SMC x Vegas)
    本系統結合了 **Smart Money Concepts (SMC)** 與 **Vegas Channel** 兩套經典策略，旨在捕捉大戶資金進場後的修正機會。
    
    1. **Vegas Channel (趨勢過濾)**：使用 144/169 與 576/676 EMA 通道。只有當長線多頭排列時，系統才會發出信號。
    2. **SMC 結構分析 (OB / FVG)**：找出大戶足跡 (OB) 與價格缺口 (FVG)。
    3. **黃金伏擊區 (買點判定)**：當股價回測至支撐區域，且受支撐於 Vegas 通道上方時。
    
    ---
    ### 策略模式說明
    *   **🟢 穩健型**：要求 **EMA 144 斜率 > 0**、**盈虧比 > 1.2** 且 **量能確認**，排除震盪盤。
    *   **🔵 標準型**：只要結構符合即發出信號，捕捉更多補漲契機。
    """)

def render_stock_details(stock):
    ticker = stock['ticker']
    name = stock.get('name', ticker)
    
    with st.spinner(f"🚀 正在抓取 {ticker} 即時報價與圖表..."):
        try:
            t_obj = yf.Ticker(ticker)
            df = t_obj.history(period='2y')
            
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                df = df.loc[:, ~df.columns.duplicated()].copy()
                
                current_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2] if len(df) > 1 else current_price
                change = current_price - prev_price
                last_time = df.index[-1].strftime('%Y-%m-%d %H:%M')
                
                upside = stock.get('upside_pct', 0) * 100
                rr = stock.get('rr_ratio', 0)
                
                # --- 主角區 ---
                st.markdown("### 🏆 市場核心數據")
                h1, h2 = st.columns([1.2, 1])
                with h1:
                    st.metric("即時價格", f"{current_price:.2f}", delta=f"{change:.2f}", help="此為 Yahoo Finance 提供之數據 (約 15 分鐘延遲)")
                with h2:
                    st.metric("預期報酬率", f"+{upside:.1f}%", delta=f"RR: {rr:.1f}")
                
                st.divider()
                
                # --- 詳細區 ---
                st.markdown("#### 🔍 伏擊細節")
                d1, d2, d3 = st.columns(3)
                with d1: st.metric("建議進場位", stock.get('entry_zone', 'N/A'))
                with d2: st.metric("防守停損位", f"{stock.get('stop_loss', 0):.1f}")
                with d3: st.metric("目標價位", f"{stock.get('target1', 0):.1f}")
                
                st.caption(f"🕒 數據最後更新：{last_time} (Yahoo Finance 延遲約 15 分鐘)")

                # --- 圖表區 ---
                st.markdown("#### 📈 技術圖表 (SMC x Vegas)")
                df['EMA_144'] = df['Close'].ewm(span=144, adjust=False).mean()
                df['EMA_576'] = df['Close'].ewm(span=576, adjust=False).mean()
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='盤勢'))
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_144'], name='EMA 144', line=dict(color='#fcd34d', width=1.5)))
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_576'], name='EMA 576', line=dict(color='#a78bfa', width=1.5)))
                
                fig.update_layout(
                    template="plotly_dark", 
                    height=550, 
                    margin=dict(l=0, r=0, t=20, b=0), 
                    xaxis_rangeslider_visible=False,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(f"無法取得 {ticker} 的歷史數據")
        except Exception as e:
            st.error(f"即時數據抓取失敗: {e}")

# 取得資料
all_signals = get_latest_signals()

# 頁面分頁排版
tab1, tab2 = st.tabs(["📊 實時監控", "📂 歷史成形回顧 & 2026 回測成效"])

with tab1:
    # 根據模式過濾
    if is_conservative_only:
        signals = [s for s in all_signals if s.get('is_conservative', False)]
        mode_text = "穩健型"
    else:
        signals = all_signals
        mode_text = "標準型"

    if not signals:
        if is_conservative_only:
            st.warning("🎯 目前無符合「穩健型」條件的標的。建議切換至「標準型」查看，或點擊左側重新掃描。")
        else:
            st.info("🎯 今日無符合條件之標的。")
    else:
        st.success(f"🔥 {mode_text}掃描完成！為您精選出 {len(signals)} 檔符合結構的標的！")
        
        triggered = [s for s in signals if s['status'] == 'Triggered']
        potential = [s for s in signals if s['status'] == 'Potential']
        
        # 排序
        potential = sorted(potential, key=lambda x: (x.get('rr_ratio', 0), x.get('upside_pct', 0)), reverse=True)
        
        # 1. 🎖️ 本日最優 5 檔伏擊標的
        if potential:
            st.markdown("## 🎖️ 本日最優 5 檔優化伏擊標的")
            top_5 = potential[:5]
            for stock in top_5:
                ticker = stock['ticker']
                name = stock.get('name', ticker)
                upside = stock.get('upside_pct', 0) * 100
                rr = stock.get('rr_ratio', 0)
                label = f"⭐ **{ticker} {name}** | 現價 **{stock.get('latest_close', 0):.2f}** | 預期報酬 **+{upside:.1f}%** | RR **{rr:.1f}**"
                with st.expander(label):
                    render_stock_details(stock)

        # 2. 🔥 已觸發進場帶 (Triggered)
        if triggered:
            st.markdown("## 🔥 已觸發進場帶 (Triggered)")
            for stock in triggered:
                ticker = stock['ticker']
                name = stock.get('name', ticker)
                upside = stock.get('upside_pct', 0) * 100
                rr = stock.get('rr_ratio', 0)
                label = f"🟢 **{ticker} {name}** | 現價 **{stock.get('latest_close', 0):.2f}** | 報酬 **+{upside:.1f}%** | RR **{rr:.1f}**"
                with st.expander(label):
                    render_stock_details(stock)

        # 3. ⏳ 其他潛在標的
        other_potential = potential[5:]
        if other_potential:
            st.markdown("## ⏳ 其他潛在伏擊標的 (Potential)")
            for stock in other_potential:
                ticker = stock['ticker']
                name = stock.get('name', ticker)
                upside = stock.get('upside_pct', 0) * 100
                rr = stock.get('rr_ratio', 0)
                label = f"🟡 **{ticker} {name}** | 現價 **{stock.get('latest_close', 0):.2f}** | 報酬 **+{upside:.1f}%** | RR **{rr:.1f}**"
                with st.expander(label):
                    render_stock_details(stock)

with tab2:
    st.markdown("### 📂 歷史成形標的回顧 & 2026 回測成效")
    
    # 🏆 策略評價區
    if is_conservative_only:
        st.success("🏆 **穩健型策略評價**：僅追蹤 EMA 斜率向上且盈虧比 > 1.2 的高品質信號。雖然交易頻率較低，但能有效過濾掉 2026 年初市場劇烈波動中的『結構假突破』案例，適合追求長期穩定成長的帳戶。")
    else:
        st.info("💡 **標準型策略評價**：全方位監控所有符合 SMC 結構與 Vegas 通道的標的。在強多頭市場中能捕捉到更多二、三線補漲標的，但需注意在市場修正式回檔中可能面臨較多止損。")

    history_file = 'data/triggered_records.json'
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
            if records:
                raw_df = pd.DataFrame(records)
                if is_conservative_only:
                    df_h = raw_df[raw_df['is_conservative'] == True].copy() if 'is_conservative' in raw_df.columns else pd.DataFrame()
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
                    st.warning("⚠️ 穩健模式下紀錄較少，請切換模式對比。")
            else: st.info("目前尚無紀錄。")
        except Exception as e: st.error(f"讀取紀錄出錯: {e}")
    else:
        st.info("歷史紀錄檔案尚未建立。")
