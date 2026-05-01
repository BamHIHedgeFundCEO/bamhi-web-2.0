"""
views/sector_rotation.py
BamHI 交易工具：板塊輪動與 VCP 監控系統
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# 匯入後端大腦
from data_engine.market.sector_engine import calculate_sector_metrics, scan_vcp_candidates

# ==========================================
# 📁 CEO 專屬：寫死在程式裡的追蹤板塊清單
# 只要在這裡新增 "板塊名稱": ["代碼1", "代碼2"...]，網頁選單就會自動擴充！
# ==========================================
TRACKED_SECTORS = {
    "太空概念股 (Space)": ["RKLB", "PL", "LUNR", "ASTS", "RDW","SATS", "VSAT", "FLY", "MDA", "IRDM","YSS","VOYG","SPIR","BKSY","SPCE","TSAT"],
    "存儲記憶體 (Storage)": ["MU", "WDC", "STX", "NTAP","SNDK","RMBS","SIMO"],
    "AI 伺服器 (AI Server)": ["SMCI", "DELL", "HPE", "VRT"],
    "散熱與液冷 (Cooling)": ["MOD", "VERT", "NVT"],
    "AI 晶片與軟體 (Chip & Software)": ["NVDA", "AVGO", "ADBE", "AMD", "INTC", "ORCL", "GOOGL", "META", "AMZN"],
    "稀土與戰略金屬 (Rare Earths)": ["MP", "UUUU", "AREC", "CRML", "NB", "TMC", "IDR", "PPTA", "CLF", "UAMY", "USAR"],
    "光通訊 (Optical Communication)": ["GLW", "LITE", "COHR", "FN", "AAOI", "POET", "MRVL", "CRDO", "ALAB", "ANET", "AVGO", "CIEN", "VIAV", "CLFD", "NOK", "LUMN", "APH"],
    "鈾礦 (Uranium)": ["CCJ", "UEC", "UUUU", "LEU", "ISOU", "UROY", "NXE", "URG", "DNN", "EU", "SMR", "OKLO", "NNE", "BWXT", "AEC", "NUCL", "JAGU"],
    "核電與核能技術 (Nuclear Power)": ["OKLO", "UEC", "UUUU", "SMR", "LEU", "CCJ", "NXE", "TLN", "ETN", "CEG", "GHM", "NNE", "KEP", "BWXT", "NEE", "SO", "D", "EMR", "ETR", "VST", "PEG", "DUK", "RWEOY", "XE", "HON", "GEV", "EXC", "PPL"]
}

def render_sector_rotation():
    st.title("🔄 BamHI 板塊輪動與資金流向監控")
    st.markdown("結合 5D/20D 動能加速、RS 相對強度與 VCP 籌碼掃描，鎖定市場最強主線。")
    
    # === 0. 全局控制面板 ===
    st.markdown("### ⚙️ 系統參數設定")
    
    # 初始化 Session State
    if "sector_selectbox_ui" not in st.session_state:
        st.session_state.sector_selectbox_ui = list(TRACKED_SECTORS.keys())[0]
        
    # 如果有來自熱力圖的跳轉請求，在渲染 Selectbox 之前先更新它的 key
    if "next_sector" in st.session_state:
        st.session_state.sector_selectbox_ui = st.session_state.next_sector
        del st.session_state.next_sector
        
    col_opt1, col_opt2, col_opt3 = st.columns([2, 2, 3])
    
    with col_opt1:
        sector_name = st.selectbox(
            "📂 選擇深度掃描板塊", 
            options=list(TRACKED_SECTORS.keys()),
            key="sector_selectbox_ui"
        )
        
    with col_opt2:
        period_opt = st.selectbox("📅 歷史區間", ["6mo", "1y", "2y", "5y", "10y", "max"], index=2, key="sector_period")
        
    with col_opt3:
        search_ticker = st.text_input("🔍 快速個股透視 (輸入代碼)", placeholder="例如: RKLB").upper()
        if search_ticker:
            target_url = f"/?search_query={search_ticker}"
            st.markdown(f"""
                <a href="{target_url}" target="_self">
                    <button style="width:100%; border-radius:5px; background-color:#FF4B4B; color:white; border:none; padding:7px; cursor:pointer;">
                        🚀 深度分析 {search_ticker}
                    </button>
                </a>
            """, unsafe_allow_html=True)
            
    # 根據選到的板塊名稱，抓出對應的股票代碼清單
    tickers = TRACKED_SECTORS[sector_name]
    st.caption(f"**追蹤清單:** {', '.join(tickers)}")
    st.markdown("---")

    # === 0. 板塊動能熱力圖 (全覽) ===
    st.subheader("🗺️ 板塊動能熱力圖 (Sector Momentum Heatmap)")
    with st.spinner("正在計算各板塊動能差值以繪製熱力圖..."):
        heatmap_data = []
        for s_name, s_tickers in TRACKED_SECTORS.items():
            df_sec, _ = calculate_sector_metrics(s_tickers, period=period_opt)
            if df_sec is not None and not df_sec.empty:
                diff = df_sec.iloc[-1]['Momentum_Diff']
                heatmap_data.append({"Sector": s_name, "Momentum_Diff": round(diff, 2), "Size": 1})
        
        if heatmap_data:
            df_heat = pd.DataFrame(heatmap_data)
            fig_heat = px.treemap(
                df_heat, 
                path=[px.Constant("所有追蹤板塊"), 'Sector'], 
                values='Size',
                color='Momentum_Diff', 
                color_continuous_scale='RdYlGn',
                color_continuous_midpoint=0,
                custom_data=['Momentum_Diff']
            )
            fig_heat.update_traces(
                hovertemplate="<b>%{label}</b><br>動能差值 (M5 - M20): %{customdata[0]:.2f}%<extra></extra>",
                texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%",
                textposition="middle center",
                textfont=dict(size=18)
            )
            # Try using Streamlit 1.35+ on_select feature to link chart clicks to the selectbox
            try:
                event = st.plotly_chart(
                    fig_heat, 
                    use_container_width=True, 
                    on_select="rerun",
                    selection_mode="points"
                )
                
                # 解析點擊事件
                if event and "selection" in event and "points" in event["selection"]:
                    points = event["selection"]["points"]
                    if points:
                        clicked_sector = points[0].get("label", "")
                        if clicked_sector in TRACKED_SECTORS and st.session_state.get("sector_selectbox_ui") != clicked_sector:
                            st.session_state.next_sector = clicked_sector
                            st.rerun()
            except TypeError:
                # 舊版 Streamlit 不支援 on_select 的降級處理
                st.plotly_chart(fig_heat, use_container_width=True)
                st.info("💡 提示：點擊熱力圖會進行縮放。若要查看特定板塊的詳細疊圖與 VCP 數據，請從左側【側邊欄】選單切換！")

    # === 主畫面：單一板塊數據視覺化 ===
    if tickers:
        with st.spinner(f"正在計算 {sector_name} 詳細動能與 VCP 訊號..."):
            df_sector, vol_data = calculate_sector_metrics(tickers, period=period_opt)
            
            if df_sector is None or df_sector.empty:
                st.error("資料獲取失敗，請檢查該板塊內的 Ticker 是否正確或已下市。")
                return

            latest = df_sector.iloc[-1]
            
            # --- 1. 頂部儀表板 ---
            st.subheader(f"🔥 {sector_name} 資金動能與擁擠度概況")
            
            # 計算今日漲跌幅
            today_close = df_sector['Sector_Close'].iloc[-1]
            yest_close = df_sector['Sector_Close'].iloc[-2]
            daily_pct = ((today_close - yest_close) / yest_close) * 100
            
            # 🌟 把欄位改成 7 欄，加入今日漲跌幅
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            col1.metric("今日漲跌幅", f"{daily_pct:.2f}%", delta=f"{daily_pct:.2f}%", delta_color="normal" if daily_pct > 0 else "inverse")
            col2.metric("5日極速動能", f"{latest['M5']:.2f}%")
            col3.metric("10日波段動能", f"{latest['M10']:.2f}%")
            col4.metric("20日中線動能", f"{latest['M20']:.2f}%")
            
            # 動能差值 (M5 vs M20)
            diff = latest['Momentum_Diff']
            diff_color = "normal" if diff > 0 else "inverse"
            col5.metric("動能差值 (M5-M20)", f"{diff:.2f}%", delta_color=diff_color)
            
            # RS 斜率
            rs_slope = latest['RS_Slope']
            col6.metric("RS 線 5日斜率", f"{rs_slope:.4f}", delta="向上" if rs_slope > 0 else "向下", delta_color="normal" if rs_slope > 0 else "inverse")
            
            # 🌟 新增：擁擠度雷達
            crowd_ratio = latest['Crowdedness'] * 100
            crowd_90p = latest['Crowdedness_90p'] * 100
            is_overheated = crowd_ratio >= crowd_90p
            
            col7.metric(
                "板塊資金擁擠度", 
                f"{crowd_ratio:.2f}%", 
                delta="⚠️ 達 90% 過熱水位" if is_overheated else "✅ 水位正常", 
                delta_color="inverse" if is_overheated else "normal"
            )
            
            # 💡 判斷進出場狀態與防護罩警報 (升級為 M5 > M10 > M20 動能共振)
            st.markdown("<br>", unsafe_allow_html=True)
            if is_overheated:
                st.error(f"🚨 **【擁擠度防護罩觸發】** 該板塊成交金額佔比 ({crowd_ratio:.2f}%) 已突破過去一年 90% 絕對高位 ({crowd_90p:.2f}%)。散戶情緒極度擁擠，隨時可能面臨大戶派發反轉，請嚴格執行減碼紀律！")
            elif latest['M5'] > latest['M10'] and latest['M10'] > latest['M20'] and rs_slope > 0:
                st.success("🟢 **【極致動能共振】** M5 > M10 > M20 多頭排列，短、中線熱錢同步加速流入，且籌碼尚未過熱！")
            elif latest['M5'] > latest['M20'] and rs_slope > 0:
                st.info("🔵 **【初步進場訊號】** 短線動能穿越中線，板塊轉強，可開始觀察下方 VCP 標的。")
            elif latest['M5'] < latest['M10']:
                st.warning("🟡 **【動能衰減】** 短線動能 (M5) 已落後波段動能 (M10)，追價力道減弱，不建議積極建倉。")

            # --- 2. 板塊 K 線圖 (自定義指數 OHLC) ---
            st.markdown("---")
            st.subheader(f"📊 {sector_name} 專屬 K 線圖 (自定義指數)")
            
            fig_k = go.Figure()
            
            # K線
            fig_k.add_trace(go.Candlestick(
                x=df_sector.index,
                open=df_sector['Sector_Open'],
                high=df_sector['Sector_High'],
                low=df_sector['Sector_Low'],
                close=df_sector['Sector_Close'],
                name="指數 K 線"
            ))
            
            # 均線
            colors = {'MA10': 'orange', 'MA20': 'yellow', 'MA60': 'red', 'MA120': 'purple', 'MA200': 'cyan'}
            for ma_name, color in colors.items():
                fig_k.add_trace(go.Scatter(
                    x=df_sector.index, y=df_sector[ma_name],
                    line=dict(color=color, width=1.5), name=ma_name
                ))
            
            fig_k.update_layout(
                height=550, margin=dict(l=0, r=0, t=30, b=0),
                xaxis_rangeslider_visible=False,
                hovermode="x unified",
                yaxis_title="板塊指數 (基準 100)"
            )
            st.plotly_chart(fig_k, use_container_width=True)

            # --- 3. 疊圖分析 (自製指數 vs SPY + RS Line) ---
            st.markdown("---")
            st.subheader("📈 相對強度分析 (Relative Strength)")
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.1, row_heights=[0.7, 0.3])
            
            fig.add_trace(go.Scatter(x=df_sector.index, y=df_sector['Sector_Index'], name=f"{sector_name} 指數", line=dict(color='blue', width=2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_sector.index, y=df_sector['SPY_Index'], name="SPY 指數", line=dict(color='gray', width=1.5, dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_sector.index, y=df_sector['RS_Line'], name="RS Line", line=dict(color='green', width=2)), row=2, col=1)
            
            fig.update_layout(height=600, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            # --- 3. VCP 個股掃描器 (包含超連結跳轉) ---
            st.markdown("---")
            st.subheader(f"🎯 {sector_name} 內部 VCP 掃描器")
            st.markdown("尋找趨勢向上且出現**波動收縮**與**成交量枯竭**的標的。")
            
            df_vcp = scan_vcp_candidates(tickers, period=period_opt)
            
            if not df_vcp.empty:
                df_vcp['Action'] = "/?search_query=" + df_vcp['Ticker']
                df_vcp = df_vcp[['Ticker', 'Price', 'Dist_to_High', 'Trend_Pass', 'ATR', 'Vol_Dry_Up', 'Action']]
                
                st.dataframe(
                    df_vcp,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Ticker": st.column_config.TextColumn("代碼", width="small"),
                        "Price": st.column_config.NumberColumn("收盤價", format="$%.2f"),
                        "Dist_to_High": st.column_config.TextColumn("距52W新高"),
                        "Trend_Pass": st.column_config.TextColumn("符合趨勢"),
                        "ATR": st.column_config.NumberColumn("近期 ATR"),
                        "Vol_Dry_Up": st.column_config.TextColumn("量能枯竭"),
                        "Action": st.column_config.LinkColumn("深度透視", display_text="🔍 前往系統分析", width="medium")
                    }
                )
            else:
                st.info("目前板塊內無完全符合 VCP 嚴格條件的標的。")
