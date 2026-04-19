import streamlit as st
from components.charts import render_dynamic_chart

# ============== 🧠 選單對應本地端資料引擎 (Mapping) ==============
UI_TOOLS_MAPPING = {
    "美股板塊強弱": {"cat_id": "market", "module": "strength", "ticker": "ALL", "name": "美股板塊強弱 (Sector Strength)", "id": "SECTOR_STRENGTH"},
    "全球市場強弱": {"cat_id": "market", "module": "world_sectors", "ticker": "WORLD", "name": "龜族全景動能儀表板", "id": "world_sectors"},
}

# ============== 🛠️ 交易工具分頁 ==============
def render_trading_tools():
    st.title("🛠️ 交易工具")
    
    # 模擬下拉的水平選單
    options = list(UI_TOOLS_MAPPING.keys())
    selected_sub = st.radio("工具選擇", options, horizontal=True, label_visibility="collapsed")
    st.divider()
    
    st.subheader(f"🎯 {selected_sub}")
    render_dynamic_chart(UI_TOOLS_MAPPING[selected_sub])
