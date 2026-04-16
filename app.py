import streamlit as st
import json
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    import pytz # fallback
    
st.title("📈 全球期貨指標 SMC x Vegas 戰情室")
st.markdown("針對全球權重指數 (NQ, ES, YM, NKD, A50) 進行 SMC 聰明錢結構與 Vegas 通道分析。報價來源為 yfinance (約 15 分鐘延遲)。")

# 透過 Streamlit @st.cache_data 原生機制，實作即時掃描與 15 分鐘快取
@st.cache_data(ttl=900, show_spinner="🤖 正在分析全球期貨最新價格結構 (大約需要 15-20 秒)...")
def get_latest_futures_signals():
    try:
        data_fetcher.run_analysis()
        with open('data/signals.json', 'r') as f:
            return json.load(f)
    except:
        return []

signals = get_latest_futures_signals()

col_btn, _ = st.columns([1, 2])
with col_btn:
    if st.button("🔄 重新掃描"):
        st.cache_data.clear()
        st.rerun()

# 判斷是否為 Fallback
is_fallback_mode = False
if signals and signals[0].get('is_fallback'):
    is_fallback_mode = True

if signals:
    st.success(f"🔥 全球市場掃描完成！共發現 {len(signals)} 檔符合趨勢指標標的！")
else:
    st.info("目前無任何指標觸發，市場可能處於震盪或過於極端。")

display_stocks = signals

# 移除歷史資料載入邏輯

def render_dashboard(display_stocks, key_prefix):
    if not display_stocks:
        st.info("此日期無推薦標的。")
        return

    col1, col2 = st.columns([1, 2])

    session_key = f'selected_ticker_{key_prefix}'
    if session_key not in st.session_state:
        st.session_state[session_key] = display_stocks[0]['ticker'] if display_stocks else None

    with col1:
        st.subheader("📋 指標訊號清單")
            
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
        
        # IC 評分呈現邏輯
        ic_val = stock.get('current_ic', 0)
        ic_color = "#34d399" if ic_val >= 0.05 else ("#f87171" if ic_val <= -0.05 else "#94a3b8")
        ic_text = f"{ic_val:+.3f}"
        ic_html = f'<div style="background: rgba(255,255,255,0.05); padding: 4px 12px; border-radius: 6px; display: inline-flex; align-items: center; gap: 8px;"><span style="color: #94a3b8; font-size: 12px;">當前預測勝率 (IC)</span><span style="color: {ic_color}; font-weight: 700; font-size: 14px;">{ic_text}</span></div>'

        html = f'<div class="stock-card"><h2 style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 0;"><span style="color:#60a5fa;">{ticker}</span><span>{c_name}</span>{sector_html}</h2><div style="margin-bottom: 16px;">{ic_html}</div><div class="metric-row"><div class="metric"><span class="metric-label">建議進場區間</span><span class="metric-value buy-zone">{entry}</span></div><div class="metric"><span class="metric-label">潛在報酬空間</span><span class="metric-value potential">+{upside:.1f}%</span></div></div><div class="metric-row"><div class="metric"><span class="metric-label">停利目標(BSL)</span><span class="metric-value target-price">{target_str}</span></div><div class="metric"><span class="metric-label">防守停損(OB Low)</span><span class="metric-value stop-loss">{sl_str}</span></div></div>{desc_html}</div>'
        
        if stock.get('is_fallback') and stock.get('fallback_reason'):
            reason = stock['fallback_reason']
            html += f'<div style="margin-top: 16px; padding: 12px; background: rgba(245, 158, 11, 0.1); border-left: 4px solid #f59e0b; border-radius: 4px;"><span style="color: #fbbf24; font-size: 13px; font-weight: 600;">💡 推薦原因</span><div style="color: #d1d5db; font-size: 13px; margin-top: 4px; line-height: 1.5;">{reason}</div></div>'
            
        html += "</div>"
        
        st.markdown(html, unsafe_allow_html=True)
        # 取代危險的 JS onclick，使用完美原生的 Streamlit button
        if st.button(f"📊 載入 {ticker} 走勢圖", key=f"btn_{ticker}_{key_prefix}", use_container_width=True):
            st.session_state[session_key] = ticker
            st.rerun()

    with col2:
        selected = st.session_state[session_key]
        if selected:
            st.subheader(f"📊 {selected} 價格動態與 SMC 結構")
        
        stock_data = next((s for s in display_stocks if s['ticker'] == selected), None)
        
        with st.spinner("繪製 K 線圖中..."):
            df = yf.download(selected, period="1y", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df.dropna(subset=['Close'], inplace=True)
            
            close_s = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
            df['EMA_144'] = close_s.ewm(span=144, adjust=False).mean()
            df['EMA_169'] = close_s.ewm(span=169, adjust=False).mean()
            df['EMA_576'] = close_s.ewm(span=576, adjust=False).mean()
            df['EMA_676'] = close_s.ewm(span=676, adjust=False).mean()

            # --- Rank IC Calculation ---
            df['Future_Return'] = close_s.shift(-5) / close_s - 1
            df['Vegas_Strength'] = (df['EMA_144'] - df['EMA_576']) / df['EMA_576']
            # pandas rolling.corr() 不支援 method='spearman'，在此改用有效率的原生 Pearson IC 取代 Time-series Rank IC
            rolling_ic = df['Vegas_Strength'].rolling(window=60).corr(df['Future_Return'])
            df['Rolling_Rank_IC'] = rolling_ic.fillna(0) # 避免圖表報錯

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.03, row_heights=[0.75, 0.25])

            # 確保提取為 1D Series 避免 yfinance 回傳多重欄位 DataFrame 導致 Plotly 繪圖失敗
            open_s = df['Open'].iloc[:, 0] if isinstance(df['Open'], pd.DataFrame) else df['Open']
            high_s = df['High'].iloc[:, 0] if isinstance(df['High'], pd.DataFrame) else df['High']
            low_s = df['Low'].iloc[:, 0] if isinstance(df['Low'], pd.DataFrame) else df['Low']

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df.index, open=open_s, high=high_s, low=low_s, close=close_s,
                name='價格', increasing_line_color='#22c55e', decreasing_line_color='#ef4444'
            ), row=1, col=1)

            # EMAs
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_144'], mode='lines', name='EMA 144', line=dict(color='#fcd34d', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_169'], mode='lines', name='EMA 169', line=dict(color='#fbbf24', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_576'], mode='lines', name='EMA 576', line=dict(color='#a78bfa', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_676'], mode='lines', name='EMA 676', line=dict(color='#8b5cf6', width=1.5)), row=1, col=1)

            # Rank IC Bar Chart
            ic_colors = ['#22c55e' if val >= 0 else '#ef4444' for val in df['Rolling_Rank_IC']]
            fig.add_trace(go.Bar(
                x=df.index, y=df['Rolling_Rank_IC'], name='Rank IC (5日勝率)',
                marker_color=ic_colors, opacity=0.8
            ), row=2, col=1)
            fig.add_hline(y=0.05, line_dash="dash", line_color="rgba(34,197,94,0.5)", row=2, col=1)
            fig.add_hline(y=-0.05, line_dash="dash", line_color="rgba(239,68,68,0.5)", row=2, col=1)

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
                    fig.add_hline(y=stock_data['target1'], line_dash="dash", line_color="#cbd5e1", annotation_text="Target 1 (BSL)", row=1, col=1)
                if stock_data.get('target2'):
                    fig.add_hline(y=stock_data['target2'], line_dash="dash", line_color="#bae6fd", annotation_text="Target 2 (EQH)", row=1, col=1)

            fig.update_layout(
                template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis_rangeslider_visible=False, xaxis2_rangeslider_visible=False,
                margin=dict(l=0, r=0, t=30, b=0),
                hovermode='x unified', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            st.plotly_chart(fig, use_container_width=True)

            st.plotly_chart(fig, use_container_width=True)

# 直接呼叫渲染儀表板佈局
render_dashboard(signals, "main")
