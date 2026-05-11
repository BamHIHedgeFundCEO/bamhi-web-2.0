"""
data_engine/market/sector_engine.py
BamHI 板塊輪動與 VCP 掃描引擎 (v2.1 升級版：RRG、板塊寬度、Bug 修正)

修正紀錄 (v2.1):
  - [Bug Fix] rs_raw 量綱錯誤：改用歸一化後的 rs_line 計算 RRG 指標，確保中軸在 100
  - [Bug Fix] Sector_Breadth fillna(0) 假訊號：改用 valid_mask 遮蔽，早期無資料保留 NaN
  - [Bug Fix] VCP high_52w 改用真正的 252 交易日窗口，而非整段 period
  - [Bug Fix] calculate_inter_sector_correlation 加入 @st.cache_data 快取
  - [New]     新增 RS_Ratio / RS_Momentum (RRG 指標) 欄位
  - [New]     新增 Sector_Breadth (板塊寬度) 欄位
"""
import pandas as pd
import yfinance as yf
import numpy as np
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def calculate_sector_metrics(
    tickers,
    period="2y",
    rrg_short_window: int = 14,
    rrg_long_window: int = 50,
    raw_data: pd.DataFrame = None
):
    """
    計算自定義板塊指數、動能、RS、RRG 指標、板塊寬度與擁擠度。
    """
    if not tickers:
        return None, None

    if raw_data is None:
        all_tickers = tickers + ['SPY']
        # 獨立下載模式 (如果有提供 raw_data 就不會進來這裡)
        raw_data = yf.download(all_tickers, period=period, progress=False, auto_adjust=False)
        
    if raw_data is None or raw_data.empty:
        return None, None

    data     = raw_data['Close']
    vol_data = raw_data['Volume']
    open_data = raw_data['Open']
    high_data = raw_data['High']
    low_data  = raw_data['Low']

    if data.empty or vol_data.empty:
        return None, None

    # 過濾出實際成功下載的 tickers，避免 yfinance 漏抓或退市代碼導致 KeyError
    valid_tickers = [t for t in tickers if t in data.columns]
    if not valid_tickers:
        return None, None

    # ── 1. 等權重 OHLC 板塊指數 ──────────────────────────────────────────────
    prev_close = data[valid_tickers].shift(1)

    ret_close = ((data[valid_tickers]      - prev_close) / prev_close).clip(-0.95, 2.0)
    ret_open  = ((open_data[valid_tickers] - prev_close) / prev_close).clip(-0.95, 2.0)
    ret_high  = ((high_data[valid_tickers] - prev_close) / prev_close).clip(-0.95, 2.0)
    ret_low   = ((low_data[valid_tickers]  - prev_close) / prev_close).clip(-0.95, 2.0)

    valid_mask = data[valid_tickers].notna().sum(axis=1) > 0

    avg_ret_close = ret_close.mean(axis=1).fillna(0)
    avg_ret_open  = ret_open.mean(axis=1).fillna(0)
    avg_ret_high  = ret_high.mean(axis=1).fillna(0)
    avg_ret_low   = ret_low.mean(axis=1).fillna(0)

    sector_index = (1 + avg_ret_close).cumprod() * 100
    sector_index = sector_index.where(valid_mask, np.nan)

    prev_sector_index = sector_index.shift(1).fillna(100).where(valid_mask, np.nan)
    sector_open  = prev_sector_index * (1 + avg_ret_open)
    sector_high  = prev_sector_index * (1 + avg_ret_high)
    sector_low   = prev_sector_index * (1 + avg_ret_low)

    # ── 2. 五大核心均線 ───────────────────────────────────────────────────────
    ma10  = sector_index.rolling(10).mean()
    ma20  = sector_index.rolling(20).mean()
    ma60  = sector_index.rolling(60).mean()
    ma120 = sector_index.rolling(120).mean()
    ma200 = sector_index.rolling(200).mean()

    # ── 3. 動能 ───────────────────────────────────────────────────────────────
    m5  = sector_index.pct_change(5)  * 100
    m10 = sector_index.pct_change(10) * 100
    m20 = sector_index.pct_change(20) * 100

    # ── 4. RS Line 與斜率 ─────────────────────────────────────────────────────
    spy_price = data['SPY']
    rs_raw    = sector_index / spy_price          # 原始比值（量綱：sector/SPY）

    # 歸一化：讓第一個有效日比值 = 1.0，使 RS Line 可跨板塊比較
    if not rs_raw.dropna().empty:
        first_valid_rs = rs_raw.dropna().iloc[0]
        rs_line = rs_raw / first_valid_rs         # 以 1.0 為中軸
    else:
        rs_line = rs_raw

    rs_slope = rs_line.diff(5)

    # SPY 同基準指數化
    if not spy_price[valid_mask].dropna().empty:
        spy_base       = spy_price[valid_mask].dropna().iloc[0]
        spy_normalized = (spy_price / spy_base) * 100
        spy_normalized = spy_normalized.where(valid_mask, np.nan)
    else:
        spy_normalized = (spy_price / spy_price.iloc[0]) * 100

    # ── 5. RRG 核心指標 ───────────────────────────────────────────────────────
    # [Bug Fix v2.1] 改用 rs_line（已歸一化，以 1.0 為基準，乘 100 後 = 100 中軸）
    # 而非原始 rs_raw（量綱不同，rs_raw ≈ 0.18，導致 RS_Ratio 偏離 100）
    rs_ratio    = (rs_line.rolling(rrg_short_window).mean()
                   / rs_line.rolling(rrg_long_window).mean()) * 100

    rs_momentum = (rs_ratio / rs_ratio.rolling(rrg_short_window).mean()) * 100

    # ── 6. 板塊寬度 (Sector Breadth) ─────────────────────────────────────────
    # 向量化計算：不需要額外 for loop，利用已下載的 data[valid_tickers]
    stocks_ma20      = data[valid_tickers].rolling(20).mean()
    is_above_ma20    = data[valid_tickers] > stocks_ma20
    valid_stock_cnt  = data[valid_tickers].notna().sum(axis=1)

    sector_breadth = (
        is_above_ma20.sum(axis=1)
        / valid_stock_cnt.replace(0, np.nan)
    ) * 100

    # [Bug Fix v2.1] 改用 valid_mask 遮蔽（保留 NaN），避免前期資料不足時
    # fillna(0) 把「資料缺失」誤判為「所有股票跌破 MA20」的假訊號
    sector_breadth = sector_breadth.where(valid_mask, np.nan)

    # ── 7. 板塊擁擠度 (Dollar Volume Crowdedness) ─────────────────────────────
    dollar_volume          = data * vol_data
    sector_dollar_volume   = dollar_volume[valid_tickers].sum(axis=1)
    spy_dollar_vol_smooth  = dollar_volume['SPY'].rolling(20).mean()

    crowdedness_ratio = sector_dollar_volume / (spy_dollar_vol_smooth + 1e-9)
    crowdedness_90p   = crowdedness_ratio.rolling(250).quantile(0.9)

    # ── 7b. 機構吃貨指標：Up/Down Dollar Volume Ratio (向量化) ────────────────
    # 原理：若資金在「上漲日」的成交金額 >> 「下跌日」→ 機構正在悄悄建倉
    daily_ret    = sector_index.pct_change()
    up_mask      = (daily_ret > 0).astype(float)
    down_mask    = (daily_ret < 0).astype(float)
    up_dv_20     = (sector_dollar_volume * up_mask).rolling(20).sum()
    down_dv_20   = (sector_dollar_volume * down_mask).rolling(20).sum()
    ud_dv_ratio  = up_dv_20 / down_dv_20.replace(0, np.nan)  # >1 = 吃貨，<1 = 派發

    # ── 8. 彙整 DataFrame ─────────────────────────────────────────────────────
    df_sector = pd.DataFrame({
        'Sector_Open'   : sector_open,
        'Sector_High'   : sector_high,
        'Sector_Low'    : sector_low,
        'Sector_Close'  : sector_index,
        'Sector_Index'  : sector_index,   # 保留舊欄位名稱，避免 UI 報錯
        'MA10'          : ma10,
        'MA20'          : ma20,
        'MA60'          : ma60,
        'MA120'         : ma120,
        'MA200'         : ma200,
        'SPY_Index'     : spy_normalized,
        'M5'            : m5,
        'M10'           : m10,
        'M20'           : m20,
        'Momentum_Diff' : m5 - m20,
        'RS_Line'       : rs_line,
        'RS_Slope'      : rs_slope,
        'RS_Ratio'      : rs_ratio,       # RRG X 軸（中軸 ≈ 100）
        'RS_Momentum'   : rs_momentum,    # RRG Y 軸（中軸 ≈ 100）
        'Sector_Breadth': sector_breadth, # 板塊寬度（0–100%）
        'Crowdedness'    : crowdedness_ratio,
        'Crowdedness_90p': crowdedness_90p,
        'UD_DV_Ratio'    : ud_dv_ratio,      # 機構吃貨強度 (>1=建倉, <1=派發)
    })

    first_valid_idx = sector_index.first_valid_index()
    if first_valid_idx is not None:
        df_sector = df_sector.loc[first_valid_idx:]

    return df_sector, vol_data


@st.cache_data(ttl=3600, show_spinner=False)
def scan_vcp_candidates(tickers, period="2y", raw_data: pd.DataFrame = None):
    """VCP 掃描器：趨勢模板 + 波動收縮 + 量縮 + 大戶吃貨"""
    results     = []
    
    if raw_data is None:
        all_tickers = list(set(tickers + ['SPY']))
        data        = yf.download(all_tickers, period=period, progress=False, auto_adjust=False)
    else:
        data = raw_data

    spy_3m_ret = 0
    if isinstance(data.columns, pd.MultiIndex):
        spy_df = data.xs('SPY', level=1, axis=1).copy()
        spy_df.dropna(inplace=True)
        if len(spy_df) >= 60:
            spy_3m_ret = spy_df['Close'].pct_change(60).iloc[-1] * 100

    for ticker in tickers:
        try:
            if ticker == 'SPY':
                continue

            if isinstance(data.columns, pd.MultiIndex):
                df = data.xs(ticker, level=1, axis=1).copy()
            else:
                df = data.copy()

            df.dropna(inplace=True)
            if len(df) < 200:
                continue

            close = df['Close'].iloc[-1]
            vol   = df['Volume'].iloc[-1]

            # --- Trend Template -----------------------------------------------
            ma50  = df['Close'].rolling(50).mean().iloc[-1]
            ma150 = df['Close'].rolling(150).mean().iloc[-1]
            ma200 = df['Close'].rolling(200).mean().iloc[-1]

            # [Bug Fix v2.1] 真正的 52 周高點 (252 交易日)，而非整段 period 最高
            high_52w  = df['Close'].iloc[-252:].max()
            trend_pass = (
                close > ma150 and close > ma200
                and ma50 > ma150 and close >= (high_52w * 0.75)
            )

            # --- Volatility Contraction (v2.1: 改用相對 ATR%) ------------------
            df['TR']      = df['High'] - df['Low']
            # 「短期 ATR」 vs 「中期 ATR」：比較窗口期而非時間點，正確實腳「最近 N 日渢動明顯低於過去 20 日平均」
            atr_5d  = df['TR'].iloc[-5:].mean()    # 最近 5 日平均波動
            atr_20d = df['TR'].iloc[-20:].mean()   # 過去 20 日平均波動
            # 相對 ATR％：用股價歸一化，讓不同價位的股票可互相比較
            atr_pct_now  = (atr_5d  / close) * 100 if close > 0 else 0
            atr_pct_base = (atr_20d / close) * 100 if close > 0 else 1
            # 收縮比：< 0.7 代表波動已顯著收縮（VCP 黄金區間），> 1 代表波動擴張
            atr_contraction = atr_pct_now / atr_pct_base if atr_pct_base > 0 else 1.0
            atr_pct_now     = round(atr_pct_now, 2)

            # --- Volume Dry-up & Up/Down Volume --------------------------------
            vol_ma20 = df['Volume'].rolling(20).mean().iloc[-1]
            vol_dry  = 1 if vol < (vol_ma20 * 0.6) else 0

            df_50        = df.iloc[-50:].copy()
            df_50['Ret'] = df_50['Close'].pct_change()
            up_vol       = df_50[df_50['Ret'] > 0]['Volume'].sum()
            down_vol     = df_50[df_50['Ret'] < 0]['Volume'].sum()
            up_down_vol_ratio = up_vol / down_vol if down_vol > 0 else 0

            # --- 動能、均線乖離率 & RS vs SPY ----------------------------------
            ma20      = df['Close'].rolling(20).mean().iloc[-1]
            dist_ma20 = (close / ma20 - 1) * 100 if ma20 else 0

            m1  = df['Close'].pct_change(1).iloc[-1]  * 100
            m10 = df['Close'].pct_change(10).iloc[-1] * 100
            m20 = df['Close'].pct_change(20).iloc[-1] * 100
            m60 = df['Close'].pct_change(60).iloc[-1] * 100

            ticker_3m_ret = df['Close'].pct_change(60).iloc[-1] * 100
            rs_3m = ticker_3m_ret - spy_3m_ret if pd.notna(ticker_3m_ret) else 0

            results.append({
                "Ticker"          : ticker,
                "Price"           : round(close, 2),
                "M1"              : round(m1, 2),
                "M10"             : round(m10, 2),
                "M20"             : round(m20, 2),
                "M60"             : round(m60, 2),
                "Dist_MA20"       : round(dist_ma20, 2),
                "ATR_Pct"         : atr_pct_now,          # ATR% = ATR/Price (相對波動率)
                "ATR_Contraction" : round(atr_contraction, 2), # ATR_5d / ATR_20d (<0.7=收縮)
                "Up_Down_Vol"     : round(up_down_vol_ratio, 2),
                "RS_3M"           : round(rs_3m, 2),
                "Dist_to_High"    : f"{round((close / high_52w - 1) * 100, 1)}%",
                "Trend_Pass"      : "✅ 是" if trend_pass else "❌ 否",
                "Vol_Dry_Up"      : "✅ 是" if vol_dry  else "❌ 否",
            })
        except Exception:
            continue

    df_out = pd.DataFrame(results)
    if not df_out.empty and 'RS_3M' in df_out.columns:
        # RS_Rank: 板塊內部相對強度百分位排行 (100 = 板塊最強, 0 = 最弱)
        df_out['RS_Rank'] = df_out['RS_3M'].rank(pct=True).mul(100).round(0).astype(int)
    return df_out


@st.cache_data(ttl=3600, show_spinner=False)
def calculate_inter_sector_correlation(sector_returns_dict: dict) -> pd.DataFrame:
    """
    計算各板塊每日報酬率的相關係數矩陣，供熱力圖渲染使用。

    Parameters
    ----------
    sector_returns_dict : {'板塊名稱': pd.Series (Sector_Close)} 格式的字典

    Returns
    -------
    pd.DataFrame  相關係數矩陣
    """
    df_all = pd.DataFrame()
    for name, series in sector_returns_dict.items():
        df_all[name] = series.pct_change()

    return df_all.corr()
