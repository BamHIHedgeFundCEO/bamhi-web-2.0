import streamlit as st
import pandas as pd
from deep_translator import GoogleTranslator

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
            # 🌟 新增：從 hist 中萃取最新的趨勢與分數來顯示文字情報
            if not hist.empty and 'Composite' in hist.columns:
                last_score = hist['Composite'].iloc[-1]
                ma20 = hist['MA_20'].iloc[-1] if 'MA_20' in hist.columns else 0
                ma60 = hist['MA_60'].iloc[-1] if 'MA_60' in hist.columns else 0
                ma120 = hist['MA_120'].iloc[-1] if 'MA_120' in hist.columns else 0
                
                # 均線趨勢判斷
                if ma20 > ma60 > ma120: trend_status = "多頭 🐂 (均線發散)"
                elif ma20 < ma60 < ma120: trend_status = "空頭 🐻 (均線蓋頭)"
                else: trend_status = "盤整震盪 ⚖️ (均線糾結)"
                
                # 燈號判斷
                if last_score > 75: status_emoji = "🔴 過熱警示 (賣訊)"
                elif last_score < 25: status_emoji = "🟢 超跌機會 (買訊)"
                else: status_emoji = "⚪ 觀望持有"
                
                # 用精美的並排卡片顯示出來
                col_t1, col_t2 = st.columns(2)
                col_t1.info(f"**趨勢狀態:** {trend_status}")
                col_t2.info(f"**量化訊號:** {status_emoji} (綜合分數: **{last_score:.1f}**)")

            # 👇 畫出雙層圖表
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
                # 💡 更安全的寫法
                is_tw = "台灣" in str(info.get('sector', '')) or "TWSE" in str(info.get('sector', ''))
                source_name = "FMP (Financial Modeling Prep)" if is_tw else "Yahoo Finance"
                st.caption(f"💡 簡介資料來源: {source_name} | 翻譯: Google Translate")
# ── 頁籤 3：財務報表 ──
        with tab_finance:
            finance_source = data.get("finance_source")
            if finance_source:
                st.markdown(f"### 關鍵財務數據 <span style='font-size:0.8rem; background-color:#374151; color:#9ca3af; padding:2px 8px; border-radius:10px; vertical-align:middle; margin-left:10px;'>資料來源: {finance_source}</span>", unsafe_allow_html=True)
            else:
                st.subheader("關鍵財務數據")
            
            # 💡 智能判斷：如果是台股，幣別換成 NT$，除數換成 1000 (因為政府財報單位是千元)
            is_twse = info.get("sector") == '台灣市場 (TWSE)'
            currency = "NT$" if is_twse else "$"
            divisor = 1000 if is_twse else 1000000 

            df_fin = data.get("income_stmt", pd.DataFrame())
            
            # ── 頂部 4 個快速指標 (直接抓 DataFrame 最新一季的資料) ──
            latest_col = df_fin.columns[0] if not df_fin.empty else None
            
            def get_latest_val(row_name):
                if latest_col and row_name in df_fin.index:
                    val = df_fin.at[row_name, latest_col]
                    if pd.notna(val) and val is not None:
                        return float(val)
                return None

            gross_margin = get_latest_val('毛利率 (Gross Margin)')
            yoy = get_latest_val('營收年增率 (YoY)')
            net_margin = get_latest_val('淨利率 (Net Margin)')
            eps = get_latest_val('單季 EPS')

            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            f_col1.metric("毛利率 (最新一季)", f"{gross_margin*100:.2f}%" if gross_margin is not None else "N/A")
            f_col2.metric("營收成長 (YoY)", f"{yoy*100:.2f}%" if yoy is not None else "N/A")
            f_col3.metric("淨利率 (最新一季)", f"{net_margin*100:.2f}%" if net_margin is not None else "N/A")
            f_col4.metric(f"單季 EPS ({currency})", f"{eps:.2f}" if eps is not None else "N/A")
            
            st.markdown("#### 📄 近期財務報表 (近四個季度)")
            
            if not df_fin.empty:
                df_display = df_fin.copy()
                
                # ── 自動格式化排版 ──
                for col in df_display.columns:
                    # 1. 營收與現金流 (轉換為 M 百萬單位)
                    for row in ['營收 (Revenue)', '營運現金流 (Operating CF)', '自由現金流 (Free CF)']:
                        if row in df_display.index:
                            val = df_display.at[row, col]
                            if pd.notna(val) and val is not None:
                                df_display.at[row, col] = f"{currency} {float(val) / divisor:,.1f} M"
                            else:
                                df_display.at[row, col] = "N/A"
                                
                    # 2. 利潤率與成長率 (轉為百分比 %)
                    for row in ['營收年增率 (YoY)', '毛利率 (Gross Margin)', '淨利率 (Net Margin)']:
                        if row in df_display.index:
                            val = df_display.at[row, col]
                            if pd.notna(val) and val is not None:
                                df_display.at[row, col] = f"{float(val) * 100:.2f} %"
                            else:
                                df_display.at[row, col] = "N/A"
                                
                    # 3. EPS
                    if '單季 EPS' in df_display.index:
                        val = df_display.at['單季 EPS', col]
                        if pd.notna(val) and val is not None:
                            df_display.at['單季 EPS', col] = f"{currency} {float(val):.2f}"
                        else:
                            df_display.at['單季 EPS', col] = "N/A"

                st.dataframe(df_display, use_container_width=True)
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
