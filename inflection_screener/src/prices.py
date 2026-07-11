"""價格層：yfinance 逐檔抓取 + retry + 失敗名單（spec §2.3）。

⚠ 僅對通過基本面閘門的 ticker 清單逐檔抓，絕不全市場掃。
單檔失敗不得中斷全流程 — 記 log 跳過。
"""
import time

import numpy as np
import pandas as pd
import yfinance as yf

from inflection_screener import config


def fetch_history(ticker: str) -> pd.DataFrame | None:
    """日線 OHLCV（近 PRICE_LOOKBACK_DAYS 日曆天）。retry 3 次指數退避。"""
    for attempt in range(config.YF_RETRIES):
        try:
            df = yf.Ticker(ticker).history(
                period=f"{config.PRICE_LOOKBACK_DAYS}d", auto_adjust=True
            )
            if df is not None and len(df) >= 60 and "Close" in df.columns:
                return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
            raise ValueError(f"資料不足（{0 if df is None else len(df)} 列）")
        except Exception as e:
            if attempt == config.YF_RETRIES - 1:
                print(f"[prices] {ticker} 失敗（{config.YF_RETRIES} 次重試後）：{e}", flush=True)
                return None
            time.sleep(2 ** attempt)
    return None


def fetch_market_cap(ticker: str) -> float:
    """市值：fast_info.market_cap，缺則 shares × 收盤價。失敗 → NaN。"""
    try:
        fi = yf.Ticker(ticker).fast_info
        mc = fi.get("marketCap") or fi.get("market_cap")
        if mc:
            return float(mc)
        shares = fi.get("shares")
        price = fi.get("lastPrice") or fi.get("last_price")
        if shares and price:
            return float(shares) * float(price)
    except Exception as e:
        print(f"[prices] {ticker} 市值失敗：{e}", flush=True)
    return np.nan


def fetch_all(tickers: list[str]) -> tuple[dict[str, pd.DataFrame], dict[str, float], list[str]]:
    """逐檔抓取。Returns (histories, market_caps, failed)。"""
    hists: dict[str, pd.DataFrame] = {}
    caps: dict[str, float] = {}
    failed: list[str] = []
    for i, t in enumerate(tickers):
        df = fetch_history(t)
        if df is None:
            failed.append(t)
            continue
        hists[t] = df
        caps[t] = fetch_market_cap(t)
        if (i + 1) % 25 == 0:
            print(f"[prices] {i + 1}/{len(tickers)}", flush=True)
    if failed:
        print(f"[prices] 失敗名單（{len(failed)}）：{','.join(failed)}", flush=True)
    return hists, caps, failed


def snapshot(df: pd.DataFrame) -> dict:
    """最新收盤價 + 20 日均成交額（閘門 ① 用）。"""
    close = df["Close"]
    dollar = (df["Close"] * df["Volume"]).tail(20)
    return {
        "price": float(close.iloc[-1]),
        "dollar_vol_20d": float(dollar.mean()) if len(dollar) else np.nan,
    }


def passes_liquidity_gate(market_cap: float, price: float, dollar_vol_20d: float) -> bool:
    """閘門 ①：流動性 / 規模（spec §5.1）。"""
    return bool(
        pd.notna(market_cap) and market_cap >= config.MIN_MARKET_CAP
        and pd.notna(price) and price >= config.MIN_PRICE
        and pd.notna(dollar_vol_20d) and dollar_vol_20d >= config.MIN_DOLLAR_VOL_20D
    )
