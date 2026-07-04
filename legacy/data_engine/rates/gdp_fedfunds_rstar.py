"""
data_engine/rates/gdp_fedfunds_rstar.py
功能：讀取 CSV 並繪製「三合一」對比圖表
"""
import plotly.graph_objects as go
from datetime import datetime
import pandas as pd
from data_engine import load_csv 

def fetch_data(ticker: str):
    # 讀取一目瞭然的 CSV 檔案
    df = load_csv("gdp_fedfunds_rstar.csv")
    if df is None: return None

    # 取出有效歷史資料，容忍 r_star 不存在的情況
    cols_to_extract = ["date", "GDP_Growth", "FEDFUNDS"]
    if "r_star" in df.columns:
        cols_to_extract.append("r_star")
        
    history = df[cols_to_extract].copy()
    
    # 選定一個主指標作為最新數值的代表 (優先顯示 r-star，若無則顯示名目利率)
    if "r_star" in df.columns and not df["r_star"].dropna().empty:
        series = df["r_star"].dropna()
    else:
        series = df["FEDFUNDS"].dropna()

    history["value"] = series.values if len(series) == len(history) else None # 為了相容格式
    
    current_val = float(series.iloc[-1]) if len(series) > 0 else 0
    change_raw = current_val - float(series.iloc[-2]) if len(series) > 1 else 0

    return {"value": current_val, "change_raw": change_raw, "history": history}

def plot_chart(df_filtered, item):
    fig = go.Figure()

    # 🔵 藍色實線：名目 GDP 成長率 (g)
    fig.add_trace(go.Scatter(
        x=df_filtered["date"], y=df_filtered["GDP_Growth"],
        mode="lines", name="名目 GDP 成長率 (g)",
        line=dict(color="#58a6ff", width=2.5) # GitHub 藍
    ))

    # 🟢 綠色虛線：名目利率 (原本的聯邦基金利率)
    fig.add_trace(go.Scatter(
        x=df_filtered["date"], y=df_filtered["FEDFUNDS"],
        mode="lines", name="名目利率 (i)",
        line=dict(color="#3fb950", width=2.2, dash="dash") # GitHub 綠
    ))

    # 🟡 黃色點線：r-star 自然利率 (r*)
    if "r_star" in df_filtered.columns:
        fig.add_trace(go.Scatter(
            x=df_filtered["date"], y=df_filtered["r_star"],
            mode="lines", name="自然利率 (r-star)",
            connectgaps=True, # 修正季頻率資料在月頻率表格中斷線畫不出來的問題
            line=dict(color="#f1c40f", width=1.5, dash="dot") # 經典黃
        ))

    # 加上衰退陰影
    recessions = [
        (datetime(1990, 7, 1), datetime(1991, 3, 31)),
        (datetime(2001, 3, 1), datetime(2001, 11, 30)),
        (datetime(2007, 12, 1), datetime(2009, 6, 30)),
        (datetime(2020, 2, 1), datetime(2020, 4, 30)),
    ]
    
    start, end = df_filtered["date"].min(), df_filtered["date"].max()
    for s_rec, e_rec in recessions:
        x0, x1 = max(s_rec, start), min(e_rec, end)
        if x0 < x1:
            fig.add_shape(
                type="rect", xref="x", yref="paper", 
                x0=x0, x1=x1, y0=0, y1=1, 
                fillcolor="rgba(127, 140, 141, 0.25)", line=dict(width=0), layer="below"
            )

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(22, 27, 34, 0.9)",
        font=dict(color="#c9d1d9", size=12), margin=dict(l=50, r=30, t=40, b=50),
        xaxis=dict(gridcolor="#30363d", showgrid=True), 
        yaxis=dict(title="百分比 (%)", gridcolor="#30363d", showgrid=True, dtick=2), 
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=450
    )
    
    return fig
