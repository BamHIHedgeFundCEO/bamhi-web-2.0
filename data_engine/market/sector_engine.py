"""
data_engine/market/sector_engine.py
BamHI 板塊輪動與 VCP 掃描引擎
"""
import pandas as pd
import yfinance as yf
import numpy as np
import streamlit as st

@st.cache_data(ttl=3600, show_spinner=False)
def calculate_sector_metrics(tickers, period="2y"):
    """計算自定義板塊指數、動能與擁擠度"""
    if not tickers:
        return None, None
        
    all_tickers = tickers + ['SPY']
    # 🚨 優化效能：一次下載 OHLCV
    raw_data = yf.download(all_tickers, period=period, progress=False)
    if raw_data.empty: return None, None
    
    data = raw_data['Close']
    vol_data = raw_data['Volume']
    open_data = raw_data['Open']
    high_data = raw_data['High']
    low_data = raw_data['Low']
    
    if data.empty or vol_data.empty: return None, None
    
    # 1. 構建「等權重 OHLC 板塊指數」
    prev_close = data[tickers].shift(1)
    
    # 計算各股每日 OHLC 相對昨收的報酬率
    ret_close = (data[tickers] - prev_close) / prev_close
    ret_open = (open_data[tickers] - prev_close) / prev_close
    ret_high = (high_data[tickers] - prev_close) / prev_close
    ret_low = (low_data[tickers] - prev_close) / prev_close
    
    # 取得板塊平均報酬率
    avg_ret_close = ret_close.mean(axis=1).fillna(0)
    avg_ret_open = ret_open.mean(axis=1).fillna(0)
    avg_ret_high = ret_high.mean(axis=1).fillna(0)
    avg_ret_low = ret_low.mean(axis=1).fillna(0)
    
    # 計算板塊收盤指數 (基準 100)
    sector_index = (1 + avg_ret_close).cumprod() * 100
    prev_sector_index = sector_index.shift(1).fillna(100)
    
    # 計算板塊 OHLC
    sector_open = prev_sector_index * (1 + avg_ret_open)
    sector_high = prev_sector_index * (1 + avg_ret_high)
    sector_low = prev_sector_index * (1 + avg_ret_low)
    
    # 2. 計算五大核心均線 (MA10, MA20, MA60, MA120, MA200)
    ma10 = sector_index.rolling(window=10).mean()
    ma20 = sector_index.rolling(window=20).mean()
    ma60 = sector_index.rolling(window=60).mean()
    ma120 = sector_index.rolling(window=120).mean()
    ma200 = sector_index.rolling(window=200).mean()
    
    # 3. 計算動能 ($M_5$, $M_{10}$, $M_{20}$)
    m5 = sector_index.pct_change(periods=5) * 100
    m10 = sector_index.pct_change(periods=10) * 100
    m20 = sector_index.pct_change(periods=20) * 100
    
    # 4. 計算 RS Line 與 5日斜率
    spy_normalized = (data['SPY'] / data['SPY'].iloc[0]) * 100
    rs_line = sector_index / spy_normalized
    rs_slope = rs_line.diff(periods=5)
    
    # 🌟 新增 5. 計算板塊擁擠度 (Sector Crowdedness) 🌟
    # 改用 Dollar Volume (成交金額 = 收盤價 × 成交量) 來精準衡量真實資金流向
    dollar_volume = data * vol_data
    
    sector_dollar_volume = dollar_volume[tickers].sum(axis=1) # 板塊總金額
    spy_dollar_volume = dollar_volume['SPY']                  # 大盤總金額
    crowdedness_ratio = sector_dollar_volume / spy_dollar_volume # 資金佔比
    
    # 計算過去 250 個交易日的 90% 分位數
    crowdedness_90p = crowdedness_ratio.rolling(window=250).quantile(0.9)
    
    # 6. 彙整板塊 DataFrame
    df_sector = pd.DataFrame({
        'Sector_Open': sector_open,
        'Sector_High': sector_high,
        'Sector_Low': sector_low,
        'Sector_Close': sector_index,
        'Sector_Index': sector_index, # 保留舊欄位以防報錯
        'MA10': ma10,
        'MA20': ma20,
        'MA60': ma60,
        'MA120': ma120,
        'MA200': ma200,
        'SPY_Index': spy_normalized,
        'M5': m5,
        'M10': m10,
        'M20': m20,
        'Momentum_Diff': m5 - m20,
        'RS_Line': rs_line,
        'RS_Slope': rs_slope,
        'Crowdedness': crowdedness_ratio,
        'Crowdedness_90p': crowdedness_90p
    }).dropna()
    
    return df_sector, vol_data

@st.cache_data(ttl=3600, show_spinner=False)
def scan_vcp_candidates(tickers, period="2y"):
    """VCP 掃描器：趨勢模板 + 波動收縮 + 量縮"""
    results = []
    # 配合更長時間軸，將 VCP 掃描範圍從 1y 延長至 2y，並允許自訂
    data = yf.download(tickers, period=period, progress=False)
    
    for ticker in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                df = data.xs(ticker, level=1, axis=1).copy()
            else:
                df = data.copy()
                
            df.dropna(inplace=True)
            if len(df) < 200: continue
            
            close = df['Close'].iloc[-1]
            vol = df['Volume'].iloc[-1]
            
            # --- 第一層：Trend Template (趨勢過濾) ---
            ma50 = df['Close'].rolling(50).mean().iloc[-1]
            ma150 = df['Close'].rolling(150).mean().iloc[-1]
            ma200 = df['Close'].rolling(200).mean().iloc[-1]
            high_52w = df['Close'].max()
            
            # 判斷是否符合趨勢條件
            trend_pass = (close > ma150 and close > ma200 and ma50 > ma150 and close >= (high_52w * 0.75))
            
            # --- 第二層：Volatility Contraction (波動收縮) ---
            # 簡化版：計算近 20 日 ATR，並觀察最新一週波幅是否小於上一週
            df['TR'] = df['High'] - df['Low']
            atr = df['TR'].rolling(14).mean().iloc[-1]
            
            # --- 第三層：Volume Dry-up (量縮) ---
            vol_ma20 = df['Volume'].rolling(20).mean().iloc[-1]
            vol_dry = 1 if vol < (vol_ma20 * 0.6) else 0 # 當日量縮至 60% 以下
            
            results.append({
                "Ticker": ticker,
                "Price": round(close, 2),
                "Dist_to_High": f"{round((close/high_52w - 1)*100, 1)}%",
                "Trend_Pass": "✅ 是" if trend_pass else "❌ 否",
                "ATR": round(atr, 2),
                "Vol_Dry_Up": "✅ 是" if vol_dry else "❌ 否"
            })
        except Exception as e:
            continue
            
    return pd.DataFrame(results)
