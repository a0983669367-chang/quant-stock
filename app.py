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
    
st.title("📈 台股 SMC x Vegas 百大流動性股全掃描")
st.markdown("每日 08:30 自動運算，從台股市值前 150 大流動性優勢標的，精選符合 **長線多頭 (Vegas)** 與 **價格回測支撐區 (SMC OB+FVG)** 的 **Top 5 強勢股**。")

def get_cutoff_key():
    """ 取得台灣時間每日 08:30 為界線的快取 Key """
    try:
        tw_tz = ZoneInfo("Asia/Taipei")
    except:
        import pytz
        tw_tz = pytz.timezone("Asia/Taipei")
        
    now_tw = datetime.datetime.now(tw_tz)
    cutoff = now_tw.replace(hour=8, minute=30, second=0, microsecond=0)
    if now_tw < cutoff:
        cutoff -= datetime.timedelta(days=1)
    return cutoff.strftime("%Y%m%d")

# 透過 Streamlit @st.cache_data 原生機制，只要 cutoff_key 變了（跨過每日 08:30），就會自動強制重新掃描！
@st.cache_data(show_spinner="🤖 系統偵測到已超過每日 08:30，正在進行智慧全市場掃描 (約需 20-30 秒)...")
def get_latest_signals(cutoff_key):
    try:
        data_fetcher.run_analysis()
        with open('data/signals.json', 'r') as f:
            return json.load(f)
    except:
        return []

cutoff_date_key = get_cutoff_key()
signals = get_latest_signals(cutoff_date_key)

col_btn, _ = st.columns([1, 2])
with col_btn:
    if st.button("🔄 重新掃描"):
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
        st.info("目前無任何標的觸發信號。")
    else:
        st.success(f"🔥 最新掃描完成！為您精選出 {len(signals)} 檔最強勢潛力標的！")

display_stocks = signals

# 讀取歷史資料
history_data = {}
if os.path.exists('data/history.json'):
    try:
        with open('data/history.json', 'r') as f:
            history_data = json.load(f)
    except:
        pass

def render_dashboard(display_stocks, key_prefix):
    if not display_stocks:
        st.info("此日期無推薦標的。")
        return

    col1, col2 = st.columns([1, 2])

    session_key = f'selected_ticker_{key_prefix}'
    if session_key not in st.session_state:
        st.session_state[session_key] = display_stocks[0]['ticker'] if display_stocks else None

    with col1:
        st.subheader("📋 強勢股清單")
        
        # 準備 Excel (CSV) 匯出資料
        try:
            df_export = pd.DataFrame(display_stocks)
            rename_map = {
                'ticker': '股票代號', 'company_name': '公司名稱', 'sector': '產業',
                'entry_zone': '進場區間', 'stop_loss': '停損價', 'target1': '理想停利價',
                'upside_pct': '潛在報酬率', 'description': '業務說明'
            }
            df_export = df_export.rename(columns=rename_map)
            export_cols = [v for k, v in rename_map.items()]
            available_cols = [c for c in export_cols if c in df_export.columns]
            
            # 將字串手動編碼為 utf-8-sig bytes，避免 Streamlit 輸出預設無 BOM 的 UTF-8 導致 Windows 亂碼
            csv_string = df_export[available_cols].to_csv(index=False)
            csv_bytes = csv_string.encode('utf-8-sig')
            
            st.download_button(
                label="⬇️ 匯出此名單至 Excel (CSV檔)",
                data=csv_bytes,
                file_name=f"SMC_選股名單_{key_prefix}.csv",
                mime="text/csv"
            )
        except Exception as e:
            pass
            
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

# 頁面排版：標籤頁
tab_main, tab_history = st.tabs(["🔥 今日最新推薦", "📚 歷史回顧寶庫"])

with tab_main:
    render_dashboard(signals, "main")

with tab_history:
    if not history_data:
        st.info("目前尚無歷史紀錄。請先執行過幾次掃描後再來查看！")
    else:
        # 取得所有可用日期，最新日期排最前
        available_dates = sorted(list(history_data.keys()), reverse=True)
        selected_date = st.selectbox("📅 選擇歷史日期", available_dates)
        
        if selected_date:
            st.markdown(f"### {selected_date} 選股回顧")
            history_signals = history_data[selected_date]
            render_dashboard(history_signals, f"hist_{selected_date}")
