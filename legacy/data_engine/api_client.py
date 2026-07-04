import requests
import pandas as pd
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000/api"

@st.cache_data(ttl=60, show_spinner=False)
def fetch_sector_metrics_from_api(sector_name: str, period: str = "1y"):
    """
    嘗試從 FastAPI 後端取得板塊指標
    如果後端沒開或發生錯誤，回傳 None
    """
    try:
        url = f"{API_BASE_URL}/sector/{sector_name}"
        params = {"period": period}
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json().get("data", [])
            if data:
                df = pd.DataFrame(data)
                # 將 Date 轉回 datetime 並設為 index (如果存在的的話)
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df.set_index('Date')
                return df
    except requests.exceptions.RequestException:
        pass # API 沒開或斷線，靜默失敗，退回本地計算
    
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vcp_from_api(sector_name: str, period: str = "1y"):
    """
    嘗試從 FastAPI 後端取得 VCP 掃描結果
    如果後端沒開或發生錯誤，回傳 None
    """
    try:
        url = f"{API_BASE_URL}/vcp/{sector_name}"
        params = {"period": period}
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json().get("data", [])
            if data:
                return pd.DataFrame(data)
    except requests.exceptions.RequestException:
        pass # API 沒開或斷線
        
    return None
