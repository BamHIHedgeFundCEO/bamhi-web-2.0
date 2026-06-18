"""個股深度檔案引擎 (移植自 data_engine/equity.py)。

yfinance (K線 + 技術指標) + FMP (美股基本面/財報) / FinMind (台股財報)。
純 pandas/numpy，不依賴 streamlit。FMP 金鑰改讀環境變數。
"""
import os
import time

import numpy as np
import pandas as pd
import requests

FMP_API_KEY = os.getenv("FMP_API_KEY", "29epqrFbGsBfasHJHyU7fnFT8CcUdeaF")

_CACHE: dict = {}
_TTL = 3600
_CACHE_MAX = 200


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


def _fmp_fundamentals(ticker: str, info: dict) -> pd.DataFrame:
    income_stmt = pd.DataFrame()
    try:
        p = requests.get(f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={FMP_API_KEY}", timeout=10).json()
        if p:
            p = p[0] if isinstance(p, list) else p
            info.update({"shortName": p.get("companyName", ticker), "sector": p.get("sector", "N/A"),
                         "industry": p.get("industry", "N/A"), "longBusinessSummary": p.get("description", "暫無公司業務介紹。"),
                         "website": p.get("website", "N/A"), "fullTimeEmployees": p.get("fullTimeEmployees", "N/A"),
                         "marketCap": p.get("mktCap", 0)})
        m = requests.get(f"https://financialmodelingprep.com/stable/key-metrics-ttm?symbol={ticker}&apikey={FMP_API_KEY}", timeout=10).json()
        if m:
            m = m[0] if isinstance(m, list) else m
            info["trailingPE"] = m.get("peRatioTTM")
            info["priceToBook"] = m.get("pbRatioTTM")
            info["returnOnEquity"] = m.get("roeTTM")
    except Exception as e:
        print(f"FMP 基本資料失敗: {e}")

    try:
        is_resp = requests.get(f"https://financialmodelingprep.com/stable/income-statement?symbol={ticker}&period=quarter&limit=5&apikey={FMP_API_KEY}", timeout=10).json()
        cf_resp = requests.get(f"https://financialmodelingprep.com/stable/cash-flow-statement?symbol={ticker}&period=quarter&limit=4&apikey={FMP_API_KEY}", timeout=10).json()
        if is_resp and cf_resp:
            df_is = pd.DataFrame(is_resp if isinstance(is_resp, list) else [is_resp])
            df_cf = pd.DataFrame(cf_resp if isinstance(cf_resp, list) else [cf_resp])
            if not df_is.empty and not df_cf.empty:
                df_is.set_index("date", inplace=True)
                df_cf.set_index("date", inplace=True)
                if "grossProfit" in df_is and "revenue" in df_is:
                    df_is["grossProfitRatio"] = df_is["grossProfit"] / df_is["revenue"]
                if "netIncome" in df_is and "revenue" in df_is:
                    df_is["netIncomeRatio"] = df_is["netIncome"] / df_is["revenue"]
                df_is["revenue_YoY"] = df_is["revenue"].pct_change(periods=-4) if len(df_is) >= 5 else None
                combined = pd.concat([df_is.head(4), df_cf.head(4)], axis=1).T
                mapping = {"revenue": "營收 (Revenue)", "revenue_YoY": "營收年增率 (YoY)", "grossProfitRatio": "毛利率 (Gross Margin)",
                           "netIncomeRatio": "淨利率 (Net Margin)", "eps": "單季 EPS", "operatingCashFlow": "營運現金流 (Operating CF)",
                           "freeCashFlow": "自由現金流 (Free CF)"}
                avail = [c for c in mapping if c in combined.index]
                income_stmt = combined.loc[avail].rename(index=mapping)
    except Exception as e:
        print(f"FMP 財報失敗: {e}")
    return income_stmt


def _financials_to_records(df: pd.DataFrame) -> list[dict]:
    """財報 DataFrame (index=指標, columns=季度) → 前端易渲染的列結構。"""
    if df.empty:
        return {"columns": [], "rows": []}
    pct_rows = {"營收年增率 (YoY)", "毛利率 (Gross Margin)", "淨利率 (Net Margin)"}
    money_rows = {"營收 (Revenue)", "營運現金流 (Operating CF)", "自由現金流 (Free CF)"}
    out = []
    for metric in df.index:
        row = {"metric": metric}
        for col in df.columns:
            v = df.at[metric, col]
            if pd.isna(v) or v is None:
                row[str(col)] = None
            elif metric in pct_rows:
                row[str(col)] = round(float(v) * 100, 2)
            elif metric in money_rows:
                row[str(col)] = round(float(v) / 1e6, 1)  # → 百萬
            else:
                row[str(col)] = round(float(v), 2)
        out.append(row)
    return {"columns": [str(c) for c in df.columns], "rows": out}


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

    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period, interval=interval)
    except Exception:
        hist = pd.DataFrame()
    if hist.empty:
        return None

    hist = _compute_indicators(hist)
    info = {"currentPrice": float(hist["Close"].iloc[-1])}
    income_stmt = _fmp_fundamentals(ticker, info)

    if "previousClose" not in info:
        info["previousClose"] = float(hist["Close"].iloc[-2]) if len(hist) > 1 else info["currentPrice"]

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
    def col(c, dg=4):
        return [None if pd.isna(v) else round(float(v), dg) for v in hist[c]] if c in hist else []

    cur = info["currentPrice"]
    prev = info["previousClose"]
    mc = info.get("marketCap") or 0
    roe = info.get("returnOnEquity")

    data = {
        "ticker": ticker, "company_name": info.get("shortName", ticker),
        "sector": info.get("sector", "N/A"), "industry": info.get("industry", "N/A"),
        "employees": info.get("fullTimeEmployees", "N/A"), "website": info.get("website", "N/A"),
        "summary": info.get("longBusinessSummary", "暫無公司業務介紹。"),
        "summary_zh": _translate_zh(info.get("longBusinessSummary", "")),
        "price": {"current": round(cur, 2), "prev_close": round(prev, 2),
                  "change": round(cur - prev, 2), "change_pct": round((cur - prev) / prev * 100, 2) if prev else 0},
        "valuation": {"market_cap_b": round(mc / 1e9, 2) if mc else None,
                      "pe": round(float(info["trailingPE"]), 2) if isinstance(info.get("trailingPE"), (int, float)) else None,
                      "pb": round(float(info["priceToBook"]), 2) if isinstance(info.get("priceToBook"), (int, float)) else None,
                      "roe_pct": round(float(roe) * 100, 2) if isinstance(roe, (int, float)) else None},
        "trend_status": trend, "signal_status": signal, "composite": round(comp, 1),
        "chart": {
            "dates": dates, "interval": interval,
            "candle": [[None if pd.isna(o) else round(float(o), 3), None if pd.isna(cl) else round(float(cl), 3),
                        None if pd.isna(lo) else round(float(lo), 3), None if pd.isna(hi) else round(float(hi), 3)]
                       for o, cl, lo, hi in zip(hist["Open"], hist["Close"], hist["Low"], hist["High"])],
            "ma": {f"MA{w}": col(f"MA_{w}") for w in (5, 10, 20, 60, 120, 240)},
            "composite": col("Composite", 2),
            "signals_up": [dates[i] for i, v in enumerate(hist["Signal_Up"]) if v],
            "signals_down": [dates[i] for i, v in enumerate(hist["Signal_Down"]) if v],
        },
        "financials": _financials_to_records(income_stmt),
    }
    if len(_CACHE) >= _CACHE_MAX:
        oldest = min(_CACHE, key=lambda k: _CACHE[k]["ts"])
        del _CACHE[oldest]
    _CACHE[key] = {"ts": time.time(), "data": data}
    return data
