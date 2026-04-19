import streamlit as st
import pandas as pd
from datetime import datetime
import importlib
from data_engine import get_data
import notes

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
