"""
data_engine/market/darkpool.py
暗池異常資金監控引擎 (FINRA + Polygon Tick Test) - 靜態唯讀後端
"""
import streamlit as st
import pandas as pd
import os

# 設定專案根目錄
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RESULTS_PATH = os.path.join(DATA_DIR, 'darkpool_results.csv')

@st.cache_data(ttl=300, show_spinner=False)
def get_darkpool_surge_list() -> pd.DataFrame:
    """
    讀取每日自動化 Pipeline (GitHub Actions 或本機排程) 
    產出的暗池爆發異常名單 (Surge Top 50)
    """
    if not os.path.exists(RESULTS_PATH):
        return pd.DataFrame()
        
    try:
        df = pd.read_csv(RESULTS_PATH)
        return df
    except Exception as e:
        print(f"讀取 darkpool_results.csv 失敗: {e}")
        return pd.DataFrame()

