import streamlit as st
import pandas as pd
from datetime import datetime
import importlib
from deep_translator import GoogleTranslator
# 🚨 自動偵測是否安裝了導覽列套件
try:
    from streamlit_option_menu import option_menu
except ImportError:
    st.error("🚨 找不到 `streamlit-option-menu` 套件！請在終端機輸入：`pip install streamlit-option-menu`")
    st.stop()

# 🚨 必須在第一行設定頁面
st.set_page_config(
    page_title="BamHI Quant",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 匯入你本地端寫好的模組
import config
from data_engine import get_data
import notes

# ============== 🎨 全域 CSS 樣式 (100% 保留你原本的致敬 Trend-Core 風格) ==============
st.markdown("""
<style>
    /* 全域深色背景與字體 */
    .stApp { 
        background-color: #0f1319; 
        color: #e5e7eb;
    }
    
    /* 隱藏預設的頂部紅線和漢堡選單，讓畫面更乾淨 */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* 頂部搜尋框樣式 */
    .stTextInput>div>div>input {
        background-color: #1f2937;
        color: white;
        border: 1px solid #374151;
        border-radius: 20px;
        padding-left: 15px;
    }
    .stTextInput>div>div>input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 1px #3b82f6;
    }

    /* Hero Section 大標題 */
    .hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        line-height: 1.2;
        color: #ffffff;
        margin-bottom: 1rem;
    }
    
    /* Hero Section 副標題 */
    .hero-subtitle {
        font-size: 1.1rem;
        color: #9ca3af;
        line-height: 1.6;
        margin-bottom: 2rem;
    }

    /* 主按鈕 (綠色) */
    .primary-btn {
        background-color: #10b981;
        color: #ffffff;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        text-decoration: none;
        display: inline-block;
        transition: all 0.2s;
        border: none;
    }
    .primary-btn:hover {
        background-color: #059669;
        transform: translateY(-2px);
    }

    /* 次按鈕 (深灰色) */
    .secondary-btn {
        background-color: #1f2937;
        color: #e5e7eb;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        text-decoration: none;
        display: inline-block;
        transition: all 0.2s;
        border: 1px solid #374151;
        margin-left: 10px;
    }
    .secondary-btn:hover {
        background-color: #374151;
    }

    /* 右側 Bento 卡片 */
    .bento-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .bento-tag {
        background-color: #064e3b;
        color: #34d399;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ============== 🧠 選單對應本地端資料引擎 (Mapping) ==============
UI_MACRO_MAPPING = {
    "10年期美債殖利率": {"cat_id": "rates", "module": "treasury", "ticker": "DGS10", "name": "10 Years Yield", "id": "DGS10"},
    "2年期美債殖利率": {"cat_id": "rates", "module": "treasury", "ticker": "DGS2", "name": "2 Years Yield", "id": "DGS2"},
    "10-2 spread": {"cat_id": "rates", "module": "treasury", "ticker": "SPREAD_10_2", "name": "10-2 Spread", "id": "SPREAD_10_2"},
    "市場寬度": {"cat_id": "market", "module": "breadth", "ticker": "SP500_BREADTH", "name": "S&P 500 市場寬度", "id": "BREADTH_SP500"},
    "情緒方向": {"cat_id": "market", "module": "naaim", "ticker": "NAAIM_AAII", "name": "散戶 & 機構情緒方向", "id": "SENTIMENT_COMBO"},
}

UI_TOOLS_MAPPING = {
    "美股板塊強弱": {"cat_id": "market", "module": "strength", "ticker": "ALL", "name": "美股板塊強弱 (Sector Strength)", "id": "SECTOR_STRENGTH"},
    "全球市場強弱": {"cat_id": "market", "module": "world_sectors", "ticker": "WORLD", "name": "龜族全景動能儀表板", "id": "world_sectors"},
}

# ============== 🧭 頂部導覽列 (Navbar) ==============
def render_navbar():
    col1, col2, col3 = st.columns([1.5, 6, 2])
    
    with col1:
        st.markdown("<h3 style='margin-top: 10px; color: #3b82f6;'>🌌 BamHI Quant</h3>", unsafe_allow_html=True)
        
    with col2:
        # 加入了下拉箭頭的選單
        NAV_OPTIONS = ["首頁", "總經市場 ▼", "交易工具 ▼", "交易日誌", "專區", "功能教學"]
        selected = option_menu(
            menu_title=None, 
            options=NAV_OPTIONS,
            icons=["house", "activity", "tools", "journal-text", "star", "book"],
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
        重視資訊量，而且想更快找到值得研究的標的與時機，BamHI 是最貼近你需求的工具。新『專區』功能也會持續更新研究當下的原始紀錄與 AI 工作流，不只給你最後結論。
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

# ============== 🔍 股票搜尋結果頁面 ==============
# ============== 🔍 股票深度搜尋引擎 (純 UI 介面) ==============
def render_search_result(ticker: str):
    st.markdown("<br>", unsafe_allow_html=True)
    st.button("← 結束搜尋，返回首頁", on_click=lambda: st.session_state.update({"search_query": ""}))
    
    ticker_upper = ticker.upper()

    # ==========================================
    # 👇 新增：超酷的時間級別與歷史長度控制器
    # ==========================================
    st.markdown("### ⚙️ 圖表參數設定")
    col_opt1, col_opt2, col_opt3 = st.columns([1, 1, 2])
    with col_opt1:
        # 提供 6 個月到 max 的選項，預設選擇 "2y" (index=2)
        period_opt = st.selectbox("📅 歷史區間", ["6mo", "1y", "2y", "5y", "10y", "max"], index=2)
    with col_opt2:
        # 提供小時、日、週線的選項，並自動顯示為中文
        interval_opt = st.selectbox("⏱️ K線級別", ["1h", "1d", "1wk"], index=1, format_func=lambda x: {"1h":"1小時線", "1d":"日線", "1wk":"週線"}[x])

    # 防呆機制：Yahoo Finance 的 API 規定 1小時線 最多只能抓 730 天
    if interval_opt == "1h" and period_opt in ["5y", "10y", "max"]:
        st.warning("⚠️ Yahoo API 限制：1小時線最多只能查詢過去 2 年 (730天)。已自動為您降至 2y。")
        period_opt = "2y"
        
    st.divider()
    
    with st.spinner(f"正在全網掃描 {ticker_upper} 的深度數據..."):
        import data_engine.equity as equity_engine
        
        # 👇 這裡最關鍵！把我們選好的時間參數傳給大腦
        data = equity_engine.fetch_stock_profile(ticker_upper, period=period_opt, interval=interval_opt)
        
        if not data:
            st.error(f"⚠️ 找不到代碼 {ticker_upper}，請確認輸入是否正確 (例如: AAPL, TSLA)。")
            return
            
        # 使用 .get() 確保如果資料缺失不會當機
        info = data.get("info", {})
        hist = data.get("history", pd.DataFrame())

        # 1. 萃取價格與基本數值
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        prev_close = info.get('previousClose', current_price)
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        # 取得公司名稱
        company_name = info.get('shortName', info.get('longName', ticker_upper))
        
        # 標題與價格區塊
        st.markdown(f"<h1 style='margin-bottom: 0;'>{company_name} ({ticker_upper})</h1>", unsafe_allow_html=True)
        price_color = "#34d399" if change >= 0 else "#ef4444"
        st.markdown(f"""
            <div style='display: flex; align-items: baseline; gap: 15px; margin-bottom: 20px;'>
                <h2 style='color: {price_color}; margin: 0; font-size: 2.5rem;'>${current_price:.2f}</h2>
                <span style='color: {price_color}; font-size: 1.2rem; font-weight: bold;'>
                    {change:+.2f} ({change_pct:+.2f}%)
                </span>
            </div>
        """, unsafe_allow_html=True)

        # 2. 核心財務指標 (四宮格)
        pe_ratio = info.get('trailingPE', 'N/A')
        pb_ratio = info.get('priceToBook', 'N/A')
        market_cap = info.get('marketCap', 0)
        market_cap_str = f"${market_cap / 1e9:.2f} B" if market_cap else "N/A"
        roe = info.get('returnOnEquity', 0)
        roe_str = f"{roe * 100:.2f}%" if roe else "N/A"

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("總市值", market_cap_str)
        col2.metric("本益比 (P/E)", f"{pe_ratio:.2f}" if isinstance(pe_ratio, (int, float)) else pe_ratio)
        col3.metric("股價淨值比 (P/B)", f"{pb_ratio:.2f}" if isinstance(pb_ratio, (int, float)) else pb_ratio)
        col4.metric("股東權益報酬率 (ROE)", roe_str)

        st.markdown("---")

        # 3. 深度分析頁籤 ( Tabs )
        tab_chart, tab_info, tab_finance, tab_quant = st.tabs([
            "📈 技術線圖", "🏢 基本資料", "📊 財務報表", "🤖 籌碼與進階交易"
        ])

# ── 頁籤 1：技術線圖 ──
        with tab_chart:
            # 👇 把使用者選好的 K 線級別 (interval_opt) 傳給畫圖引擎
            fig = equity_engine.plot_candlestick(hist, ticker_upper, interval=interval_opt)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("暫無歷史價格數據。")

      # ── 頁籤 2：基本資料 ──
        with tab_info:
            st.subheader("公司簡介")
            col_info1, col_info2 = st.columns([1, 2])
            with col_info1:
                emp = info.get('fullTimeEmployees')
                emp_str = f"{emp:,}" if isinstance(emp, (int, float)) else "N/A"
                
                st.markdown(f"""
                <div class='bento-card' style='padding: 1rem;'>
                    <p style='color:#9ca3af; font-size:0.85rem; margin-bottom: 5px;'>所屬板塊 (Sector)</p>
                    <p style='font-size:1.1rem; font-weight:bold; color:white;'>{info.get('sector', 'N/A')}</p>
                    <p style='color:#9ca3af; font-size:0.85rem; margin-bottom: 5px; margin-top:15px;'>所屬產業 (Industry)</p>
                    <p style='font-size:1.1rem; font-weight:bold; color:white;'>{info.get('industry', 'N/A')}</p>
                    <p style='color:#9ca3af; font-size:0.85rem; margin-bottom: 5px; margin-top:15px;'>全職員工數</p>
                    <p style='font-size:1.1rem; font-weight:bold; color:white;'>{emp_str}</p>
                </div>
                """, unsafe_allow_html=True)
                
            with col_info2:
                # 抓取英文原文
                raw_summary = info.get('longBusinessSummary', '暫無公司業務介紹。')
                
                # 自動翻譯機制 (加入 try-except 防止翻譯失敗導致當機)
                display_summary = raw_summary
                if raw_summary != '暫無公司業務介紹。':
                    with st.spinner("🤖 正在將公司簡介翻譯為繁體中文..."):
                        try:
                            # 呼叫 Google 翻譯引擎轉為繁體中文 (zh-TW)
                            translated = GoogleTranslator(source='auto', target='zh-TW').translate(raw_summary)
                            display_summary = translated
                        except Exception:
                            # 如果翻譯伺服器忙碌，優雅地退回顯示英文
                            display_summary = f"{raw_summary}<br><br><span style='color:#ef4444; font-size:0.8rem;'>*(翻譯伺服器暫時忙碌，顯示原文)*</span>"

                # 顯示翻譯後的中文結果
                st.markdown(f"<div style='background-color:#1f2937; padding:15px; border-radius:10px; color:#d1d5db; line-height:1.6;'>{display_summary}</div>", unsafe_allow_html=True)
                st.caption("💡 資料來源: Yahoo Finance | 翻譯: Google Translate")
        # ── 頁籤 3：財務報表 ──
        with tab_finance:
            st.subheader("關鍵財務數據")
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            f_col1.metric("毛利率 (Gross Margin)", f"{info.get('grossMargins', 0)*100:.2f}%" if info.get('grossMargins') else "N/A")
            f_col2.metric("營收成長 (YoY)", f"{info.get('revenueGrowth', 0)*100:.2f}%" if info.get('revenueGrowth') else "N/A")
            f_col3.metric("淨利率 (Profit Margin)", f"{info.get('profitMargins', 0)*100:.2f}%" if info.get('profitMargins') else "N/A")
            f_col4.metric("負債資產比", f"{info.get('debtToEquity', 0):.2f}%" if info.get('debtToEquity') else "N/A")
            
            st.markdown("#### 📄 年度損益表 (Income Statement)")
            if not data["income_stmt"].empty:
                # 將資料轉置 (Transpose) 讓年份在上面，科目在左邊，並將大數字除以 100 萬 (轉換為百萬美元)
                df_income = data["income_stmt"].copy()
                df_income.columns = [str(date).split(' ')[0] for date in df_income.columns] # 取出日期字串
                df_income = df_income / 1000000 # 轉換單位為百萬
                
                # 只挑選幾個重要的中文科目顯示
                key_items = {
                    "Total Revenue": "總營收",
                    "Gross Profit": "毛利",
                    "Operating Income": "營業利益",
                    "Net Income": "淨利"
                }
                
                # 過濾並重新命名
                df_display = pd.DataFrame()
                for en_key, tw_key in key_items.items():
                    if en_key in df_income.index:
                        df_display[tw_key] = df_income.loc[en_key]
                
                if not df_display.empty:
                    st.dataframe(df_display.T.style.format("{:,.2f} M"), use_container_width=True)
            else:
                st.info("無法取得損益表資料。")

        # ── 頁籤 4：籌碼與進階交易 (預留骨架) ──
        with tab_quant:
            st.subheader("🤖 BamHI 量化訊號與特殊模組")
            
            col_q1, col_q2 = st.columns(2)
            with col_q1:
                st.markdown("""
                <div class='bento-card'>
                    <h4 style='color: #60a5fa;'>🕵️ 內部人與機構動向</h4>
                    <p style='color: #9ca3af; font-size: 0.9rem;'>追蹤 CEO/CFO 買賣紀錄與大戶籌碼流向。</p>
                    <div style='background-color: rgba(255,193,7,0.1); color: #ffc107; padding: 10px; border-radius: 8px; font-size: 0.85rem; text-align: center;'>
                        🚧 爬蟲程式開發中，即將開放
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            with col_q2:
                st.markdown("""
                <div class='bento-card'>
                    <h4 style='color: #a78bfa;'>🕸️ 網格與期權交易雷達</h4>
                    <p style='color: #9ca3af; font-size: 0.9rem;'>選擇權未平倉量 (OI) 分佈與適合網格交易的震盪區間。</p>
                    <div style='background-color: rgba(255,193,7,0.1); color: #ffc107; padding: 10px; border-radius: 8px; font-size: 0.85rem; text-align: center;'>
                        🚧 模組建置中，敬請期待
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ============== 📊 畫出共用的動態圖表 (完全依賴你的 data_engine) ==============
def render_dynamic_chart(item_config):
    cat_id = item_config["cat_id"]
    module_name = item_config["module"]
    ticker = item_config["ticker"]
    
    # 呼叫你的 data_engine 讀資料
    row_data = get_data(cat_id, module_name, ticker)
    
    if row_data:
        change_val = row_data.get('change_pct', 0)
        st.caption(f"最新數值: **{row_data.get('value', 0):.2f}** |  漲跌幅: {change_val:+.2f}%")
        df = row_data.get("history", pd.DataFrame())
    else:
        st.error(f"⚠️ 無法取得數據！請確認 `data/{module_name}.csv` 檔案是否存在且格式正確。")
        df = pd.DataFrame()
        
    st.divider()

    # 時間區間過濾器
    if not df.empty and "date" in df.columns:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        col_range, _ = st.columns([4, 1])
        with col_range:
            range_option = st.radio("時間區間", ["All", "6m", "YTD", "1Y", "3Y", "5Y", "10Y"], horizontal=True, key=f"range_{item_config['id']}")

        end = df["date"].max()
        if range_option == "All": start = df["date"].min()
        elif range_option == "6m": start = end - pd.DateOffset(months=6)
        elif range_option == "YTD": start = datetime(end.year, 1, 1)
        elif range_option == "1Y": start = end - pd.DateOffset(years=1)
        elif range_option == "3Y": start = end - pd.DateOffset(years=3)
        elif range_option == "5Y": start = end - pd.DateOffset(years=5)
        else: start = end - pd.DateOffset(years=10)

        df_filtered = df[(df["date"] >= start) & (df["date"] <= end)]

        try:
            mod = importlib.import_module(f"data_engine.{cat_id}.{module_name}")
            fig = mod.plot_chart(df_filtered, item_config)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"無法載入繪圖邏輯：請確認 `data_engine/{cat_id}/{module_name}.py` 裡面有 `plot_chart` 函式。錯誤: {e}")
    else:
        st.info("暫無歷史數據可繪製，請檢查 CSV 檔案中是否有 'date' 欄位。")

    # 串連你的筆記系統
    st.markdown("---")
    st.subheader(f"📝 交易筆記與紀錄")
    try:
        note_content = notes.fetch_note(cat_id, module_name, ticker)
        st.markdown(note_content)
    except Exception as e:
        st.caption(f"尚無此指標筆記。")

# ============== 🏠 總經市場分頁 ==============
def render_macro_market():
    st.title("📊 總經市場指標")
    
    # 模擬下拉的水平選單
    options = list(UI_MACRO_MAPPING.keys())
    selected_sub = st.radio("指標選擇", options, horizontal=True, label_visibility="collapsed")
    st.divider()
    
    st.subheader(f"📉 {selected_sub}")
    render_dynamic_chart(UI_MACRO_MAPPING[selected_sub])

# ============== 🛠️ 交易工具分頁 ==============
def render_trading_tools():
    st.title("🛠️ 交易工具")
    
    # 模擬下拉的水平選單
    options = list(UI_TOOLS_MAPPING.keys())
    selected_sub = st.radio("工具選擇", options, horizontal=True, label_visibility="collapsed")
    st.divider()
    
    st.subheader(f"🎯 {selected_sub}")
    render_dynamic_chart(UI_TOOLS_MAPPING[selected_sub])

# ============== 主程式 ==============
def main():
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
        
    elif page_token in ["交易日誌", "專區", "功能教學"]:
        st.title(f"🚧 {page_token}")
        st.info("此功能正在開發中...")

if __name__ == "__main__":
    main()