import streamlit as st
import pandas as pd
import os
from datetime import datetime

@st.cache_data(ttl=3600)
def draw_ai_table(csv_path, engine_type):
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        if 'Win_Prob' in df.columns: df['Win_Prob'] = df['Win_Prob'] * 100
        
        if engine_type == "alpha":
            display_cols = ['Ticker', 'Resonance_Score', 'Win_Prob', 'Price', 'RS_Rating', 'Ov_Supply', 'POC_Dist', 'MA20_DP', 'Vol_Dry_Up', 'Turtle']
            col_config = {
                "Resonance_Score": st.column_config.ProgressColumn("🔥 共振總分", format="%.1f", min_value=0, max_value=100),
                "RS_Rating": st.column_config.NumberColumn("RS 強度", format="%.0f"),
                "Turtle": st.column_config.CheckboxColumn("海龜突破")
            }
        else: # Genesis 引擎
            display_cols = ['Ticker', 'Resonance_Score', 'Win_Prob', 'Price', 'MA_Conv', 'Vol_Z', 'Breakout', 'MA20_Slope', 'Ov_Supply', 'POC_Dist']
            col_config = {
                "Resonance_Score": st.column_config.ProgressColumn("⚡ 物理共振", format="%.1f", min_value=0, max_value=100),
                "MA_Conv": st.column_config.NumberColumn("均線糾結 %", format="%.2f%%"),
                "Vol_Z": st.column_config.NumberColumn("爆量 Z-Score", format="%.2f"),
                "Breakout": st.column_config.NumberColumn("破線位階 %", format="%.1f%%"),
                "MA20_Slope": st.column_config.NumberColumn("20MA 拐頭 %", format="%.2f%%")
            }

        common_config = {
            "Ticker": st.column_config.TextColumn("代碼"),  # 👈 把它刪掉，留這樣就好
            "Win_Prob": st.column_config.NumberColumn("🤖 AI 勝率", format="%.1f%%"),
            "Price": st.column_config.NumberColumn("價格 ($)", format="%.2f"),
            "Ov_Supply": st.column_config.NumberColumn("套牢 %", format="%.1f%%"),
            "POC_Dist": st.column_config.NumberColumn("POC 距離 %", format="%.1f%%")
        }
        col_config.update(common_config)

        st.dataframe(
            df[[c for c in display_cols if c in df.columns]],
            use_container_width=True, hide_index=True, height=500,
            column_config=col_config
        )
        st.caption(f"🔄 最後更新：{datetime.fromtimestamp(os.path.getmtime(csv_path)).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.info(f"⏳ 該引擎資料尚未產生或同步中...")
