"""市場觀察 — 讀取 Pipeline 預算 CSV/JSON，供 API 回傳。"""
import json
import os
from datetime import datetime, timezone

import pandas as pd

DATA_DIR = "data"


def _mtime(path: str) -> str:
    if not os.path.exists(path):
        return ""
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_kings() -> dict:
    path = os.path.join(DATA_DIR, "mr_kings.csv")
    if not os.path.exists(path):
        return {"items": [], "total": 0, "updated_at": "", "error": "資料尚未生成，請先跑 Pipeline"}
    try:
        df = pd.read_csv(path)
        df["Pullback_Buy"] = df["Pullback_Buy"].astype(bool)
        float_cols = df.select_dtypes("float64").columns
        df[float_cols] = df[float_cols].astype("float32")
        items = df.where(pd.notnull(df), None).to_dict(orient="records")
        return {"items": items, "total": len(items), "updated_at": _mtime(path)}
    except Exception as e:
        return {"items": [], "total": 0, "updated_at": "", "error": str(e)}


def get_rising_stars() -> dict:
    path = os.path.join(DATA_DIR, "mr_rising_stars.csv")
    if not os.path.exists(path):
        return {"items": [], "total": 0, "updated_at": "", "error": "資料尚未生成，請先跑 Pipeline"}
    try:
        df = pd.read_csv(path)
        float_cols = df.select_dtypes("float64").columns
        df[float_cols] = df[float_cols].astype("float32")
        items = df.where(pd.notnull(df), None).to_dict(orient="records")
        return {"items": items, "total": len(items), "updated_at": _mtime(path)}
    except Exception as e:
        return {"items": [], "total": 0, "updated_at": "", "error": str(e)}


def get_adjacency() -> dict:
    path = os.path.join(DATA_DIR, "mr_adjacency.json")
    if not os.path.exists(path):
        return {"nodes": [], "edges": [], "sectors": {}, "computed_at": "", "error": "資料尚未生成"}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"nodes": [], "edges": [], "sectors": {}, "computed_at": "", "error": str(e)}
