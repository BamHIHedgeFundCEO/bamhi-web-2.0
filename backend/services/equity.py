"""個股深度檔案引擎 (移植自 data_engine/equity.py)。

yfinance (K線 + 技術指標) + FMP (美股基本面/財報) / FinMind (台股財報)。
純 pandas/numpy，不依賴 streamlit。FMP 金鑰改讀環境變數。
"""
import os
import time

import numpy as np
import pandas as pd
import requests

FMP_API_KEY = os.getenv("FMP_API_KEY", "")

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


def _fmp_fundamentals(ticker: str, info: dict) -> None:
    try:
        p = requests.get(f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={FMP_API_KEY}", timeout=10).json()
        if p:
            p = p[0] if isinstance(p, list) else p
            info.update({"shortName": p.get("companyName", ticker), "sector": p.get("sector", "N/A"),
                         "industry": p.get("industry", "N/A"), "longBusinessSummary": p.get("description", "暫無公司業務介紹。"),
                         "website": p.get("website", "N/A"), "fullTimeEmployees": p.get("fullTimeEmployees", "N/A"),
                         "marketCap": p.get("mktCap", 0)})
    except Exception as e:
        print(f"FMP 基本資料失敗: {e}")



def _translate_zh(text: str) -> str | None:
    """將英文公司簡介翻為繁體中文（對應 Streamlit deep_translator）。失敗回 None。"""
    if not text or text == "暫無公司業務介紹。":
        return None
    try:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="auto", target="zh-TW").translate(text[:4900])
    except Exception as e:
        print(f"翻譯失敗，退回原文: {e}")
        return None


def get_profile(ticker: str, period: str = "2y", interval: str = "1d"):
    ticker = ticker.upper()
    if interval == "1h" and period in ("5y", "10y", "max"):
        period = "2y"
    key = f"{ticker}:{period}:{interval}"
    cached = _CACHE.get(key)
    if cached and time.time() - cached["ts"] < _TTL:
        return cached["data"]

    import yfinance as yf

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    stock = yf.Ticker(ticker, session=session)
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
    _fmp_fundamentals(ticker, info)

    if "previousClose" not in info:
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
    mc = info.get("marketCap") or 0

    data = {
        "ticker": ticker, "company_name": info.get("shortName", ticker),
        "sector": info.get("sector", "N/A"), "industry": info.get("industry", "N/A"),
        "employees": info.get("fullTimeEmployees", "N/A"), "website": info.get("website", "N/A"),
        "summary": info.get("longBusinessSummary", "暫無公司業務介紹。"),
        "summary_zh": _translate_zh(info.get("longBusinessSummary", "")),
        "price": {"current": round(cur, 2), "prev_close": round(prev, 2),
                  "change": round(cur - prev, 2), "change_pct": round((cur - prev) / prev * 100, 2) if prev else 0},
        "valuation": {"market_cap_b": round(mc / 1e9, 2) if mc else None},
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
