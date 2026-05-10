"""
components/sector_signals.py
首頁板塊訊號推播面板：快速掃描所有板塊的進出場狀態並在首頁顯示
"""
import streamlit as st
from data_engine.market.sector_engine import calculate_sector_metrics
from config.sectors import TRACKED_SECTORS, SECTOR_LEADERS

def get_signal_for_sector(sector_name, period="1y"):
    """
    根據進出場邏輯，回傳一個板塊的訊號狀態
    回傳: (emoji, status_text, detail_text, color_key)
    """
    tickers = TRACKED_SECTORS.get(sector_name, [])
    if not tickers:
        return ("⚪", "無資料", "無法取得板塊資料", "gray")

    try:
        df_sector, _ = calculate_sector_metrics(tickers, period=period)
        if df_sector is None or df_sector.empty:
            return ("⚪", "無資料", "無法計算板塊指標", "gray")

        latest = df_sector.iloc[-1]
        close_val  = latest.get('Sector_Close', 0)
        ma20_val   = latest.get('MA20', 0)
        ma60_val   = latest.get('MA60', 0)
        rs_slope   = latest.get('RS_Slope', 0)     # ✅ 正確欄位名稱

        # ✅ 擁擠度：原始值是小數（0~1），乘以 100 轉成百分比
        crowd_ratio = latest.get('Crowdedness', 0) * 100
        crowd_90p   = latest.get('Crowdedness_90p', 999) * 100
        is_overheated = crowd_ratio >= crowd_90p

        # 判斷訊號（與板塊輪動頁邏輯完全一致）
        if is_overheated:
            return ("🚨", "過熱警報",
                    f"擁擠度 {crowd_ratio:.1f}% 已突破90分位 {crowd_90p:.1f}%，籌碼極度擁擠，注意大戶派發風險！",
                    "red")
        elif close_val < ma20_val:
            return ("🔴", "空頭弱勢",
                    f"指數跌破月線（收盤 {close_val:.2f} < MA20 {ma20_val:.2f}），建議觀望。",
                    "orange")
        elif close_val > ma20_val and ma20_val > ma60_val and rs_slope > 0 and latest.get('M5', 0) > 0:
            return ("🟢", "強勢多頭",
                    f"Close > MA20 > MA60，RS 向上發散，板塊處於主升段，可尋找 VCP 突破點。",
                    "green")
        elif close_val > ma20_val and rs_slope > 0:
            return ("🔵", "初步轉強",
                    f"指數剛站上月線且 RS 翻轉向上，有落底回升跡象，可開始關注 VCP 候選股。",
                    "blue")
        else:
            return ("🟡", "整理蓄力",
                    f"指數在月線之上但動能衰減或 RS 下滑，板塊可能橫盤消化或面臨賣壓。",
                    "yellow")

    except Exception as e:
        return ("⚪", "計算錯誤", f"資料計算過程異常: {str(e)[:60]}", "gray")


def render_sector_signals_panel():
    """首頁板塊訊號推播面板"""
    # 背景卡片容器
    st.markdown("""
    <div style='
        background: linear-gradient(135deg, #0f1923 0%, #1a2635 100%);
        border: 1px solid #1e3a5f;
        border-radius: 16px;
        padding: 24px 28px 16px 28px;
        margin: 20px 0;
    '>
        <div style='display:flex; align-items:center; gap:10px; margin-bottom:4px;'>
            <span style='font-size:1.4rem;'>⚡</span>
            <h3 style='color:white; margin:0; font-size:1.15rem;'>板塊即時訊號推播</h3>
        </div>
        <p style='color:#6b7280; font-size:0.82rem; margin:0 0 18px 0;'>
            基於板塊指數 MA 排列 + 擁擠度防護罩，快速瀏覽所有板塊進出場狀態
        </p>
    </div>
    """, unsafe_allow_html=True)

    COLOR_MAP = {
        "green":  ("#052e16", "#16a34a"),
        "blue":   ("#0c1a2e", "#3b82f6"),
        "yellow": ("#1c1a00", "#ca8a04"),
        "orange": ("#2d1200", "#ea580c"),
        "red":    ("#2d0a0a", "#dc2626"),
        "gray":   ("#111827", "#4b5563"),
    }

    with st.spinner("正在快速掃描所有板塊訊號..."):
        cols_per_row = 2
        sector_list = list(TRACKED_SECTORS.keys())
        
        for i in range(0, len(sector_list), cols_per_row):
            row_sectors = sector_list[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            
            for col, sector_name in zip(cols, row_sectors):
                emoji, status, detail, color_key = get_signal_for_sector(sector_name)
                bg_color, border_color = COLOR_MAP.get(color_key, ("#111827", "#4b5563"))
                leaders = SECTOR_LEADERS.get(sector_name, [])
                leaders_html = (
                    f"<div style='margin-top:5px; font-size:0.77rem; color:#f59e0b;'>👑 龍頭：{' · '.join(leaders)}</div>"
                    if leaders else ""
                )
                
                # 使用 expander 實現「點擊展開詳情」
                with col:
                    label = f"{emoji} **{sector_name}**  —  {status}"
                    with st.expander(label, expanded=False):
                        st.markdown(
                            f"<div style='background:{bg_color}; border-left:3px solid {border_color}; "
                            f"border-radius:8px; padding:12px 15px; font-size:0.88rem; color:#e5e7eb;'>"
                            f"{detail}"
                            f"{leaders_html}"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        # ✅ 使用 st.button 跳轉：設定 session_state 後切換到板塊輪動頁
                        if st.button(
                            f"🔍 前往查看 {sector_name.split('(')[0].strip()} 詳細分析",
                            key=f"goto_{sector_name}",
                            use_container_width=True
                        ):
                            st.session_state["sector_selectbox_ui"] = sector_name
                            st.session_state["goto_sector_rotation"] = True
                            st.rerun()
