import streamlit as st

try:
    from streamlit_option_menu import option_menu
except ImportError:
    st.error("🚨 找不到 `streamlit-option-menu` 套件！請在終端機輸入：`pip install streamlit-option-menu`")
    st.stop()

# ============== 🧭 頂部導覽列 (Navbar) ==============
def render_navbar():
    col1, col2, col3 = st.columns([1.5, 6, 2])
    
    with col1:
        st.markdown("<h3 style='margin-top: 10px; color: #3b82f6;'>🌌 BamHI Quant</h3>", unsafe_allow_html=True)
        
    with col2:
        # 👇 這裡改為「交易模型」
        NAV_OPTIONS = ["首頁", "總經市場 ▼", "交易工具 ▼", "交易模型", "專區", "功能教學"]
        selected = option_menu(
            menu_title=None, 
            options=NAV_OPTIONS,
            # 👇 第四個 icon 改為 "cpu"
            icons=["house", "activity", "tools", "cpu", "star", "book"],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#9ca3af", "font-size": "14px"}, 
                "nav-link": {"font-size": "14px", "text-align": "center", "margin":"0px", "--hover-color": "#1f2937", "color": "#d1d5db"},
                "nav-link-selected": {"background-color": "#1f2937", "color": "white"},
            }
        )
        
    with col3:
        search_query = st.text_input("🔍 搜尋美股代碼...", label_visibility="collapsed", placeholder="搜尋代碼...")
        
    return selected, search_query

# ============== 🏠 封面區塊 (100% 原汁原味保留) ==============
def render_hero_section():
    st.markdown("<br><br>", unsafe_allow_html=True) 
    col_left, col_right = st.columns([1.2, 1], gap="large")
    
    with col_left:
        st.markdown("<div class='bento-tag'>▲ BAMHI QUANT 趨勢追蹤器</div>", unsafe_allow_html=True)
        st.markdown("<div class='hero-title'>更早看懂市場，<br>少走研究彎路</div>", unsafe_allow_html=True)
        st.markdown("""
        <div class='hero-subtitle'>
        BamHI Quant 把全市場掃描、板塊輪動、趨勢雷達、回測驗證、機構與內部人追蹤，整合出一套每天可以直接執行的研究工作流。<br><br>
        重視資訊量，而且想更快找到值得研究的標的與時機，BamHI 是最貼近你需求的工具。新『專區』功能也會持續更新研究當下的原始紀錄與 AI 工作流，不只給你最後結論。<br><br>
        Buy the dip, short the VIX, f**k Bitcoin.
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div>
            <a href='#' class='primary-btn'>🚀 開始 7 天免費試用</a>
            <a href='#' class='secondary-btn'>👤 登入 / 建立帳號</a>
            <a href='#' class='secondary-btn'>📖 查看 10 大功能</a>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br><p style='color:#fbbf24; font-size:0.9rem;'>⚡ 試用期間全功能開放，包含會員專區與 AI 工作流相關內容。</p>", unsafe_allow_html=True)

    with col_right:
        st.markdown("""
        <div class='bento-card'>
            <div class='bento-tag'>會員專區亮點</div>
            <h3 style='color: white; margin-bottom: 10px;'>會員專區 + AI 工作流，<br>讓你更早看到研究過程</h3>
            <p style='color: #9ca3af; font-size: 0.9rem; line-height: 1.5; margin-bottom: 20px;'>
            不只看整理後結論，而是更早看到我如何追蹤題材、整理資料、記錄部位與持續追蹤。
            </p>
            
            <div style='background-color: #1f2937; padding: 15px; border-radius: 10px; margin-bottom: 10px;'>
                <strong style='color: white; font-size: 0.9rem;'>第一手研究紀錄</strong><br>
                <span style='color: #9ca3af; font-size: 0.8rem;'>交易想法、部位變化與事件追蹤，持續更新在專區。</span>
            </div>
            
            <div style='background-color: #1f2937; padding: 15px; border-radius: 10px; margin-bottom: 10px;'>
                <strong style='color: white; font-size: 0.9rem;'>AI 工作流拆解</strong><br>
                <span style='color: #9ca3af; font-size: 0.8rem;'>直接看到我如何用 AI 協助研究、整理資料與建立觀察名單。</span>
            </div>
            
            <div style='background-color: #1f2937; padding: 15px; border-radius: 10px;'>
                <strong style='color: white; font-size: 0.9rem;'>從想法到執行一條龍</strong><br>
                <span style='color: #9ca3af; font-size: 0.8rem;'>先用工具找機會，再回到專區持續跟進，讓研究能一路追蹤下去。</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
