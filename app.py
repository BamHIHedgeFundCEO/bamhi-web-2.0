import streamlit as st

# 🚨 必須在第一行設定頁面
st.set_page_config(
    page_title="BamHI Quant",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="collapsed"
)

import os
from components.ui_layout import render_navbar, render_hero_section
from views.macro_market import render_macro_market
from views.trading_tools import render_trading_tools
from views.trading_models import render_trading_models
from views.search_view import render_search_result

def load_local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ 找不到 CSS 樣式檔案：{file_name}")

# ============== 主程式 ==============
def main():
    # 載入所有全域 CSS
    load_local_css("assets/style.css")

    if "search_query" not in st.session_state:
        st.session_state.search_query = ""

    # 渲染頂部導覽列與搜尋框
    selected_nav, search_input = render_navbar()
    
    # 把選單上的 ▼ 符號拿掉來做邏輯判斷
    page_token = selected_nav.replace(" ▼", "")
    
    # 同步搜尋狀態
    if search_input:
        st.session_state.search_query = search_input
        render_search_result(search_input)
        
    elif page_token == "首頁":
        render_hero_section()
        
    elif page_token == "總經市場":
        render_macro_market()
        
    elif page_token == "交易工具":
        render_trading_tools()
        
    elif page_token == "交易模型":
        render_trading_models()
        
    elif page_token in ["專區", "功能教學"]:
        st.title(f"🚧 {page_token}")
        st.info("此功能正在開發中...")

if __name__ == "__main__":
    main()