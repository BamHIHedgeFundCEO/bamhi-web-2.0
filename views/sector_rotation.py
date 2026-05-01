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
    "AI 應用軟體 (AI Apps)": ["ADBE", "ADP", "AI", "APP", "APPS", "ASAN", "BRZE", "CLBT", "CRM", "CVLT", "DDOG", "DOCS", "DOCU", "DUOL", "ESTC", "FIG", "FSLY", "GTLB", "GWRE", "HUBS", "INTU", "IOT", "KVYO", "LIF", "MDB", "MNDY", "NET", "NOW", "PATH", "PCOR", "PINS", "PLTR", "RBLX", "RBRK", "RDDT", "SAP", "SHOP", "SNAP", "SNOW", "SOUN", "SPOT", "TEAM", "TEM", "TTD", "TWLO", "U", "VEEV", "ZETA", "ZM"],
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
                "資金佔大盤均量比例", 
                f"{crowd_ratio:.2f}%", 
                delta="⚠️ 達 90% 過熱水位" if is_overheated else "✅ 水位正常", 
                delta_color="inverse" if is_overheated else "normal"
            )
            
            # 💡 判斷進出場狀態與防護罩警報
            close_val = latest['Sector_Close']
            ma20_val = latest['MA20']
            ma60_val = latest['MA60']
            
            st.markdown("<br>", unsafe_allow_html=True)
            if is_overheated:
                st.error(f"🚨 **【擁擠度防護罩觸發】** 該板塊資金佔大盤均量比例 ({crowd_ratio:.2f}%) 已突破過去一年 90% 絕對高位 ({crowd_90p:.2f}%)。散戶情緒極度擁擠，隨時可能面臨大戶派發反轉，請嚴格執行減碼紀律，切勿盲目追高！")
            elif close_val < ma20_val:
                st.warning(f"🔴 **【空頭弱勢 / 跌破月線】** 指數跌破 20 日均線 ({close_val:.2f} < {ma20_val:.2f})，板塊處於回檔或空頭格局，建議觀望，等待突破壓力或 VCP 右側收縮完成。")
            elif close_val > ma20_val and ma20_val > ma60_val and rs_slope > 0 and latest['M5'] > 0:
                st.success("🟢 **【強勢多頭排列】** 價格站上月線與季線 (Close > MA20 > MA60)，且相對強度 (RS) 向上發散。板塊處於主升段，是尋找 VCP 突破與順勢建倉的最佳時機！")
            elif close_val > ma20_val and rs_slope > 0:
                st.info("🔵 **【初步轉強訊號】** 指數剛站上 20 日均線且 RS 開始向上翻轉，板塊有落底回升跡象。可開始把注意力放在下方掃描出的 VCP 潛力股。")
            else:
                st.warning("🟡 **【動能衰減 / 整理區間】** 指數雖在月線之上，但短線動能減弱或 RS 呈現下滑，板塊可能正在進行橫盤消化或面臨獲利了結賣壓。")

            # --- 2. 綜合圖表 (K線 + 相對強度) ---
            st.markdown("---")
            col_rs1, col_rs2 = st.columns([3, 1])
            with col_rs1:
                st.subheader(f"📊 {sector_name} 綜合圖表 (K線 + 相對強度)")
            with col_rs2:
                use_log_scale = st.checkbox("開啟對數座標 (Log Scale)", value=True, help="當板塊漲幅極大 (如鈾礦) 時，線性座標會壓縮波動。開啟對數座標能還原真實的漲跌百分比比例！")
            
            # 建立三層子圖 (K線, 疊圖, RS Line)，開啟 shared_xaxes 讓 X 軸連動對齊
            fig = make_subplots(
                rows=3, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.5, 0.3, 0.2]
            )
            
            # --- Row 1: K線與均線 ---
            fig.add_trace(go.Candlestick(
                x=df_sector.index,
                open=df_sector['Sector_Open'],
                high=df_sector['Sector_High'],
                low=df_sector['Sector_Low'],
                close=df_sector['Sector_Close'],
                name="指數 K 線"
            ), row=1, col=1)
            
            colors = {'MA10': 'orange', 'MA20': 'yellow', 'MA60': 'red', 'MA120': 'purple', 'MA200': 'cyan'}
            for ma_name, color in colors.items():
                fig.add_trace(go.Scatter(
                    x=df_sector.index, y=df_sector[ma_name],
                    line=dict(color=color, width=1.5), name=ma_name
                ), row=1, col=1)
                
            # --- Row 2: 疊圖分析 (Sector vs SPY) ---
            fig.add_trace(go.Scatter(x=df_sector.index, y=df_sector['Sector_Index'], name=f"{sector_name} 指數", line=dict(color='blue', width=2)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_sector.index, y=df_sector['SPY_Index'], name="SPY 指數", line=dict(color='gray', width=1.5, dash='dot')), row=2, col=1)
            
            # --- Row 3: RS Line ---
            fig.add_trace(go.Scatter(x=df_sector.index, y=df_sector['RS_Line'], name="RS Line", line=dict(color='green', width=2)), row=3, col=1)
            
            fig.add_hline(
                y=1.0,
                line_dash="dot",
                line_color="rgba(255,255,255,0.3)",
                annotation_text="RS 基準 (= SPY)",
                annotation_position="bottom right",
                row=3, col=1
            )
            
            if use_log_scale:
                fig.update_yaxes(type="log", row=1, col=1)
                fig.update_yaxes(type="log", row=2, col=1)
            
            fig.update_layout(
                height=900, margin=dict(l=0, r=0, t=30, b=0),
                xaxis_rangeslider_visible=False,
                xaxis3_rangeslider_visible=False,  # 隱藏 Candlestick 預設的 rangeslider
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # --- 3. VCP 個股掃描器 (包含超連結跳轉) ---
            st.markdown("---")
            st.subheader(f"🎯 {sector_name} 內部 VCP 掃描器")
            st.markdown("尋找趨勢向上且出現**波動收縮**與**成交量枯竭**的標的。")
            
            df_vcp = scan_vcp_candidates(tickers, period=period_opt)
            
            if not df_vcp.empty:
                df_vcp['Action'] = "/?search_query=" + df_vcp['Ticker']
                
                # 幫漲跌幅加上直觀的顏色標籤與符號
                def format_pct(val):
                    if pd.isna(val): return "-"
                    color = "🟢 " if val > 0 else "🔴 " if val < 0 else "⚪ "
                    return f"{color}{val:+.2f}%"
                
                df_vcp['M1_Fmt'] = df_vcp['M1'].apply(format_pct)
                df_vcp['M10_Fmt'] = df_vcp['M10'].apply(format_pct)
                df_vcp['M20_Fmt'] = df_vcp['M20'].apply(format_pct)
                df_vcp['M60_Fmt'] = df_vcp['M60'].apply(format_pct)
                df_vcp['Dist_MA20_Fmt'] = df_vcp['Dist_MA20'].apply(format_pct)
                df_vcp['RS_3M_Fmt'] = df_vcp['RS_3M'].apply(format_pct)
                
                # ATR 收縮與吃貨量比格式化
                df_vcp['ATR_Contraction_Fmt'] = df_vcp['ATR_Contraction'].apply(lambda x: f"🔥 {x:.2f}" if x < 0.6 else f"{x:.2f}")
                df_vcp['Up_Down_Vol_Fmt'] = df_vcp['Up_Down_Vol'].apply(lambda x: f"🐳 {x:.2f}" if x > 1.2 else f"{x:.2f}")
                
                df_vcp = df_vcp[['Ticker', 'Price', 'M1_Fmt', 'M10_Fmt', 'M20_Fmt', 'M60_Fmt', 'Dist_MA20_Fmt', 'RS_3M_Fmt', 'ATR_Contraction_Fmt', 'Up_Down_Vol_Fmt', 'Dist_to_High', 'Trend_Pass', 'Vol_Dry_Up', 'Action']]
                
                st.dataframe(
                    df_vcp,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Ticker": st.column_config.TextColumn("代碼", width="small"),
                        "Price": st.column_config.NumberColumn("收盤價", format="$%.2f"),
                        "M1_Fmt": st.column_config.TextColumn("日漲跌幅"),
                        "M10_Fmt": st.column_config.TextColumn("累積10日"),
                        "M20_Fmt": st.column_config.TextColumn("累積20日"),
                        "M60_Fmt": st.column_config.TextColumn("累積60日"),
                        "Dist_MA20_Fmt": st.column_config.TextColumn("月線乖離"),
                        "RS_3M_Fmt": st.column_config.TextColumn("RS 3M"),
                        "ATR_Contraction_Fmt": st.column_config.TextColumn("波動收縮比"),
                        "Up_Down_Vol_Fmt": st.column_config.TextColumn("吃貨量比"),
                        "Dist_to_High": st.column_config.TextColumn("距52W高"),
                        "Trend_Pass": st.column_config.TextColumn("多頭趨勢"),
                        "Vol_Dry_Up": st.column_config.TextColumn("量能枯竭"),
                        "Action": st.column_config.LinkColumn("深度透視", display_text="🔍 系統分析", width="small")
                    }
                )
            else:
                st.info("目前板塊內無符合 VCP 嚴格條件的標的。")
