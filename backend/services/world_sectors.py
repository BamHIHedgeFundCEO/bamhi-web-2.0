"""全球市場強弱運算引擎 (移植自 data_engine/market/world_sectors.py)。

純 pandas / numpy，讀 data/world_sectors.csv。
策略 ATR 以收盤價近似 (與 sector_strength 一致)，不依賴 yfinance。
"""
import os

import numpy as np
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")

PORTFOLIO_STRUCTURE = {
    "🌐 全球與美國大盤 (Global & US Broad)": {"VT": "全球全市場", "ACWI": "全球市場(ACWI)", "ACWX": "全球(除美國)", "VTI": "美股全市場", "SPY": "標普500", "QQQ": "納斯達克", "DIA": "道瓊工業", "IWM": "羅素2000", "MDY": "中型股", "XLK": "科技板塊", "XLF": "金融板塊", "XLV": "醫療保健"},
    "🌏 亞洲與太平洋 (Asia & Pacific)": {"EWA": "澳洲", "EWH": "香港", "EWM": "馬來西亞", "EWS": "新加坡", "EWT": "台灣", "EWY": "南韓", "IFN": "印度(IFN)", "INDA": "印度(INDA)", "EWJ": "日本", "EPP": "亞洲(不含日本)", "AAXJ": "亞洲(除日本)", "FXI": "中國大型股(H股)", "MCHI": "中國全市場", "ASHR": "中國滬深300(A股)", "KWEB": "中國互聯網", "VNM": "越南", "EIDO": "印尼", "THD": "泰國", "EPHE": "菲律賓"},
    "🌎 美洲與新興市場 (Americas & EM)": {"EEM": "新興市場", "EMXC": "新興市場(除中國)", "VWO": "新興市場(Vanguard)", "ILF": "拉丁美洲", "EWC": "加拿⼤", "EWW": "墨西哥", "EWZ": "巴西", "ARS": "阿根廷", "ARGT": "阿根廷(ARGT)", "ECH": "智利", "EPU": "秘魯", "GXG": "哥倫比亞"},
    "🌍 歐洲板塊 (Europe)": {"EFA": "歐澳遠東", "EZU": "歐元區", "IEUR": "歐洲全市場", "VGK": "歐洲(Vanguard)", "EWD": "瑞典", "EWG": "德國", "EWK": "比利時", "EWL": "瑞士", "EWN": "荷蘭", "EWO": "奧地利", "EWP": "西班牙", "EWQ": "法國", "EWU": "英國", "EWI": "義大利", "GREK": "希臘", "EPOL": "波蘭"},
    "🐫 中東與非洲 (Middle East & Africa)": {"EZA": "南非", "TUR": "土耳其", "KSA": "沙烏地阿拉伯", "EIS": "以色列", "AFK": "非洲全市場"},
    "🏢 房地產與抵押債 (Real Estate)": {"VNQ": "美國房地產", "VNQI": "全球房地產(除美國)", "REET": "全球REITs", "REM": "抵押貸款REITs", "MBB": "MBS抵押債券"},
    "💰 高股息與進階收益 (Dividend & Income)": {"PFF": "特別股與收益", "DVY": "精選高股息", "SCHD": "美國紅利", "IDV": "國際高股息", "AMLP": "能源MLP", "JEPI": "標普掩護性買權", "JEPQ": "納指掩護性買權", "QQQI": "納斯達克高收益", "DIVO": "增強型股息", "QDVO": "成長與收益", "QYLD": "納指Covered Call", "XYLD": "標普Covered Call"},
    "🛡️ 固定收益與債券 (Fixed Income)": {"BND": "全市場債券", "AGG": "美國總體債", "BNDX": "國際債券", "TIP": "抗通膨債", "VTIP": "短期抗通膨債", "TLT": "20年期公債", "TLH": "10-20年公債", "IEF": "7-10年公債", "IEI": "3-7年公債", "SHY": "1-3年公債", "BILS": "3-12個月國庫券", "BIL": "1-3個月國庫券", "SGOV": "0-3個月國庫券", "LQD": "投資級公司債", "HYG": "高收益債", "BINC": "主動型彈性收益", "JAAA": "AAA級CLO", "JBBB": "BBB級CLO", "EMB": "新興市場債", "EMHY": "新興市場高收債"},
    "🛢️ 大宗商品與加密資產 (Commodities & Crypto)": {"DBC": "廣泛大宗商品", "PDBC": "大宗商品(PDBC)", "DBB": "基本金屬", "DBA": "農產品", "GLD": "黃金", "SLV": "白銀", "CPER": "銅礦指數", "USO": "美國原油", "UNG": "天然氣", "UUP": "美元指數", "IBIT": "比特幣"},
}

NAME_MAPPING = {t: name for g in PORTFOLIO_STRUCTURE.values() for t, name in g.items()}


def _load_prices() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "world_sectors.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["date"])
    return df


def _strategies(df_indexed: pd.DataFrame) -> dict:
    """收盤價近似 ATR + ma50 + 20D PR 排名 → 策略 A/B/C。"""
    rows = []
    for t in df_indexed.columns:
        c = df_indexed[t].dropna()
        if len(c) < 50:
            continue
        curr = float(c.iloc[-1])
        ma50 = float(c.rolling(50).mean().iloc[-1])
        if len(c) < 21:
            continue
        ret20 = (curr / float(c.iloc[-21]) - 1) * 100
        ret10 = (curr / float(c.iloc[-11]) - 1) * 100 if len(c) >= 11 else np.nan
        ret3 = (curr / float(c.iloc[-4]) - 1) * 100 if len(c) >= 4 else np.nan
        atr_pct = float(c.diff().abs().rolling(14).mean().iloc[-1]) / curr * 100 if curr > 0 else np.nan
        if np.isnan(ret20) or np.isnan(atr_pct):
            continue
        rows.append({"ticker": t, "name": NAME_MAPPING.get(t, t), "price": round(curr, 4),
                     "atr_pct": round(atr_pct, 4), "ret20": ret20, "ret10": ret10, "ret3": ret3,
                     "ma50": ma50, "above_ma50": curr > ma50,
                     "trend": [round(float(x), 4) for x in c.tail(60).tolist()]})

    if not rows:
        return {"a": [], "b": [], "c": []}
    df = pd.DataFrame(rows)
    df["r20"] = df["ret20"].rank(pct=True) * 100

    a = df[(df["above_ma50"]) & (df["r20"] >= 70) & (df["ret10"].abs() < 2.0 * df["atr_pct"]) & (df["ret3"] > 1.5 * df["atr_pct"])]
    b = df[(df["above_ma50"]) & (df["r20"] >= 70) & (df["ret10"] < -3.0 * df["atr_pct"]) & (df["ret3"] > 1.0 * df["atr_pct"])]
    c = df[(~df["above_ma50"]) & (df["ret20"] < 0) & (df["ret3"] < 0)]

    cols = ["ticker", "name", "price", "atr_pct", "r20", "ret10", "ret3", "trend"]

    def _out(d):
        return d[cols].sort_values("ret3", ascending=False).round(4).to_dict(orient="records")

    return {"a": _out(a), "b": _out(b), "c": _out(c)}


def get_momentum(period: int):
    prices = _load_prices()
    if prices.empty:
        return None
    df = prices.set_index("date").ffill()
    as_of = prices["date"].iloc[-1].strftime("%Y-%m-%d")

    items = []
    mode = "vol_adjusted" if period >= 5 else "price"
    if len(df) > period + 1:
        curr = df.iloc[-1]
        prev = df.iloc[-(period + 1)]
        pct = (curr - prev) / prev
        vols = df.pct_change(fill_method=None).tail(period).std() if period >= 5 else None
        for group, tickers in PORTFOLIO_STRUCTURE.items():
            for t, name in tickers.items():
                if t not in df.columns or pd.isna(curr.get(t)):
                    continue
                pchg = float(pct[t])
                if period < 5:
                    score, vol_val = pchg * 100, 0.0
                else:
                    vol = float(vols[t])
                    score = pchg / vol if vol > 0 else 0.0
                    vol_val = vol * (252 ** 0.5) * 100
                items.append({"ticker": t, "name": name, "group": group, "price": round(float(curr[t]), 4),
                              "chg_pct": round(pchg * 100, 4), "vol_pct": round(vol_val, 4), "score": round(score, 4),
                              "trend": [round(float(x), 4) for x in df[t].dropna().tail(60).tolist()]})

    return {"as_of": as_of, "period": period, "mode": mode, "items": items,
            "strategies": _strategies(df), "groups": list(PORTFOLIO_STRUCTURE.keys())}
