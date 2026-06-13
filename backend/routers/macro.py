"""總經市場指標 API (對應 Streamlit views/macro_market.py)。

唯讀：讀取 data/ 下各 CSV，回傳原始時間序列 + 最新值/漲跌。
圖表樣式由前端 chart-spec 負責，後端只供資料 (§3.1)。
不依賴 streamlit / yfinance，可直接於 Render 運行。
"""
import os

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth import get_current_user

router = APIRouter(prefix="/api/macro", tags=["macro"])

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")

# 指標 → 顯示名稱
INDICATOR_NAMES = {
    "DGS10": "10 Years Yield",
    "DGS2": "2 Years Yield",
    "SPREAD_10_2": "10-2 Spread",
    "MACRO_TRIO": "核心經濟指標 (GDP / 名目利率 / r-star)",
    "BREADTH_SP500": "S&P 500 市場寬度",
    "SENTIMENT_COMBO": "散戶 & 機構情緒方向",
}


class LatestStat(BaseModel):
    value: float | None = None
    change: float | None = None
    change_type: str = "none"  # pct | raw | none


class MacroSeriesResponse(BaseModel):
    id: str
    name: str
    latest: LatestStat
    data: list[dict]


def _read_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=503, detail=f"暫無資料：data/{filename} 不存在")
    return pd.read_csv(path)


def _records(df: pd.DataFrame) -> list[dict]:
    """NaN → None，date 轉為 ISO 字串。"""
    out = df.where(pd.notnull(df), None)
    if "date" in out.columns:
        out = out.copy()
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")


def _pct_change(series: pd.Series) -> float | None:
    s = series.dropna()
    if len(s) < 2 or float(s.iloc[0]) == 0:
        return None
    return (float(s.iloc[-1]) - float(s.iloc[0])) / float(s.iloc[0]) * 100.0


# ── 各指標處理器 ──
def _rates(indicator: str) -> tuple[LatestStat, list[dict]]:
    df = _read_csv("rates.csv")
    col = {"DGS10": "DGS10", "DGS2": "DGS2", "SPREAD_10_2": "Spread"}[indicator]
    if indicator == "SPREAD_10_2":
        data = df[["date", "DGS10", "DGS2", "Spread"]]
    else:
        data = df[["date", col]]
    latest = LatestStat(
        value=float(df[col].dropna().iloc[-1]),
        change=_pct_change(df[col]),
        change_type="pct",
    )
    return latest, _records(data)


def _macro_trio() -> tuple[LatestStat, list[dict]]:
    df = _read_csv("gdp_fedfunds_rstar.csv")
    cols = ["date", "GDP_Growth", "FEDFUNDS"]
    if "r_star" in df.columns:
        cols.append("r_star")
    primary = df["r_star"].dropna() if "r_star" in df.columns and df["r_star"].notna().any() else df["FEDFUNDS"].dropna()
    change = (float(primary.iloc[-1]) - float(primary.iloc[-2])) if len(primary) > 1 else None
    latest = LatestStat(value=float(primary.iloc[-1]), change=change, change_type="raw")
    return latest, _records(df[cols])


def _breadth() -> tuple[LatestStat, list[dict]]:
    df = _read_csv("breadth.csv")
    latest = LatestStat(
        value=float(df["value"].dropna().iloc[-1]),
        change=_pct_change(df["value"]),
        change_type="pct",
    )
    return latest, _records(df[["date", "value", "breadth_50", "breadth_200"]])


def _sentiment() -> tuple[LatestStat, list[dict]]:
    naaim_path = os.path.join(DATA_DIR, "naaim.csv")
    aaii_path = os.path.join(DATA_DIR, "sentiment.csv")
    frames = []

    if os.path.exists(naaim_path):
        n = pd.read_csv(naaim_path).rename(columns={"Date": "date"})
        keep = [c for c in ["date", "NAAIM", "NAAIM_MA20", "SP500_Price"] if c in n.columns]
        frames.append(("naaim", n[keep]))
    if os.path.exists(aaii_path):
        a = pd.read_csv(aaii_path).rename(
            columns={"Date": "date", "Spread": "AAII_Spread", "Spread_MA20": "AAII_MA20"}
        )
        keep = [c for c in ["date", "AAII_Spread", "AAII_MA20", "SP500_Price"] if c in a.columns]
        frames.append(("aaii", a[keep]))

    if not frames:
        raise HTTPException(status_code=503, detail="暫無情緒資料")

    merged = frames[0][1]
    for _, f in frames[1:]:
        merged = pd.merge(merged, f, on="date", how="outer", suffixes=("", "_aaii"))

    # 整併 SP500：兩來源任一存在即可
    sp_cols = [c for c in merged.columns if c.startswith("SP500_Price")]
    if sp_cols:
        merged["SP500"] = merged[sp_cols].bfill(axis=1).iloc[:, 0]
        merged = merged.drop(columns=sp_cols)

    merged = merged.sort_values("date").reset_index(drop=True)

    latest = LatestStat(change_type="none")
    if "NAAIM" in merged.columns and merged["NAAIM"].notna().any():
        latest.value = float(merged["NAAIM"].dropna().iloc[-1])

    out_cols = [c for c in ["date", "NAAIM", "NAAIM_MA20", "AAII_Spread", "AAII_MA20", "SP500"] if c in merged.columns]
    return latest, _records(merged[out_cols])


@router.get("/series", response_model=MacroSeriesResponse)
def get_series(
    indicator: str = Query(..., description="DGS10 / DGS2 / SPREAD_10_2 / MACRO_TRIO / BREADTH_SP500 / SENTIMENT_COMBO"),
    _user: dict = Depends(get_current_user),
) -> MacroSeriesResponse:
    if indicator not in INDICATOR_NAMES:
        raise HTTPException(status_code=404, detail=f"未知指標：{indicator}")

    if indicator in ("DGS10", "DGS2", "SPREAD_10_2"):
        latest, data = _rates(indicator)
    elif indicator == "MACRO_TRIO":
        latest, data = _macro_trio()
    elif indicator == "BREADTH_SP500":
        latest, data = _breadth()
    else:  # SENTIMENT_COMBO
        latest, data = _sentiment()

    return MacroSeriesResponse(
        id=indicator, name=INDICATOR_NAMES[indicator], latest=latest, data=data
    )
