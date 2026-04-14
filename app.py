import streamlit as st
import json
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import data_fetcher
import threading

# 頁面配置
st.set_page_config(page_title="台股 SMC x Vegas 量化監控系統", layout="wide", page_icon="📈")

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
st.title("📈 台股 SMC x Vegas 百大流動性股全掃描")
st.markdown("每日 08:30 自動運算，從台股市值前 150 大流動性優勢標的，精選符合 **長線多頭 (Vegas)** 與 **價格回測支撐區 (SMC OB+FVG)** 的 **Top 5 強勢股**。")

# 透過 Streamlit 原生方式執行首次資料讀取，避免畫面死亡
@st.cache_data(ttl=60*60)
def fetch_signals_or_run():
    if not os.path.exists('data/signals.json'):
        return None
    try:
        with open('data/signals.json', 'r') as f:
            return json.load(f)
    except:
        return None

signals = fetch_signals_or_run()

if signals is None:
    st.info("系統尚未建立最新的熱門股掃描訊號。請點擊上方按鈕首次初始化資料。")
    if st.button("🚀 啟動全市場初始掃描 (預計 20-30 秒)"):
        with st.spinner("正在使用 yfinance 多執行緒並行掃描前 150 大台股歷史資料..."):
            data_fetcher.run_analysis()
            st.cache_data.clear()
            st.success("分析完成！")
            st.rerun()
    st.stop()
else:
    # 新增一個手動更新按鈕
    if st.button("🔄 重新掃描最新市場行情"):
        with st.spinner("正在並行掃描前 150 大台股..."):
            data_fetcher.run_analysis()
            st.cache_data.clear()
            st.rerun()

# 判斷是否為 Fallback
is_fallback_mode = False
if signals and signals[0].get('is_fallback'):
    is_fallback_mode = True

if is_fallback_mode:
    st.warning(f"⚠️ 今日無完美觸發進場標的，系統啟動備用機制，推薦 {len(signals)} 檔【潛力觀察名單】供參：")
else:
    if not signals:
        st.info("今日無任何標的觸發信號。")
    else:
        st.success(f"🔥 今日掃描完成！為您精選出 {len(signals)} 檔最強勢潛力標的！")

display_stocks = signals

# 頁面排版
col1, col2 = st.columns([1, 2])

# 初始化選股狀態
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = display_stocks[0]['ticker'] if display_stocks else None

with col1:
    st.subheader("📋 每日 Top 5 強勢股清單")
    for stock in display_stocks:
        ticker = stock['ticker']
        entry = stock.get('entry_zone') or "未成型"
        sl = stock.get('stop_loss') or 0
        target = stock.get('target1') or 0
        upside = stock.get('upside_pct', 0) * 100
        
        sl_str = f"NT$ {sl:.2f}" if sl else "-"
        target_str = f"NT$ {target:.2f}" if target else "-"
        
        c_name = stock.get('company_name', '').replace('\n', ' ').replace('\r', '')
        sector = stock.get('sector', '').replace('\n', ' ').replace('\r', '')
        desc = stock.get('description', '').replace('\n', ' ').replace('\r', '')
        
        desc_html = f'<div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.1);"><div style="color: #94a3b8; font-size: 12px; margin-bottom: 4px; letter-spacing: 0.05em;">主要經營業務</div><div style="color: #cbd5e1; font-size: 13px; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis;" title="{desc}">{desc}</div></div>' if desc and desc != '無' else ''
        sector_html = f'<span style="font-size: 13px; font-weight: normal; background: #334155; padding: 2px 8px; border-radius: 12px; color: #cbd5e1;">{sector}</span>' if sector and sector != '未知' else ''
        html = f'<div class="stock-card"><h2 style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 0;"><span style="color:#60a5fa;">{ticker}</span><span>{c_name}</span>{sector_html}</h2><div class="metric-row"><div class="metric"><span class="metric-label">建議進場區間</span><span class="metric-value buy-zone">{entry}</span></div><div class="metric"><span class="metric-label">潛在報酬空間</span><span class="metric-value potential">+{upside:.1f}%</span></div></div><div class="metric-row"><div class="metric"><span class="metric-label">停利目標(BSL)</span><span class="metric-value target-price">{target_str}</span></div><div class="metric"><span class="metric-label">防守停損(OB Low)</span><span class="metric-value stop-loss">{sl_str}</span></div></div>{desc_html}</div>'
        
        if stock.get('is_fallback') and stock.get('fallback_reason'):
            reason = stock['fallback_reason']
            html += f'<div style="margin-top: 16px; padding: 12px; background: rgba(245, 158, 11, 0.1); border-left: 4px solid #f59e0b; border-radius: 4px;"><span style="color: #fbbf24; font-size: 13px; font-weight: 600;">💡 推薦原因</span><div style="color: #d1d5db; font-size: 13px; margin-top: 4px; line-height: 1.5;">{reason}</div></div>'
            
        html += "</div>"
        
        st.markdown(html, unsafe_allow_html=True)
        # 取代危險的 JS onclick，使用完美原生的 Streamlit button
        if st.button(f"📊 載入 {ticker} 走勢圖", key=f"btn_{ticker}", use_container_width=True):
            st.session_state.selected_ticker = ticker
            st.rerun()

with col2:
    selected = st.session_state.selected_ticker
    if selected:
        st.subheader(f"📊 {selected} 價格動態與 SMC 結構")
        
        stock_data = next((s for s in display_stocks if s['ticker'] == selected), None)
        
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

            # 確保提取為 1D Series 避免 yfinance 回傳多重欄位 DataFrame 導致 Plotly 繪圖失敗
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
                if stock_data.get('target2'):
                    fig.add_hline(y=stock_data['target2'], line_dash="dash", line_color="#bae6fd", annotation_text="Target 2 (EQH)")

            fig.update_layout(
                template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=30, b=0),
                hovermode='x unified', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            st.plotly_chart(fig, use_container_width=True)
