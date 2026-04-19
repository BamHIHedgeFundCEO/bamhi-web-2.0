import streamlit as st
from components.charts import render_dynamic_chart

# ============== 🧠 選單對應本地端資料引擎 (Mapping) ==============
UI_MACRO_MAPPING = {
    "10年期美債殖利率": {"cat_id": "rates", "module": "treasury", "ticker": "DGS10", "name": "10 Years Yield", "id": "DGS10"},
    "2年期美債殖利率": {"cat_id": "rates", "module": "treasury", "ticker": "DGS2", "name": "2 Years Yield", "id": "DGS2"},
    "10-2 spread": {"cat_id": "rates", "module": "treasury", "ticker": "SPREAD_10_2", "name": "10-2 Spread", "id": "SPREAD_10_2"},
    "市場寬度": {"cat_id": "market", "module": "breadth", "ticker": "SP500_BREADTH", "name": "S&P 500 市場寬度", "id": "BREADTH_SP500"},
    "情緒方向": {"cat_id": "market", "module": "naaim", "ticker": "NAAIM_AAII", "name": "散戶 & 機構情緒方向", "id": "SENTIMENT_COMBO"},
}

# ============== 🏠 總經市場分頁 ==============
def render_macro_market():
    st.title("📊 總經市場指標")
    
    # 模擬下拉的水平選單
    options = list(UI_MACRO_MAPPING.keys())
    selected_sub = st.radio("指標選擇", options, horizontal=True, label_visibility="collapsed")
    st.divider()
    
    st.subheader(f"📉 {selected_sub}")
    render_dynamic_chart(UI_MACRO_MAPPING[selected_sub])
