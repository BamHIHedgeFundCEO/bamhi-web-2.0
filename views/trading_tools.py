import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from components.charts import render_dynamic_chart

# 匯入我們的後端大腦
from data_engine.market.darkpool import get_darkpool_surge_list

# ============== 🧠 選單對應本地端資料引擎 (Mapping) ==============
UI_TOOLS_MAPPING = {
    "暗池異常資金監控": "DARK_POOL",
    "美股板塊強弱": {"cat_id": "market", "module": "strength", "ticker": "ALL", "name": "美股板塊強弱 (Sector Strength)", "id": "SECTOR_STRENGTH"},
    "全球市場強弱": {"cat_id": "market", "module": "world_sectors", "ticker": "WORLD", "name": "龜族全景動能儀表板", "id": "world_sectors"},
}

def color_chg(val):
    try:
        v = float(val)
        if v > 0: return 'color: #00FF00;'
        elif v < 0: return 'color: #FF4136;'
    except: pass
    return ''

def color_rsi(val):
    try:
        v = float(val)
        if v > 70: return 'color: #FF4136; font-weight: bold;' # 超買
        elif v < 30: return 'color: #00FF00; font-weight: bold;' # 超賣
    except: pass
    return ''

def color_surx(val):
    try:
        v = float(val)
        if v >= 3.0: return 'color: #FF851B; font-weight: bold;'
        elif v >= 1.5: return 'color: #FFDC00;'
    except: pass
    return ''

def render_darkpool_scanner():
    """渲染暗池監控器頁面"""
    st.subheader("🎯 BamHI 交易工具：暗池異常資金監控 (Surge + 雙軌技術指標)")
    st.markdown("每日盤後全自動運算，捕捉 **暗池成交量異常放大 (Surx)**，並整合了趨勢 (VCP) 與反彈 (左側抄底) 雙軌技術型態濾網。")

    df_results = get_darkpool_surge_list()
    
    if df_results.empty:
        st.warning("⚠️ 目前尚無資料，請確認 `update_darkpool_pipeline.py` 是否已成功執行。")
        return
        
    st.success("✅ 資料讀取成功！以下為最新的 Top 50 異常與技術型態觀察名單：")
    
    # 整理格式
    format_dict = {
        'Price': "${:.2f}",
        'Chg%': "{:.2f}%",
        'Surx': "{:.2f}x",
        'Short%': "{:.2f}%",
        'Dist_52W_High%': "{:.2f}%",
        'Dist_MA200_%': "{:.2f}%",
        'Dist_52W_Low%': "{:.2f}%",
        'RSI_14': "{:.2f}"
    }
    
    # 如果舊欄位還在 (避免有時 CSV 未更新報錯)
    for col in list(format_dict.keys()):
        if col not in df_results.columns:
            format_dict.pop(col)
            
    styled_df = df_results.style\
        .map(color_chg, subset=['Chg%'] if 'Chg%' in df_results.columns else [])\
        .map(color_rsi, subset=['RSI_14'] if 'RSI_14' in df_results.columns else [])\
        .map(color_surx, subset=['Surx'] if 'Surx' in df_results.columns else [])\
        .format(format_dict)
    
    st.dataframe(styled_df, use_container_width=True, height=600)
    
    csv = df_results.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 下載完整技術型態分析報表 (CSV)",
        data=csv,
        file_name="BamHI_DarkPool_Technical_Top50.csv",
        mime="text/csv",
    )
# ============== 🛠️ 交易工具分頁 ==============
def render_trading_tools():
    st.title("🛠️ 交易工具")
    
    # 模擬下拉的水平選單
    options = list(UI_TOOLS_MAPPING.keys())
    selected_sub = st.radio("工具選擇", options, horizontal=True, label_visibility="collapsed")
    st.divider()
    
    if selected_sub == "暗池異常資金監控":
        render_darkpool_scanner()
    else:
        st.subheader(f"🎯 {selected_sub}")
        render_dynamic_chart(UI_TOOLS_MAPPING[selected_sub])
