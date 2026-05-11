"""
views/sector_rotation.py
BamHI 交易工具：板塊輪動與 VCP 監控系統
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf

# 匯入後端大腦
from data_engine.market.sector_engine import calculate_sector_metrics, scan_vcp_candidates
from views._sector_charts import (render_rrg_tab, render_breadth_chart, get_rrg_quadrant,
                                   render_rrg_trail_tab, render_correlation_heatmap,
                                   render_institutional_flow_chart, render_momentum_crossover_chart)

# ✅ 板塊設定集中管理，從 sector_config 引入（避免與根目錄 config.py 衝突）
from sector_config import TRACKED_SECTORS, SECTOR_LEADERS

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
    leaders = SECTOR_LEADERS.get(sector_name, [])
    
    # 追蹤清單（龍頭股用 ⭐ 標記）
    ticker_display = [f"⭐ {t}" if t in leaders else t for t in tickers]
    st.caption(f"**追蹤清單:** {', '.join(ticker_display)}")
    
    # 龍頭股提示
    if leaders:
        _leader_html = "  ·  ".join(f"<code style='color:#f59e0b'>{t}</code>" for t in leaders)
        st.markdown(
            f"<div style='background:linear-gradient(90deg,#1e3a5f,#1f2937);padding:8px 14px;border-radius:8px;"
            f"border-left:3px solid #f59e0b;margin-bottom:6px;font-size:0.88rem;'>"
            f"👑 <b>板塊龍頭：</b> {_leader_html}&nbsp;"
            f"<span style='color:#9ca3af;font-size:0.8rem;'>（這些是此板塊重點追蹤的核心標的）</span></div>",
            unsafe_allow_html=True
        )
    st.markdown("---")

    # === 預先計算所有板塊資料（一次載入，4個 Tab 共用，避免殘留）===
    with st.spinner("🔄 正在從 Yahoo Finance 批量下載所有追蹤標的，確保不漏接..."):
        all_sector_data = {}
        
        # 1. 蒐集所有板塊中的獨立 tickers
        all_unique_tickers = set(['SPY'])
        for _s_tickers in TRACKED_SECTORS.values():
            all_unique_tickers.update(_s_tickers)
            
        @st.cache_data(ttl=3600, show_spinner=False)
        def fetch_bulk_data(tickers_list, period):
            return yf.download(tickers_list, period=period, progress=False, auto_adjust=False)
            
        bulk_raw_data = fetch_bulk_data(list(all_unique_tickers), period_opt)

        # 2. 本地超高速計算各個板塊的指標 (無網路請求)
        for _s_name, _s_tickers in TRACKED_SECTORS.items():
            _df, _ = calculate_sector_metrics(_s_tickers, period=period_opt, raw_data=bulk_raw_data)
            if _df is not None and not _df.empty:
                all_sector_data[_s_name] = _df

    # === 全覽面板：熱力圖 + RRG + 軌跡 + 相關係數 ===
    tab_heat, tab_rrg, tab_trail, tab_corr = st.tabs([
        "🗺️ 動能熱力圖",
        "📡 RRG 板塊輪動圖",
        "📈 RRG 軌跡追蹤",
        "🔗 板塊相關係數",
    ])

    with tab_heat:
        st.subheader("🗺️ 板塊動能熱力圖 (Sector Momentum Heatmap)")
        heatmap_data = []
        for s_name, _df_sec in all_sector_data.items():
            if not _df_sec.empty and 'Momentum_Diff' in _df_sec.columns:
                diff = _df_sec.iloc[-1]['Momentum_Diff']
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
            try:
                event = st.plotly_chart(
                    fig_heat,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="points"
                )
                if event and "selection" in event and "points" in event["selection"]:
                    points = event["selection"]["points"]
                    if points:
                        clicked_sector = points[0].get("label", "")
                        if clicked_sector in TRACKED_SECTORS and st.session_state.get("sector_selectbox_ui") != clicked_sector:
                            st.session_state.next_sector = clicked_sector
                            st.rerun()
            except TypeError:
                st.plotly_chart(fig_heat, use_container_width=True)
                st.info("💡 提示：點擊熱力圖會進行縮放。若要查看特定板塊，請從選單切換！")

    with tab_rrg:
        render_rrg_tab(all_sector_data)

    with tab_trail:
        render_rrg_trail_tab(all_sector_data)

    with tab_corr:
        render_correlation_heatmap(all_sector_data)

    # === 主畫面：單一板塊數據視覺化 ===
    if tickers:
        with st.spinner(f"正在計算 {sector_name} 詳細動能與 VCP 訊號..."):
            df_sector, vol_data = calculate_sector_metrics(tickers, period=period_opt, raw_data=bulk_raw_data)
            
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
            
            # 擁擠度雷達
            crowd_ratio = latest['Crowdedness'] * 100
            crowd_90p = latest['Crowdedness_90p'] * 100
            is_overheated = crowd_ratio >= crowd_90p

            col7.metric(
                "資金佔大盤均量比例",
                f"{crowd_ratio:.2f}%",
                delta="⚠️ 達 90% 過熱水位" if is_overheated else "✅ 水位正常",
                delta_color="inverse" if is_overheated else "normal"
            )

            # RRG 象限標籤（第二行顯示）
            rs_r_val = latest.get('RS_Ratio', None)
            rs_m_val = latest.get('RS_Momentum', None)
            if rs_r_val is not None and rs_m_val is not None and pd.notna(rs_r_val) and pd.notna(rs_m_val):
                q_label, q_color, q_desc = get_rrg_quadrant(float(rs_r_val), float(rs_m_val))
                st.markdown(
                    f"<div style='background:linear-gradient(90deg,#1e3a5f,#1f2937);"
                    f"padding:8px 16px;border-radius:8px;border-left:4px solid {q_color};"
                    f"margin:4px 0 8px 0;'>"
                    f"<span style='color:{q_color};font-weight:bold;font-size:1rem;'>{q_label}</span>"
                    f"&nbsp;&nbsp;<span style='color:#9ca3af;font-size:0.87rem;'>"
                    f"RS-Ratio: {rs_r_val:.2f} ｜ RS-Momentum: {rs_m_val:.2f} ｜ {q_desc}"
                    f"</span></div>",
                    unsafe_allow_html=True
                )
            
            # 判斷進出場狀態與防護罩警報
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
            
            fig = make_subplots(
                rows=3, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.5, 0.3, 0.2]
            )
            
            # Row 1: K線與均線
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
                
            # Row 2: 疊圖分析 (Sector vs SPY)
            fig.add_trace(go.Scatter(x=df_sector.index, y=df_sector['Sector_Index'], name=f"{sector_name} 指數", line=dict(color='blue', width=2)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_sector.index, y=df_sector['SPY_Index'], name="SPY 指數", line=dict(color='gray', width=1.5, dash='dot')), row=2, col=1)
            
            # Row 3: RS Line
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
                xaxis3_rangeslider_visible=False,
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # --- 2b. 板塊寬度走勢圖 ---
            render_breadth_chart(df_sector, sector_name)

            # --- 2c. 機構吃貨走勢圖 ---
            render_institutional_flow_chart(df_sector, sector_name)

            # --- 2d. M5/M10/M20 動能三線交叉圖 ---
            render_momentum_crossover_chart(df_sector, sector_name)

            # --- 3. VCP 個股掃描器 (包含超連結跳轉) ---
            st.markdown("---")
            st.subheader(f"🎯 {sector_name} 內部 VCP 掃描器")
            st.markdown("尋找趨勢向上且出現**波動收縮**與**成交量枯竭**的標的。")
            
            df_vcp = scan_vcp_candidates(tickers, period=period_opt, raw_data=bulk_raw_data)
            
            if not df_vcp.empty:
                df_vcp['Ticker'] = df_vcp['Ticker'].apply(
                    lambda t: f"⭐ {t}" if t in leaders else t
                )
                df_vcp['Action'] = "/?search_query=" + df_vcp['Ticker'].str.replace("⭐ ", "", regex=False)
                
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
                
                df_vcp['ATR_Pct_Fmt']         = df_vcp['ATR_Pct'].apply(lambda x: f"🔥 {x:.2f}%" if x < 1.5 else f"{x:.2f}%") if 'ATR_Pct' in df_vcp.columns else "-"
                df_vcp['ATR_Contraction_Fmt'] = df_vcp['ATR_Contraction'].apply(lambda x: f"🔥 {x:.2f}" if x < 0.7 else (f"⚠️ {x:.2f}" if x > 1.2 else f"{x:.2f}"))
                df_vcp['Up_Down_Vol_Fmt'] = df_vcp['Up_Down_Vol'].apply(lambda x: f"🐳 {x:.2f}" if x > 1.2 else f"{x:.2f}")
                df_vcp['RS_Rank_Fmt']     = df_vcp['RS_Rank'].apply(lambda x: f"🥇 {int(x)}" if x >= 80 else (f"🥈 {int(x)}" if x >= 50 else f"{int(x)}")) if 'RS_Rank' in df_vcp.columns else "-"
                
                df_vcp = df_vcp[['Ticker', 'Price', 'M1_Fmt', 'M10_Fmt', 'M20_Fmt', 'M60_Fmt',
                                  'Dist_MA20_Fmt', 'RS_3M_Fmt', 'RS_Rank_Fmt',
                                  'ATR_Pct_Fmt', 'ATR_Contraction_Fmt',
                                  'Up_Down_Vol_Fmt', 'Dist_to_High', 'Trend_Pass', 'Vol_Dry_Up', 'Action']]
                
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
                        "RS_3M_Fmt":           st.column_config.TextColumn("RS 3M"),
                        "RS_Rank_Fmt":         st.column_config.TextColumn("板塊RS排行"),
                        "ATR_Pct_Fmt":         st.column_config.TextColumn("ATR% (相對)"),
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
