"""
L0 粗篩 — yfscreen (Yahoo Finance Screener API)

實際欄位名核對（yfscreen 0.1.2，2026-07-05 核對）：
  region                           → 地區篩選 (eq "us")
  intradaymarketcap                → 即時市值（$），用 btwn
  intradayprice                    → 即時股價，用 gt
  dayvolume                        → 日成交量（股數），用 gt
  quarterlyrevenuegrowth.quarterly → 季度 YoY 營收成長率（小數格式，0.20 = 20%），用 gte/gt

  回傳 DataFrame 的 ticker 欄位名為 "symbol"（非 "ticker"）。

Yahoo 偶爾改名 → 若篩選回傳空或錯誤先重跑 `yfs.data_filters` 核對。

鐵律（§4.1）：L0 只做 screener 有欄位的條件，均線/形態計算一律落到 L1。
"""

import time
from typing import Optional

import pandas as pd
import yfscreen as yfs

# ── 共用硬門檻（左右池同，§4.2） ─────────────────────────────────────
_CAP_MIN = 150_000_000       # $150M
_CAP_MAX = 20_000_000_000    # $20B（含中型股，§0 命名備注）
_PRICE_MIN = 2.0             # 最新價 ≥ $2
_VOL_MIN = 500_000           # 日成交量（股數）> 500K

# 營收 YoY 門檻（quarterly.yoy，小數制）
_REV_YOY_LEFT  = 0.00   # ≥ 0%（放鬆，左側初期財報通常還沒顯現）
_REV_YOY_RIGHT = 0.20   # ≥ 20%


def _fetch_one_screen(
    rev_yoy_min: float, label: str, max_results: int = 5000
) -> tuple[list[str], dict[str, float]]:
    """
    對 Yahoo Finance screener 跑一次查詢，yfscreen 內部自動分頁（每批 ≤250），
    回傳 (symbol 清單, {symbol: market_cap})。

    market_cap 取自回傳欄位 "marketCap.raw"（已核對 2026-07-05）。

    rev_yoy_min: 小數格式（0.0 = 0%，0.20 = 20%）
    max_results: 最多抓幾筆（防止無上限耗時；實際 universe ~2,500-3,500 筆）
    """
    filters = [
        ["eq",   ["region",                          "us"]],
        ["btwn", ["intradaymarketcap",               _CAP_MIN, _CAP_MAX]],
        ["gt",   ["intradayprice",                   _PRICE_MIN]],
        ["gt",   ["dayvolume",                       _VOL_MIN]],
        ["gte",  ["quarterlyrevenuegrowth.quarterly", rev_yoy_min]],
    ]

    try:
        query   = yfs.create_query(filters)
        payload = yfs.create_payload(
            "equity", query,
            size=max_results, offset=0,
            sort_field="intradaymarketcap", sort_type="DESC",
        )
        df = yfs.get_data(payload)
    except Exception as e:
        print(f"[l0] {label} screener error: {e}")
        return [], {}

    if df is None or df.empty:
        print(f"[l0] {label} screener returned empty")
        return [], {}

    # 欄位名稱：yfscreen 回傳為 "symbol"（已核對 2026-07-05）
    sym_col = "symbol" if "symbol" in df.columns else None
    if sym_col is None:
        # fallback：猜一個含 symbol/ticker 的欄位
        candidates = [c for c in df.columns if c.lower() in ("symbol", "ticker")]
        sym_col = candidates[0] if candidates else None

    if sym_col is None:
        print(f"[l0] {label} 找不到 symbol 欄位，columns={list(df.columns)[:10]}")
        return [], {}

    tickers = df[sym_col].dropna().str.upper().tolist()

    # 市值（marketCap.raw，已核對 2026-07-05；欄位缺失時回空 dict）
    market_caps: dict[str, float] = {}
    mc_col = "marketCap.raw" if "marketCap.raw" in df.columns else None
    if mc_col:
        for sym, mc in zip(df[sym_col], df[mc_col]):
            if pd.notna(sym) and pd.notna(mc):
                market_caps[str(sym).upper()] = float(mc)
    else:
        print(f"[l0] {label} 找不到 marketCap.raw 欄位（Yahoo 可能改名）")

    print(f"[l0] {label} universe = {len(tickers)} 檔")
    return tickers, market_caps


def run_l0(max_results: int = 5000) -> dict:
    """
    執行 L0 粗篩，回傳：
      {
        "left_raw":    list[str],          # 左池候選（rev_yoy ≥ 0%）
        "right_raw":   list[str],          # 右池候選（rev_yoy ≥ 20%）
        "universe":    list[str],          # 左右聯集，去重保序
        "market_caps": dict[str, float],   # {ticker: 市值}（screener marketCap.raw）
      }

    左右池各跑一次 screener，再取聯集作為 L1 需處理的全 universe。
    聯集是因為右池候選一定已包含在左池條件內（rev 20% ⊂ rev 0%），
    但仍分開跑以確保兩條件各自獨立，符合 §4.2 設計。
    """
    print("[l0] 開始左池篩選（rev_yoy ≥ 0%）...")
    left_raw, left_caps = _fetch_one_screen(_REV_YOY_LEFT,  "LEFT",  max_results)

    time.sleep(1)  # 避免短時間連打 Yahoo API

    print("[l0] 開始右池篩選（rev_yoy ≥ 20%）...")
    right_raw, right_caps = _fetch_one_screen(_REV_YOY_RIGHT, "RIGHT", max_results)

    # 聯集去重（dict.fromkeys 保序）
    universe = list(dict.fromkeys(left_raw + right_raw))
    market_caps = {**right_caps, **left_caps}  # 左池較新鮮度無差，重疊時任取

    print(
        f"[l0] 完成 — left_raw={len(left_raw)}, "
        f"right_raw={len(right_raw)}, universe={len(universe)}"
    )
    return {
        "left_raw": left_raw,
        "right_raw": right_raw,
        "universe": universe,
        "market_caps": market_caps,
    }
