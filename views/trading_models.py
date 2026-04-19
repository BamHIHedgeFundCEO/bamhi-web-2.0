import streamlit as st
import glob
import re
from components.ai_models import draw_ai_table

# ============== 🤖 交易模型分頁 ==============
def render_trading_models():
    st.title("🤖 BamHI 量化模型庫與每日戰報")
    st.markdown("揭開 BamHI 交易決策背後的 AI 大腦，並展示兩大引擎每日最新（或歷史）輸出的狙擊名單。")
    
    # ==========================================
    # 🕰️ 新增：時光機日期選擇器
    # ==========================================
    st.markdown("### 📅 戰報日期選擇")
    
    # 自動掃描 data 資料夾內的歷史檔案 (利用正則表達式抓取檔名裡的日期)
    history_files = glob.glob("data/BamHI_Dashboard_20*.csv")
    dates = []
    for f in history_files:
        match = re.search(r"(\d{8})", f)
        if match:
            date_str = match.group(1)
            # 格式化為 YYYY-MM-DD 比較好看
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            dates.append((formatted_date, date_str))
            
    # 依照日期由新到舊排序
    dates = sorted(dates, key=lambda x: x[0], reverse=True)
    
    # 建立下拉選單選項 (預設第一項永遠是 Latest)
    options = ["🔥 最新戰報 (Latest)"] + [f"🕰️ 歷史紀錄: {d[0]}" for d in dates]
    
    # 畫出下拉式選單
    selected_option = st.selectbox("請選擇要查看的 AI 榜單日期：", options, label_visibility="collapsed")
    
    # 🧠 根據使用者的選擇，決定要讀取哪兩個 CSV 檔案
    if selected_option == "🔥 最新戰報 (Latest)":
        alpha_path = "data/BamHI_Dashboard_Latest.csv"
        genesis_path = "data/BamHI_Genesis_Dashboard_Latest.csv"
        display_date = "(Latest)"
    else:
        # 抽出選擇的 YYYYMMDD
        selected_date_raw = dates[options.index(selected_option) - 1][1]
        alpha_path = f"data/BamHI_Dashboard_{selected_date_raw}.csv"
        genesis_path = f"data/BamHI_Genesis_Dashboard_{selected_date_raw}.csv"
        display_date = selected_option.replace("🕰️ 歷史紀錄: ", "")
        
    st.divider()

    # ==========================================
    # 📊 雙引擎展示區 (Tabs)
    # ==========================================
    tab_m1, tab_m2, tab_backtest = st.tabs(["🌊 Alpha 趨勢大腦", "🌋 Genesis 創世紀大腦", "📈 歷史回測績效"])

    with tab_m1:
        st.subheader("Alpha 趨勢追蹤模型 (V7.3)")
        st.markdown("**模型架構:** `LightGBM Classifier` + `Optuna 最佳化`")
        st.markdown("**訓練目標:** 尋找均線多頭排列、準備進入主升段的強勢股，目標捕獲 10% 波段利潤。")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("歷史驗證 AUC", "0.825")
        col2.metric("模型深度 (Max Depth)", "4")
        col3.metric("訓練樣本數", "15,000+")
        
        st.markdown("#### 🧠 核心決策特徵權重 (Feature Importance)")
        st.progress(85, text="1. RSI 強弱指標 (RSI)")
        st.progress(72, text="2. 距離 52 週高點比例 (Dist_52W_High)")
        st.progress(68, text="3. 相對大盤強度 (RS_Rating)")
        st.progress(55, text="4. 20MA 未來扣抵推力 (MA20_DP)")
        
        st.markdown("---")
        st.markdown(f"#### 🎯 AI 嚴選名單 🌊 Alpha 引擎 {display_date}")
        # 👇 直接把動態路徑傳進去
        draw_ai_table(alpha_path, engine_type="alpha")

    with tab_m2:
        st.subheader("Genesis 底部翻轉模型 (V1.0)")
        st.markdown("**模型架構:** `LightGBM Classifier`")
        st.markdown("**訓練目標:** 專攻均線極度糾結、底部帶量突破的潛在轉折股，追求極致盈虧比。")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("歷史驗證 AUC", "0.798")
        col2.metric("均線糾結容忍度", "< 15%")
        col3.metric("底部爆量要求", "Z-Score > 1.5")
        
        st.markdown("#### 🧠 核心決策特徵權重 (Feature Importance)")
        st.progress(88, text="1. 均線糾結度 (MA_Convergence_Ratio)")
        st.progress(76, text="2. 底部爆量 Z-Score (Vol_Z_Score)")
        st.progress(70, text="3. 波動率壓縮 (ATR_Pct)")
        st.progress(62, text="4. 上方套牢籌碼比例 (Overhead_Supply_Ratio)")
        
        st.markdown("---")
        st.markdown(f"#### 🎯 AI 嚴選名單 🌋 Genesis 引擎 {display_date}")
        # 👇 直接把動態路徑傳進去
        draw_ai_table(genesis_path, engine_type="genesis")

    with tab_backtest:
        st.subheader("🚧 回測系統建置中")
        st.info("未來這裡將會串接 BamHI 模型的歷史權益曲線 (Equity Curve)、最大回撤 (Max Drawdown) 與夏普值 (Sharpe Ratio) 等專業量化回測數據。")
