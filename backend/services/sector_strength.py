"""美股板塊強弱運算引擎 (移植自 data_engine/market/strength.py)。

純 pandas / numpy，不依賴 streamlit / yfinance。
所有重運算 (RSI / ATR / 相對強度 / 百分位排名 / 訊號) 集中於此 (§3.1)。
"""
import json
import os
import time

import numpy as np
import pandas as pd

_OVERVIEW_CACHE: dict = {}   # {"mtime": float, "data": dict}
_HEATMAP_CACHE: dict = {}   # period → {"mtime": float, "data": dict}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
BENCHMARK = "VTI"

# ETF 成分股鑽取的行程內快取 (TTL 1 小時)，避免重複打 yfinance
_HOLDINGS_CACHE: dict = {}
_HOLDINGS_TTL = 3600
_HOLDINGS_MAX = 50

PORTFOLIO_STRUCTURE = {
    "通訊服務 (Communication)": {"XLC": "通訊服務 SPDR", "SOCL": "社群媒體", "HERO": "電競與遊戲"},
    "非必需消費 (Discretionary)": {"XLY": "非必需消費 SPDR", "ITB": "房屋建築 (iShares)", "XHB": "房屋建築 (SPDR)", "IBUY": "線上零售 (Amplify)", "ONLN": "線上零售 (ProShares)", "PEJ": "休閒娛樂", "XRT": "零售業 SPDR"},
    "必需消費 (Staples)": {"XLP": "必需消費 SPDR", "PBJ": "食品與飲料"},
    "能源 (Energy)": {"XLE": "能源 SPDR", "GUNR": "全球天然資源", "FCG": "天然氣", "XOP": "油氣開採", "ICLN": "全球乾淨能源", "QCLN": "綠能與乾淨能源", "OIH": "石油服務", "TAN": "太陽能", "NLR": "鈾與核能", "AMLP": "能源基礎建設"},
    "金融 (Financial)": {"XLF": "金融 SPDR", "VFH": "金融 (Vanguard)", "KRE": "區域型銀行", "KBE": "銀行業 SPDR", "IAI": "券商與交易所", "KIE": "保險業", "IPAY": "數位支付", "BIZD": "商業發展公司(BDC)"},
    "醫療保健 (Health Care)": {"XLV": "醫療保健 SPDR", "IBB": "生技 (iShares)", "XBI": "生技 (SPDR)", "IHI": "醫療設備", "IHF": "醫療服務提供商", "XHE": "醫療器材", "XPH": "製藥業", "MJ": "大麻替代收成"},
    "工業 (Industrial)": {"XLI": "工業 SPDR", "ITA": "航太與國防", "ROKT": "太空與深海探勘", "UFO": "太空產業", "SHLD": "國防科技", "BOTZ": "機器人與AI", "IYT": "交通運輸", "JETS": "全球航空業", "SNSR": "物聯網", "DRIV": "自駕與電動車", "PAVE": "美國基礎建設", "GRID": "智慧電網"},
    "原物料 (Materials)": {"XLB": "原物料 SPDR", "GDX": "金礦開採", "SIL": "白銀開採", "COPX": "銅礦開採", "XME": "金屬與採礦", "LIT": "鋰電池技術", "IYM": "美國基本物料", "URA": "鈾礦 ETF", "REMX": "稀土與戰略金屬"},
    "不動產 (Real Estate)": {"XLRE": "不動產 SPDR", "VNQ": "美國房地產 (Vanguard)", "VNQI": "全球房地產(除美國)", "REET": "全球 REITs", "REM": "抵押貸款 REITs"},
    "科技 (Technology)": {"XLK": "科技 SPDR", "CHAT": "生成式 AI 與科技", "AIQ": "AI 與科技", "IXN": "全球科技", "QTEC": "納斯達克 100 科技", "QTUM": "量子運算", "VGT": "資訊科技 (Vanguard)", "SOXX": "半導體 (iShares)", "SMH": "半導體 (VanEck)", "XSD": "半導體(等權重)", "IGV": "軟體服務", "FDN": "網路指數", "KWEB": "中國互聯網", "CIBR": "網路資安 (First Trust)", "HACK": "網路資安 (Amplify)", "SKYY": "雲端運算", "METV": "元宇宙", "FINX": "金融科技", "XT": "指數型科技"},
    "公用事業 (Utilities)": {"XLU": "公用事業 SPDR", "IGF": "全球基礎建設"},
    "主題型與極端動能 (Thematic & Momentum)": {"MEME": "迷因股", "DXYZ": "Destiny Tech100", "BLOK": "區塊鏈技術", "IPO": "新股上市 IPO", "MOAT": "寬護城河優勢", "MOO": "全球農業", "ARKK": "ARK 創新", "ARKW": "ARK 下一代網路", "ARKF": "ARK 金融科技", "ARKX": "ARK 太空探勘", "ARKQ": "ARK 自行技術與機器人", "ARKG": "ARK 基因革命", "WGMI": "比特幣礦企"},
}

NAME_MAPPING = {t: name for group in PORTFOLIO_STRUCTURE.values() for t, name in group.items()}
GROUP_MAPPING = {t: g for g, tickers in PORTFOLIO_STRUCTURE.items() for t in tickers}


def _load_prices() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "sector_strength.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    float_cols = df.select_dtypes("float64").columns
    df[float_cols] = df[float_cols].astype("float32")
    return df


def compute_metrics(close_df: pd.DataFrame, benchmark: str = BENCHMARK) -> pd.DataFrame:
    """移植 compute_universal_metrics：以 date 為 index 的價格矩陣 → 指標表。"""
    if benchmark not in close_df.columns:
        return pd.DataFrame()
    bench_close = close_df[benchmark].dropna()

    rows = []
    for t in close_df.columns:
        if t == benchmark:
            continue
        c = close_df[t].dropna()
        common = c.index.intersection(bench_close.index)
        if len(common) < 130:
            continue
        c = c.loc[common]
        b = bench_close.loc[common]
        curr = float(c.iloc[-1])
        b_curr = float(b.iloc[-1])

        ret1 = (curr / float(c.iloc[-2]) - 1) * 100
        ret3 = (curr / float(c.iloc[-4]) - 1) * 100
        ret10 = (curr / float(c.iloc[-11]) - 1) * 100
        ret20 = (curr / float(c.iloc[-21]) - 1) * 100
        ret60 = (curr / float(c.iloc[-61]) - 1) * 100
        ret120 = (curr / float(c.iloc[-121]) - 1) * 100
        rel5 = (curr / float(c.iloc[-6]) - 1) * 100 - (b_curr / float(b.iloc[-6]) - 1) * 100
        rel20 = ret20 - (b_curr / float(b.iloc[-21]) - 1) * 100

        rs_line = c / b
        rs_60ma = rs_line.rolling(60).mean()
        rs_above = float(rs_line.iloc[-1]) > float(rs_60ma.iloc[-1]) and float(rs_60ma.iloc[-1]) > float(rs_60ma.iloc[-2])

        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = (gain / loss).replace([np.inf, -np.inf], 9999)
        rsi = float((100 - (100 / (1 + rs))).fillna(50).iloc[-1])

        atr14 = float(delta.abs().rolling(14).mean().iloc[-1])
        atr_pct = (atr14 / curr) * 100 if curr > 0 else 0.0

        rows.append({
            "ticker": t, "name": NAME_MAPPING.get(t, t), "group": GROUP_MAPPING.get(t, "個股"),
            "price": curr, "ret1": ret1, "ret3": ret3, "ret10": ret10,
            "rel5": rel5, "rel20": rel20, "_ret20": ret20, "_ret60": ret60, "_ret120": ret120,
            "rsi": rsi, "rs_above_ma": rs_above, "atr_pct": atr_pct,
            "trend": [round(x, 2) for x in c.tail(126).tolist()],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["r20"] = df["_ret20"].rank(pct=True) * 100
    df["r60"] = df["_ret60"].rank(pct=True) * 100
    df["r120"] = df["_ret120"].rank(pct=True) * 100
    df["total_rank"] = 0.2 * df["r20"] + 0.4 * df["r60"] + 0.4 * df["r120"]

    golden = (
        (df["total_rank"] >= 80) & df["rs_above_ma"] & (df["rsi"] >= 45) & (df["rsi"] <= 60)
        & (df["ret1"] > 1.0 * df["atr_pct"])
    )
    df["signal"] = np.where(golden, "🔥", "")
    return df.drop(columns=["_ret20", "_ret60", "_ret120"])


def get_overview():
    _path = os.path.join(DATA_DIR, "sector_strength.csv")
    try:
        _mt = os.path.getmtime(_path)
    except OSError:
        _mt = 0.0
    if _OVERVIEW_CACHE.get("mtime") == _mt and _mt:
        return _OVERVIEW_CACHE["data"]

    prices = _load_prices()
    if prices.empty:
        return None
    df = compute_metrics(prices.set_index("date"))
    if df.empty:
        return {"as_of": None, "items": [], "strategies": {"a": [], "b": [], "c": []}}

    as_of = prices["date"].iloc[-1].strftime("%Y-%m-%d")

    # 策略 A/B/C (移植自 Streamlit 多週期信號掃描)
    a = df[(df["total_rank"] >= 70) & (df["ret3"] > 1.0 * df["atr_pct"])]
    b = df[(df["total_rank"] <= 30) & (df["ret10"] < -2.0 * df["atr_pct"]) & (df["ret3"] > 0)]
    c = df[(df["total_rank"] >= 50) & (df["ret3"] < -1.5 * df["atr_pct"])]

    strat_cols = ["ticker", "name", "price", "atr_pct", "r20", "ret10", "ret3", "trend"]

    def _strat(d):
        return d[strat_cols].sort_values("ret3", ascending=False).round(4).to_dict(orient="records")

    items = df.sort_values(["group", "total_rank"], ascending=[True, False]).round(4)
    result = {
        "as_of": as_of,
        "items": items.to_dict(orient="records"),
        "strategies": {"a": _strat(a), "b": _strat(b), "c": _strat(c)},
    }
    _OVERVIEW_CACHE["mtime"] = _mt
    _OVERVIEW_CACHE["data"] = result
    return result


def get_heatmap(period: int):
    _path = os.path.join(DATA_DIR, "sector_strength.csv")
    try:
        _mt = os.path.getmtime(_path)
    except OSError:
        _mt = 0.0
    cached = _HEATMAP_CACHE.get(period)
    if cached and cached["mtime"] == _mt and _mt:
        return cached["data"]

    prices = _load_prices()
    if prices.empty:
        return None
    df = prices.sort_values("date").ffill()
    if len(df) <= period + 1:
        return {"period": period, "items": []}
    latest = df.iloc[-1]
    prev = df.iloc[-(period + 1)]
    items = []
    for group, tickers in PORTFOLIO_STRUCTURE.items():
        for t, name in tickers.items():
            if t in df.columns and pd.notna(latest.get(t)) and prev.get(t, 0) > 0:
                chg = (latest[t] - prev[t]) / prev[t] * 100
                items.append({"ticker": t, "name": name, "group": group, "price": round(float(latest[t]), 2), "chg_pct": round(float(chg), 2), "score": round(float(chg), 2)})
    result = {"period": period, "items": items}
    _HEATMAP_CACHE[period] = {"mtime": _mt, "data": result}
    return result


def get_holdings_metrics(etf: str):
    """ETF 成分股即時動能掃描 (對應 Streamlit Tab2 第二階段)。
    on-demand 用 yfinance 抓成分股 + VTI 一年日線，套用同一套指標引擎。
    """
    etf = etf.upper()
    path = os.path.join(DATA_DIR, "etf_holdings.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        holdings_map = json.load(f)
    holdings = holdings_map.get(etf, [])
    if not holdings:
        return {"etf": etf, "holdings_count": 0, "golden": [], "all": []}

    # 快取命中
    cached = _HOLDINGS_CACHE.get(etf)
    if cached and time.time() - cached["ts"] < _HOLDINGS_TTL:
        return cached["data"]

    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("後端未安裝 yfinance，無法即時鑽取成分股")

    yf_df = yf.download(holdings + [BENCHMARK], period="1y", auto_adjust=False, progress=False)
    if yf_df.empty or "Close" not in yf_df.columns:
        return {"etf": etf, "holdings_count": len(holdings), "golden": [], "all": []}

    float_cols = yf_df.select_dtypes("float64").columns
    yf_df[float_cols] = yf_df[float_cols].astype("float32")
    close_df = yf_df["Close"] if isinstance(yf_df.columns, pd.MultiIndex) else yf_df
    df = compute_metrics(close_df).sort_values("total_rank", ascending=False).round(4)
    all_rows = df.to_dict(orient="records")
    golden = df[df["signal"] == "🔥"].to_dict(orient="records")

    data = {"etf": etf, "holdings_count": len(holdings), "golden": golden, "all": all_rows}
    if len(_HOLDINGS_CACHE) >= _HOLDINGS_MAX:
        oldest = min(_HOLDINGS_CACHE, key=lambda k: _HOLDINGS_CACHE[k]["ts"])
        del _HOLDINGS_CACHE[oldest]
    _HOLDINGS_CACHE[etf] = {"ts": time.time(), "data": data}
    return data


def get_relative_strength(tickers: list[str]):
    prices = _load_prices()
    if prices.empty or BENCHMARK not in prices.columns:
        return None
    df = prices.sort_values("date")
    dates = df["date"].dt.strftime("%Y-%m-%d").tolist()
    bench = df[BENCHMARK]
    series = []
    for t in tickers:
        if t not in df.columns:
            continue
        rs = df[t] / bench
        first = rs.first_valid_index()
        if first is not None and rs.loc[first] > 0:
            rs = rs / rs.loc[first]
        data = [[d, round(float(v), 4)] for d, v in zip(dates, rs.tolist()) if pd.notna(v)]
        series.append({"ticker": t, "data": data})
    return {"benchmark": BENCHMARK, "series": series}
