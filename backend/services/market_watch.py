"""市場觀察 — 讀取 Pipeline 預算 CSV/JSON，供 API 回傳。"""
import json
import os
from datetime import datetime, timezone

import pandas as pd

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

# mtime-keyed file cache: path → {"mtime": float, "data": dict}
_FILE_CACHE: dict[str, dict] = {}


def _mtime_str(path: str) -> str:
    if not os.path.exists(path):
        return ""
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _mtime_float(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _cached(path: str) -> dict | None:
    entry = _FILE_CACHE.get(path)
    if entry and entry["mtime"] == _mtime_float(path):
        return entry["data"]
    return None


def get_kings() -> dict:
    path = os.path.join(DATA_DIR, "mr_kings.csv")
    if not os.path.exists(path):
        return {"items": [], "total": 0, "updated_at": "", "error": "資料尚未生成，請先跑 Pipeline"}
    if (hit := _cached(path)):
        return hit
    try:
        df = pd.read_csv(path)
        df["Pullback_Buy"] = df["Pullback_Buy"].astype(bool)
        if "Is_New" in df.columns:
            df["Is_New"] = df["Is_New"].astype(bool)
        float_cols = df.select_dtypes("float64").columns
        df[float_cols] = df[float_cols].astype("float32")
        items = df.where(pd.notnull(df), None).to_dict(orient="records")
        result = {"items": items, "total": len(items), "updated_at": _mtime_str(path)}
        _FILE_CACHE[path] = {"mtime": _mtime_float(path), "data": result}
        return result
    except Exception as e:
        return {"items": [], "total": 0, "updated_at": "", "error": str(e)}


def get_rising_stars() -> dict:
    path = os.path.join(DATA_DIR, "mr_rising_stars.csv")
    if not os.path.exists(path):
        return {"items": [], "total": 0, "updated_at": "", "error": "資料尚未生成，請先跑 Pipeline"}
    if (hit := _cached(path)):
        return hit
    try:
        df = pd.read_csv(path)
        for col in ("Entry_Momentum", "Entry_Pullback", "Is_New"):
            if col in df.columns:
                df[col] = df[col].astype(bool)
        float_cols = df.select_dtypes("float64").columns
        df[float_cols] = df[float_cols].astype("float32")
        items = df.where(pd.notnull(df), None).to_dict(orient="records")
        result = {"items": items, "total": len(items), "updated_at": _mtime_str(path)}
        _FILE_CACHE[path] = {"mtime": _mtime_float(path), "data": result}
        return result
    except Exception as e:
        return {"items": [], "total": 0, "updated_at": "", "error": str(e)}


def get_adjacency() -> dict:
    path = os.path.join(DATA_DIR, "mr_adjacency.json")
    if not os.path.exists(path):
        return {"nodes": [], "edges": [], "sectors": {}, "computed_at": "", "error": "資料尚未生成"}
    if (hit := _cached(path)):
        return hit
    try:
        with open(path, encoding="utf-8") as f:
            result = json.load(f)
        _FILE_CACHE[path] = {"mtime": _mtime_float(path), "data": result}
        return result
    except Exception as e:
        return {"nodes": [], "edges": [], "sectors": {}, "computed_at": "", "error": str(e)}
