"""技術層：週線 Stage 2 前置 / 日線 Minervini 模板 / RS / 量能標註（spec §5.4）。"""
import numpy as np
import pandas as pd

from inflection_screener import config


def weekly_pass(df: pd.DataFrame) -> bool:
    """週線三條件（全過才進日線檢查）。日線 resample 成週線。"""
    wk = df["Close"].resample("W-FRI").last().dropna()
    need = config.WEEKLY_MA_SLOW + config.WEEKLY_SLOPE_WEEKS
    if len(wk) < need:
        return False
    ma10 = wk.rolling(config.WEEKLY_MA_FAST).mean()
    ma30 = wk.rolling(config.WEEKLY_MA_SLOW).mean()
    w1 = wk.iloc[-1] > ma30.iloc[-1]
    tail = ma30.tail(config.WEEKLY_SLOPE_WEEKS).to_numpy()
    if np.isnan(tail).any():
        return False
    slope = np.polyfit(np.arange(len(tail)), tail, 1)[0]
    w2 = slope > 0
    w3 = ma10.iloc[-1] > ma30.iloc[-1]
    return bool(w1 and w2 and w3)


def daily_template_pass(df: pd.DataFrame) -> bool:
    """日線趨勢模板 D1–D5（Minervini，五條全過為硬閘門）。"""
    close = df["Close"]
    if len(close) < 200 + config.MA200_RISING_DAYS:
        return False
    ma50 = close.rolling(50).mean()
    ma150 = close.rolling(150).mean()
    ma200 = close.rolling(200).mean()
    c = close.iloc[-1]
    d1 = c > ma50.iloc[-1] > ma150.iloc[-1] > ma200.iloc[-1]
    d2 = ma200.iloc[-1] > ma200.iloc[-1 - config.MA200_RISING_DAYS]
    d3 = ma150.iloc[-1] > ma200.iloc[-1]
    win52 = close.tail(252)
    d4 = c >= win52.min() * config.LOW_52W_MULT
    d5 = c >= win52.max() * config.HIGH_52W_MULT
    return bool(d1 and d2 and d3 and d4 and d5)


def rs_raw(close: pd.Series, spy: pd.Series) -> float:
    """RS_raw = Σ w_k × (個股 ret_k − SPY ret_k)。窗口不足 → NaN。"""
    idx = close.index.intersection(spy.index)
    c, s = close.loc[idx], spy.loc[idx]
    if len(c) < max(config.RS_WEIGHTS) + 1:
        return np.nan
    total = 0.0
    for k, w in config.RS_WEIGHTS.items():
        r_stock = c.iloc[-1] / c.iloc[-1 - k] - 1
        r_spy = s.iloc[-1] / s.iloc[-1 - k] - 1
        total += w * (r_stock - r_spy)
    return float(total)


def rs_line_lead_flag(close: pd.Series, spy: pd.Series) -> bool:
    """flag_rs_lead 🔺：RS_Line 創 126 日新高 且 價格未創 126 日新高（最純左側訊號）。"""
    idx = close.index.intersection(spy.index)
    c, s = close.loc[idx], spy.loc[idx]
    n = config.RS_LINE_HIGH_DAYS
    if len(c) < n:
        return False
    rs_line = c / s
    rs_new_high = rs_line.iloc[-1] >= rs_line.tail(n).max()
    price_new_high = c.iloc[-1] >= c.tail(n).max()
    return bool(rs_new_high and not price_new_high)


def volume_annotations(df: pd.DataFrame) -> dict:
    """量能標註（不淘汰）：vol_confirm / obv_confirm / vcp_proxy。"""
    close, vol = df["Close"], df["Volume"]
    high, low = df["High"], df["Low"]
    out = {"vol_confirm": False, "obv_confirm": False, "vcp_proxy": False}
    if len(close) < config.BREAKOUT_HIGH_DAYS + config.BREAKOUT_LOOKBACK_DAYS:
        return out

    # vol_confirm：近 20 日內收盤創 63 日新高的最近一日，其量 ≥ 1.5 × 50 日均量
    roll_max = close.rolling(config.BREAKOUT_HIGH_DAYS).max()
    is_breakout = close >= roll_max
    recent = is_breakout.tail(config.BREAKOUT_LOOKBACK_DAYS)
    if recent.any():
        d = recent[recent].index[-1]
        avg_vol = vol.rolling(config.VOL_AVG_DAYS).mean()
        if pd.notna(avg_vol.loc[d]) and avg_vol.loc[d] > 0:
            out["vol_confirm"] = bool(vol.loc[d] >= config.VOL_CONFIRM_MULT * avg_vol.loc[d])

    # obv_confirm：OBV > OBV 的 MA20 且 OBV 創 63 日新高
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * vol).cumsum()
    obv_ma = obv.rolling(config.OBV_MA_DAYS).mean()
    if pd.notna(obv_ma.iloc[-1]):
        out["obv_confirm"] = bool(
            obv.iloc[-1] > obv_ma.iloc[-1]
            and obv.iloc[-1] >= obv.tail(config.OBV_HIGH_DAYS).max()
        )

    # vcp_proxy：ATR(14) 相對 60 日前收斂 ≥ 30%
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    atr = tr.rolling(config.VCP_ATR_DAYS).mean()
    if len(atr) > config.VCP_LOOKBACK_DAYS:
        atr_then = atr.iloc[-1 - config.VCP_LOOKBACK_DAYS]
        atr_now = atr.iloc[-1]
        if pd.notna(atr_then) and atr_then > 0 and pd.notna(atr_now):
            out["vcp_proxy"] = bool((atr_then - atr_now) / atr_then >= config.VCP_CONTRACTION_MIN)
    return out


def evaluate(df: pd.DataFrame, spy_close: pd.Series) -> dict:
    """單檔完整技術評估（僅對左側池成員呼叫）。"""
    wk = weekly_pass(df)
    daily = daily_template_pass(df) if wk else False  # 週線全過才進日線（spec §5.4）
    return {
        "weekly_pass": wk,
        "trend_template_pass": daily,
        "rs_raw": rs_raw(df["Close"], spy_close),
        "rs_line_high": rs_line_lead_flag(df["Close"], spy_close),
        **volume_annotations(df),
    }
