"""交易模型每日戰報 API (對應 Streamlit views/trading_models.py + components/ai_models.py)。

唯讀：讀取 data/BamHI_Dashboard_*.csv (Alpha) 與 BamHI_Genesis_Dashboard_*.csv (Genesis)。
"""
import glob
import os
import re
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import get_current_user

router = APIRouter(prefix="/api/models", tags=["models"])

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")

# 各引擎顯示欄位 (對應 ai_models.draw_ai_table)
ALPHA_COLS = ["Ticker", "Resonance_Score", "Win_Prob", "Price", "RS_Rating", "Ov_Supply", "POC_Dist", "MA20_DP", "Vol_Dry_Up", "Turtle", "Dollar_Vol_M", "MktCap_B", "Cap_Tier"]
GENESIS_COLS = ["Ticker", "Resonance_Score", "Win_Prob", "Price", "MA_Conv", "Vol_Z", "Breakout", "MA20_Slope", "Ov_Supply", "POC_Dist", "Dollar_Vol_M", "MktCap_B", "Cap_Tier"]

ENGINE_PREFIX = {"alpha": "BamHI_Dashboard", "genesis": "BamHI_Genesis_Dashboard"}


def _list_dates() -> list[dict]:
    """掃描 Alpha 歷史檔，回傳最近 5 個日期 (新→舊)。"""
    files = glob.glob(os.path.join(DATA_DIR, "BamHI_Dashboard_20*.csv"))
    dates = []
    for f in files:
        m = re.search(r"(\d{8})", os.path.basename(f))
        if m:
            d = m.group(1)
            dates.append({"raw": d, "label": f"{d[:4]}-{d[4:6]}-{d[6:]}"})
    dates.sort(key=lambda x: x["raw"], reverse=True)
    return dates[:5]


def _resolve_path(engine: str, date: str) -> tuple[str, str]:
    prefix = ENGINE_PREFIX[engine]
    if date == "latest":
        return os.path.join(DATA_DIR, f"{prefix}_Latest.csv"), "(Latest)"
    return os.path.join(DATA_DIR, f"{prefix}_{date}.csv"), f"{date[:4]}-{date[4:6]}-{date[6:]}"


@router.get("/dates")
def dates(_user: dict = Depends(get_current_user)):
    """可選戰報日期 (供前端時光機下拉)。"""
    return {"latest_available": True, "dates": _list_dates()}


@router.get("/report")
def report(
    engine: str = Query(..., description="alpha | genesis"),
    date: str = Query("latest", description="latest 或 YYYYMMDD"),
    _user: dict = Depends(get_current_user),
):
    """單一引擎在指定日期的戰報：統計速覽 + 嚴選名單。"""
    if engine not in ENGINE_PREFIX:
        raise HTTPException(status_code=404, detail=f"未知引擎：{engine}")

    path, display_date = _resolve_path(engine, date)
    if not os.path.exists(path):
        return {"engine": engine, "date": display_date, "updated_at": None,
                "stats": {"total": 0, "avg_win_prob": None, "max_resonance": None}, "items": []}

    df = pd.read_csv(path)
    total = len(df)
    avg_win_prob = float(df["Win_Prob"].mean() * 100) if total and "Win_Prob" in df.columns else None
    max_resonance = float(df["Resonance_Score"].max()) if total and "Resonance_Score" in df.columns else None

    if "Win_Prob" in df.columns:
        df = df.copy()
        df["Win_Prob"] = df["Win_Prob"] * 100  # 轉成百分比 (對應 draw_ai_table)

    cols = ALPHA_COLS if engine == "alpha" else GENESIS_COLS
    keep = [c for c in cols if c in df.columns]
    items = df[keep].where(pd.notnull(df[keep]), None).round(4).to_dict(orient="records")

    updated_at = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return {
        "engine": engine,
        "date": display_date,
        "updated_at": updated_at,
        "stats": {
            "total": total,
            "avg_win_prob": round(avg_win_prob, 1) if avg_win_prob is not None else None,
            "max_resonance": round(max_resonance, 1) if max_resonance is not None else None,
        },
        "items": items,
    }
