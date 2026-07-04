import streamlit as st
import glob
import re
from components.ai_models import draw_ai_table
import os
import pandas as pd
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
    

    # 🌟 核心修改：強制切斷，只保留最近 5 天的歷史紀錄
    dates = dates[:5]
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
        
        # ==========================================
        # 🌊 Alpha 動態數據儀表板 (自動化計算)
        # ==========================================
       
        
        if os.path.exists(alpha_path):
            try:
                # 讀取 CSV 資料計算即時指標
                df_alpha = pd.read_csv(alpha_path)
                
                total_picks = len(df_alpha)
                if total_picks > 0:
                    avg_win_prob = df_alpha['Win_Prob'].mean() * 100
                    # 確保 CSV 裡有 Resonance_Score 欄位
                    max_resonance = df_alpha['Resonance_Score'].max() if 'Resonance_Score' in df_alpha.columns else 0
                else:
                    avg_win_prob = 0
                    max_resonance = 0
                
                # 顯示動態戰報看板
                st.markdown("#### 📊 今日戰況速覽 (🌊 Alpha)")
                col1, col2, col3 = st.columns(3)
                col1.metric("今日狙擊標的數", f"{total_picks} 檔")
                col2.metric("榜首最高共振分", f"{max_resonance:.1f} 分" if total_picks > 0 else "N/A")
                col3.metric("入榜平均勝率", f"{avg_win_prob:.1f}%" if total_picks > 0 else "N/A")
                
            except Exception as e:
                st.warning(f"無法載入 Alpha 統計數據: {e}")
        else:
            st.info("尚無今日 Alpha 戰報數據。")

        st.markdown("---")
        st.markdown(f"#### 🎯 AI 嚴選名單 🌊 Alpha 引擎 {display_date}")
        # 👇 調用共用元件渲染表格
        draw_ai_table(alpha_path, engine_type="alpha")

        # ==========================================
        # 📥 下載 Alpha 戰報 CSV
        # ==========================================
        st.markdown("<br>", unsafe_allow_html=True)
        if os.path.exists(alpha_path):
            with open(alpha_path, "rb") as file:
                st.download_button(
                    label=f"📥 下載 Alpha 戰報 CSV",
                    data=file,
                    file_name=f"BamHI_Alpha_Report_{display_date.replace('/', '-')}.csv",
                    mime="text/csv",
                    key="download_alpha"
                )
    with tab_m2:
        st.subheader("Genesis 底部翻轉模型 (V1.0)")
        st.markdown("**模型架構:** `LightGBM Classifier` + `Optuna 最佳化`")
        st.markdown("**訓練目標:** 專攻均線極度糾結、底部帶量突破的潛在轉折股，追求極致盈虧比。")
        
        # ==========================================
        # 🌟 全新動態數據儀表板 (直接從當天的 CSV 抓資料算，零人工維護)
        # ==========================================
        
        
        if os.path.exists(genesis_path):
            try:
                df = pd.read_csv(genesis_path)
                
                # 計算當日即時戰況
                total_picks = len(df)
                if total_picks > 0:
                    avg_win_prob = (df['Win_Prob'].mean() * 100)
                    max_resonance = df['Resonance_Score'].max()
                else:
                    avg_win_prob = 0
                    max_resonance = 0
                
                # 顯示動態數據看板
                st.markdown("#### 📊 今日戰況速覽")
                col1, col2, col3 = st.columns(3)
                col1.metric("今日狙擊標的數", f"{total_picks} 檔")
                col2.metric("榜首最高共振分", f"{max_resonance:.1f} 分" if total_picks > 0 else "N/A")
                col3.metric("入榜平均勝率", f"{avg_win_prob:.1f}%" if total_picks > 0 else "N/A")
                
            except Exception as e:
                st.warning(f"無法載入今日統計數據: {e}")
        else:
            st.info("尚無今日戰報數據。")

        # ==========================================
        # 🎯 AI 表格與下載按鈕 (保持不變)
        # ==========================================
        st.markdown("---")
        st.markdown(f"#### 🎯 AI 嚴選名單 🌋 Genesis 引擎 {display_date}")
        draw_ai_table(genesis_path, engine_type="genesis")

        st.markdown("<br>", unsafe_allow_html=True)
        if os.path.exists(genesis_path):
            with open(genesis_path, "rb") as file:
                st.download_button(
                    label=f"📥 下載 Genesis 戰報 CSV",
                    data=file,
                    file_name=f"BamHI_Genesis_Report_{display_date.replace('/', '-')}.csv",
                    mime="text/csv",
                    key="download_genesis"
                )


    with tab_backtest:
        st.subheader("🚧 回測系統建置中")
        st.info("未來這裡將會串接 BamHI 模型的歷史權益曲線 (Equity Curve)、最大回撤 (Max Drawdown) 與夏普值 (Sharpe Ratio) 等專業量化回測數據。")
