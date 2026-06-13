"""暗池異常資金監控 API (對應 Streamlit render_darkpool_scanner)。

唯讀：讀取每日 pipeline 產出的 data/darkpool_results.csv，轉成 JSON。
不依賴 streamlit，可直接於 Render 運行。
"""
import os
import time
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user

router = APIRouter(prefix="/api/dark-pool", tags=["dark-pool"])

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_PATH = os.path.join(BASE_DIR, "data", "darkpool_results.csv")

# 60 日走勢迷你線快取 (best-effort，失敗不影響表格)
_TREND_CACHE: dict = {"ts": 0, "data": {}}
_TREND_TTL = 900


def _fetch_trends(tickers: list[str]) -> dict:
    """用 yfinance 抓 ~50 檔近 60 日收盤，給迷你線用。失敗回空 dict。"""
    if _TREND_CACHE["data"] and time.time() - _TREND_CACHE["ts"] < _TREND_TTL:
        return _TREND_CACHE["data"]
    out: dict = {}
    try:
        import yfinance as yf

        raw = yf.download(tickers, period="3mo", progress=False, auto_adjust=False)
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})
        for t in tickers:
            if t in close.columns:
                s = close[t].dropna().tail(60)
                if len(s) >= 2:
                    out[t] = [round(float(x), 2) for x in s.tolist()]
        _TREND_CACHE.update(ts=time.time(), data=out)
    except Exception as e:
        print(f"[dark-pool] 走勢抓取失敗（略過）: {e}")
    return out

# CSV 原始欄位 → API snake_case 欄位
COLUMN_MAP = {
    "Ticker": "ticker",
    "Price": "price",
    "Chg%": "chg_pct",
    "Surx": "surx",
    "Short%": "short_pct",
    "Above_MA200": "above_ma200",
    "Dist_52W_High%": "dist_52w_high_pct",
    "Dist_MA200_%": "dist_ma200_pct",
    "Dist_52W_Low%": "dist_52w_low_pct",
    "RSI_14": "rsi_14",
}


class DarkPoolItem(BaseModel):
    ticker: str
    price: float | None = None
    chg_pct: float | None = None
    surx: float | None = None
    short_pct: float | None = None
    above_ma200: bool | None = None
    dist_52w_high_pct: float | None = None
    dist_ma200_pct: float | None = None
    dist_52w_low_pct: float | None = None
    rsi_14: float | None = None
    trend: list[float] | None = None


class DarkPoolResponse(BaseModel):
    as_of: str | None = None
    count: int
    items: list[DarkPoolItem]


@router.get("/surge-list", response_model=DarkPoolResponse)
def get_surge_list(_user: dict = Depends(get_current_user)) -> DarkPoolResponse:
    if not os.path.exists(RESULTS_PATH):
        raise HTTPException(
            status_code=503,
            detail="暫無暗池資料，請確認 update_darkpool_pipeline.py 是否已執行。",
        )

    df = pd.read_csv(RESULTS_PATH)
    df = df.rename(columns=COLUMN_MAP)
    if "above_ma200" in df.columns:
        df["above_ma200"] = df["above_ma200"].astype(bool)

    # NaN → None，確保可序列化為合法 JSON
    records = df.where(pd.notnull(df), None).to_dict(orient="records")

    # 加上 60 日走勢迷你線 (best-effort)
    trends = _fetch_trends([r["ticker"] for r in records if r.get("ticker")])
    for r in records:
        r["trend"] = trends.get(r.get("ticker"))

    as_of = datetime.fromtimestamp(
        os.path.getmtime(RESULTS_PATH), tz=timezone.utc
    ).strftime("%Y-%m-%d")

    return DarkPoolResponse(
        as_of=as_of,
        count=len(records),
        items=[DarkPoolItem(**r) for r in records],
    )
