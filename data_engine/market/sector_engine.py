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
    
    # 計算各股每日 OHLC 相對昨收的報酬率，並限制極端值 (防止錯價或極端單日爆擊毀掉指數)
    ret_close = ((data[tickers] - prev_close) / prev_close).clip(lower=-0.95, upper=2.0)
    ret_open = ((open_data[tickers] - prev_close) / prev_close).clip(lower=-0.95, upper=2.0)
    ret_high = ((high_data[tickers] - prev_close) / prev_close).clip(lower=-0.95, upper=2.0)
    ret_low = ((low_data[tickers] - prev_close) / prev_close).clip(lower=-0.95, upper=2.0)
    
    # 確保只有在至少有一檔股票有資料時，才開始計算指數
    valid_mask = data[tickers].notna().sum(axis=1) > 0
    
    # 取得板塊平均報酬率
    avg_ret_close = ret_close.mean(axis=1).fillna(0)
    avg_ret_open = ret_open.mean(axis=1).fillna(0)
    avg_ret_high = ret_high.mean(axis=1).fillna(0)
    avg_ret_low = ret_low.mean(axis=1).fillna(0)
    
    # 計算板塊收盤指數 (基準 100)
    sector_index = (1 + avg_ret_close).cumprod() * 100
    # 把前期完全沒有股票資料的日子設為 NaN
    sector_index = sector_index.where(valid_mask, np.nan)
    
    # 前一日板塊指數 (給 OHLC 計算用)，並剔除無效日期
    prev_sector_index = sector_index.shift(1).fillna(100).where(valid_mask, np.nan)
    
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
    # 為了避免前期大盤漲幅導致 RS Line 被嚴重壓縮，改以第一天有效的比例來歸一化
    spy_price = data['SPY']
    rs_raw = sector_index / spy_price
    
    if not rs_raw.dropna().empty:
        first_valid_rs = rs_raw.dropna().iloc[0]
        rs_line = rs_raw / first_valid_rs
    else:
        rs_line = rs_raw
        
    rs_slope = rs_line.diff(periods=5)
    
    # 把 SPY 指數也對齊到第一天有效日期
    if not spy_price[valid_mask].dropna().empty:
        spy_base = spy_price[valid_mask].dropna().iloc[0]
        spy_normalized = (spy_price / spy_base) * 100
        spy_normalized = spy_normalized.where(valid_mask, np.nan)
    else:
        spy_normalized = (spy_price / spy_price.iloc[0]) * 100
    
    # 🌟 新增 5. 計算板塊擁擠度 (Sector Crowdedness) 🌟
    # 改用 Dollar Volume (成交金額 = 收盤價 × 成交量) 來精準衡量真實資金流向
    dollar_volume = data * vol_data
    sector_dollar_volume = dollar_volume[tickers].sum(axis=1) # 板塊總金額
    
    # 為了避免 SPY 單日爆量 (如四巫日) 導致佔比失真，將大盤基準平滑化 (20日均量)
    spy_dollar_vol_smoothed = dollar_volume['SPY'].rolling(window=20).mean()
    
    # 真實佔比 = 板塊總金額 / 大盤平均基準金額
    # 加上 1e-9 防止分母為 0
    crowdedness_ratio = sector_dollar_volume / (spy_dollar_vol_smoothed + 1e-9)
    
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
    })
    
    # 不要使用 .dropna()，因為這會因為 MA200 和 Crowdedness_90p 導致前 250 天的資料被刪掉！
    # 這會讓指數從中途開始畫，導致看起來不是從 100 出發。
    # 改為：只刪除「板塊完全沒有資料」的前期日子
    first_valid_idx = sector_index.first_valid_index()
    if first_valid_idx is not None:
        df_sector = df_sector.loc[first_valid_idx:]
    
    return df_sector, vol_data

@st.cache_data(ttl=3600, show_spinner=False)
def scan_vcp_candidates(tickers, period="2y"):
    """VCP 掃描器：趨勢模板 + 波動收縮 + 量縮 + 大戶吃貨"""
    results = []
    # 配合更長時間軸，將 VCP 掃描範圍從 1y 延長至 2y，並允許自訂
    # 加入 SPY 用於計算 RS (Relative Strength)
    all_tickers = list(set(tickers + ['SPY']))
    data = yf.download(all_tickers, period=period, progress=False)
    
    # --- 優化：在迴圈外先準備好 SPY 數據與報酬率 ---
    spy_3m_ret = 0
    if isinstance(data.columns, pd.MultiIndex):
        spy_df = data.xs('SPY', level=1, axis=1).copy()
        spy_df.dropna(inplace=True)
        if len(spy_df) >= 60:
            spy_3m_ret = spy_df['Close'].pct_change(60).iloc[-1] * 100
            
    for ticker in tickers:
        try:
            if ticker == 'SPY': continue # 跳過 SPY 自己的掃描
            
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
            df['TR'] = df['High'] - df['Low']
            df['ATR_14'] = df['TR'].rolling(14).mean()
            atr = df['ATR_14'].iloc[-1]
            atr_20d_ago = df['ATR_14'].shift(20).iloc[-1]
            atr_contraction = atr / atr_20d_ago if pd.notna(atr_20d_ago) and atr_20d_ago > 0 else 1.0
            
            # --- 第三層：Volume Dry-up (量縮) & 大戶吃貨 (Up/Down Volume) ---
            vol_ma20 = df['Volume'].rolling(20).mean().iloc[-1]
            vol_dry = 1 if vol < (vol_ma20 * 0.6) else 0 # 當日量縮至 60% 以下
            
            df_50 = df.iloc[-50:].copy()
            df_50['Ret'] = df_50['Close'].pct_change()
            up_vol = df_50[df_50['Ret'] > 0]['Volume'].sum()
            down_vol = df_50[df_50['Ret'] < 0]['Volume'].sum()
            up_down_vol_ratio = up_vol / down_vol if down_vol > 0 else 0
            
            # --- 額外擴充：動能、均線乖離率與 RS vs SPY ---
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            dist_ma20 = (close / ma20 - 1) * 100 if ma20 else 0
            
            m1 = df['Close'].pct_change(1).iloc[-1] * 100
            m10 = df['Close'].pct_change(10).iloc[-1] * 100
            m20 = df['Close'].pct_change(20).iloc[-1] * 100
            m60 = df['Close'].pct_change(60).iloc[-1] * 100
            
            # RS 評分 (近 3 個月與近 6 個月相對 SPY 報酬率差值)
            ticker_3m_ret = df['Close'].pct_change(60).iloc[-1] * 100
            rs_3m = ticker_3m_ret - spy_3m_ret if pd.notna(ticker_3m_ret) else 0
            
            results.append({
                "Ticker": ticker,
                "Price": round(close, 2),
                "M1": round(m1, 2),
                "M10": round(m10, 2),
                "M20": round(m20, 2),
                "M60": round(m60, 2),
                "Dist_MA20": round(dist_ma20, 2),
                "ATR_Contraction": round(atr_contraction, 2),
                "Up_Down_Vol": round(up_down_vol_ratio, 2),
                "RS_3M": round(rs_3m, 2),
                "Dist_to_High": f"{round((close/high_52w - 1)*100, 1)}%",
                "Trend_Pass": "✅ 是" if trend_pass else "❌ 否",
                "Vol_Dry_Up": "✅ 是" if vol_dry else "❌ 否"
            })
        except Exception as e:
            continue
            
    return pd.DataFrame(results)
