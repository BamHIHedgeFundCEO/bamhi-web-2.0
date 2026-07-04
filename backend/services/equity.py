"""個股深度檔案引擎 (移植自 data_engine/equity.py)。

yfinance (K線 + 技術指標)。純 pandas/numpy，不依賴 streamlit。
公司基本面 (FMP) 功能已於 2026-07-04 移除。
"""
import time

import numpy as np
import pandas as pd

_CACHE: dict = {}
_TTL = 3600
_CACHE_MAX = 200


def _sanitize(obj):
    if isinstance(obj, float):
        return None if not np.isfinite(obj) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _compute_indicators(hist: pd.DataFrame) -> pd.DataFrame:
    for ma in (5, 10, 20, 60, 120, 240):
        hist[f"MA_{ma}"] = hist["Close"].rolling(ma).mean()
    hist["Max_20"] = hist["High"].shift(1).rolling(20).max()
    hist["Min_20"] = hist["Low"].shift(1).rolling(20).min()
    hist["Signal_Up"] = (hist["Close"] > hist["Max_20"]) & (hist["Close"].shift(1) <= hist["Max_20"].shift(1))
    hist["Signal_Down"] = (hist["Close"] < hist["Min_20"]) & (hist["Close"].shift(1) >= hist["Min_20"].shift(1))

    try:
        typical = (hist["High"] + hist["Low"] + hist["Close"]) / 3
        flow = typical * hist["Volume"]
        delta = typical.diff()
        pos = pd.Series(np.where(delta > 0, flow, 0), index=hist.index).rolling(14).sum()
        neg = pd.Series(np.where(delta < 0, flow, 0), index=hist.index).rolling(14).sum()
        with np.errstate(divide="ignore", invalid="ignore"):
            hist["MFI"] = (100 - (100 / (1 + pos / neg))).fillna(50)
        exp12 = hist["Close"].ewm(span=12, adjust=False).mean()
        exp26 = hist["Close"].ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        hist["MACD_Hist"] = macd - macd.ewm(span=9, adjust=False).mean()
        hist["Bias"] = (hist["Close"] - hist["MA_60"]) / hist["MA_60"] * 100 if "MA_60" in hist else 0
        lookback = min(250, len(hist))
        if lookback > 10:
            def rank(s):
                return s.rolling(lookback, min_periods=1).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False)
            hist["Composite"] = (rank(hist["MFI"]) + rank(hist["MACD_Hist"]) + rank(hist["Bias"])) / 3
        else:
            hist["Composite"] = 50
    except Exception as e:
        print(f"指標計算失敗: {e}")
    return hist


def get_profile(ticker: str, period: str = "2y", interval: str = "1d"):
    ticker = ticker.upper()
    if interval == "1h" and period in ("5y", "10y", "max"):
        period = "2y"
    key = f"{ticker}:{period}:{interval}"
    cached = _CACHE.get(key)
    if cached and time.time() - cached["ts"] < _TTL:
        return cached["data"]

    import yfinance as yf

    # 不要自帶 session：yfinance 1.2+ 內部用 curl_cffi 並拒收 requests.Session，
    # 讓它自行處理（預設 impersonate chrome，反封鎖比手動 User-Agent 更佳）。
    stock = yf.Ticker(ticker)
    hist = pd.DataFrame()
    for attempt in range(3):
        try:
            hist = stock.history(period=period, interval=interval)
            if not hist.empty:
                break
        except Exception as e:
            print(f"[equity] yfinance error {ticker} attempt {attempt+1}: {e}")
        if attempt < 2:
            time.sleep(2 ** attempt)
    if hist.empty:
        print(f"[equity] empty history for {ticker} after 3 attempts")
        return None

    hist = _compute_indicators(hist)
    close_valid = hist["Close"].dropna()
    info = {"currentPrice": float(close_valid.iloc[-1]) if len(close_valid) > 0 else float("nan")}
    info["previousClose"] = float(close_valid.iloc[-2]) if len(close_valid) > 1 else info["currentPrice"]

    # 趨勢 / 訊號燈號
    last = hist.iloc[-1]
    ma20, ma60, ma120 = last.get("MA_20", 0), last.get("MA_60", 0), last.get("MA_120", 0)
    if ma20 > ma60 > ma120:
        trend = "多頭 🐂 (均線發散)"
    elif ma20 < ma60 < ma120:
        trend = "空頭 🐻 (均線蓋頭)"
    else:
        trend = "盤整震盪 ⚖️ (均線糾結)"
    comp = float(last.get("Composite", 50)) if pd.notna(last.get("Composite", 50)) else 50
    signal = "🔴 過熱警示 (賣訊)" if comp > 75 else "🟢 超跌機會 (買訊)" if comp < 25 else "⚪ 觀望持有"

    dates = [d.strftime("%Y-%m-%d %H:%M") if interval == "1h" else d.strftime("%Y-%m-%d") for d in hist.index]
    def _safe(v, dg):
        try:
            f = float(v)
            return None if not np.isfinite(f) else round(f, dg)
        except Exception:
            return None
    def col(c, dg=4):
        return [_safe(v, dg) for v in hist[c]] if c in hist else []

    cur = info["currentPrice"]
    prev = info["previousClose"]

    data = {
        "ticker": ticker,
        "price": {"current": round(cur, 2), "prev_close": round(prev, 2),
                  "change": round(cur - prev, 2), "change_pct": round((cur - prev) / prev * 100, 2) if prev else 0},
        "trend_status": trend, "signal_status": signal, "composite": round(comp, 1),
        "chart": {
            "dates": dates, "interval": interval,
            "candle": [[_safe(o, 3), _safe(cl, 3), _safe(lo, 3), _safe(hi, 3)]
                       for o, cl, lo, hi in zip(hist["Open"], hist["Close"], hist["Low"], hist["High"])],
            "ma": {f"MA{w}": col(f"MA_{w}") for w in (5, 10, 20, 60, 120, 240)},
            "composite": col("Composite", 2),
            "signals_up": [dates[i] for i, v in enumerate(hist["Signal_Up"]) if v],
            "signals_down": [dates[i] for i, v in enumerate(hist["Signal_Down"]) if v],
        },
    }
    data = _sanitize(data)
    if len(_CACHE) >= _CACHE_MAX:
        oldest = min(_CACHE, key=lambda k: _CACHE[k]["ts"])
        del _CACHE[oldest]
    _CACHE[key] = {"ts": time.time(), "data": data}
    return data
