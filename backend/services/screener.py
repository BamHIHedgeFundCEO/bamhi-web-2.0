"""BamHI 模型選股 — 把選股邏輯自動化（取代手動貼 AI）。

三類：
  1. VCP   ：跨 17 板塊彙整 VCP 掃描的 🎯 強訊 / 高分標的（來自 sector_rotation 預算 JSON）
  2. Alpha ：BamHI_Dashboard_Latest.csv 套 SCREENING_PLAYBOOK 市值分級篩選
  3. Genesis：BamHI_Genesis_Dashboard_Latest.csv 同分級（確認濾網改 Vol_Z）

分級門檻見 SCREENING_PLAYBOOK.md。
"""
import glob
import json
import os

import pandas as pd

DATA_DIR = "data"
SR_DIR = os.path.join(DATA_DIR, "sector_rotation")

# 市值分級門檻 (對應 SCREENING_PLAYBOOK.md 第二節)
# (級別, MktCap_B 下界, 上界, Dollar_Vol_M 閘門, Ov_Supply 上限, 是否需當日突破確認)
TIERS = [
    ("Mega", 100, float("inf"), 200, 8, False),
    ("Large", 10, 100, 50, 8, False),
    ("Mid", 2, 10, 20, 5, False),
    ("Small", 0.3, 2, 10, 3, True),
    ("Micro", 0, 0.3, 5, 3, True),
]
PER_TIER = 10

ALPHA_COLS = ["Ticker", "Resonance_Score", "Win_Prob", "Price", "RS_Rating",
              "Dollar_Vol_M", "MktCap_B", "Ov_Supply", "Turtle", "ATR_Pct", "Dist_52W_High"]
GENESIS_COLS = ["Ticker", "Resonance_Score", "Win_Prob", "Price", "MA_Conv", "Vol_Z",
                "Breakout", "Dollar_Vol_M", "MktCap_B", "Ov_Supply", "ATR_Pct"]


def screen_models(engine: str) -> dict:
    """Alpha / Genesis 戰報套市值分級篩選，回傳每級最多 10 檔（依 Resonance_Score）。"""
    prefix = "BamHI_Dashboard" if engine == "alpha" else "BamHI_Genesis_Dashboard"
    path = os.path.join(DATA_DIR, f"{prefix}_Latest.csv")
    if not os.path.exists(path):
        return {"engine": engine, "tiers": [], "total_picked": 0, "error": "找不到戰報資料"}

    df = pd.read_csv(path)
    if df.empty or "Resonance_Score" not in df.columns or "MktCap_B" not in df.columns:
        return {"engine": engine, "tiers": [], "total_picked": 0}

    df = df.copy()
    # 共通前處理：Alpha 剔除 RS_Rating >= 300 的新股雜訊
    if engine == "alpha" and "RS_Rating" in df.columns:
        df = df[df["RS_Rating"] < 300]
    if "Win_Prob" in df.columns:
        df["Win_Prob"] = df["Win_Prob"] * 100  # 轉百分比

    cols = ALPHA_COLS if engine == "alpha" else GENESIS_COLS
    keep = [c for c in cols if c in df.columns]

    tiers_out = []
    picked = 0
    for name, lo, hi, dv_min, ov_max, need_confirm in TIERS:
        seg = df[(df["MktCap_B"] >= lo) & (df["MktCap_B"] < hi)]
        if "Dollar_Vol_M" in seg.columns:
            seg = seg[seg["Dollar_Vol_M"] >= dv_min]
        if "Ov_Supply" in seg.columns:
            seg = seg[seg["Ov_Supply"] < ov_max]
        if need_confirm:  # 小/微型強制當日確認
            if engine == "alpha" and "Turtle" in seg.columns:
                seg = seg[seg["Turtle"] == 1]
            elif engine == "genesis" and "Vol_Z" in seg.columns:
                seg = seg[seg["Vol_Z"] > 1.5]
        seg = seg.sort_values("Resonance_Score", ascending=False).head(PER_TIER)
        items = seg[keep].where(pd.notnull(seg[keep]), None).round(3).to_dict(orient="records")
        picked += len(items)
        tiers_out.append({
            "tier": name,
            "gate": {"dollar_vol_min": dv_min, "ov_supply_max": ov_max, "need_confirm": need_confirm},
            "count": len(items),
            "items": items,
        })

    updated_at = _mtime(path)
    return {"engine": engine, "updated_at": updated_at, "columns": keep,
            "total_picked": picked, "tiers": tiers_out}


def screen_vcp(min_score: int = 60) -> dict:
    """跨所有板塊彙整 VCP：取 🎯 強訊或分數 >= min_score，依代碼去重(留最高分)後排序。"""
    rows = []
    for f in glob.glob(os.path.join(SR_DIR, "detail_*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        sector = d.get("sector", "")
        for r in d.get("vcp", []):
            score = r.get("vcp_score") or 0
            if r.get("vcp_pass") or score >= min_score:
                rows.append({
                    "ticker": r.get("ticker"),
                    "sector": sector,
                    "vcp_score": score,
                    "vcp_pass": bool(r.get("vcp_pass")),
                    "contractions": r.get("contractions"),
                    "up_down_vol": r.get("up_down_vol"),
                    "rs_rank": r.get("rs_rank"),
                    "dist_to_high": r.get("dist_to_high"),
                    "price": r.get("price"),
                })

    # 跨板塊去重：同一代碼留最高分（並記錄它出現在哪些板塊）
    best = {}
    for r in rows:
        t = r["ticker"]
        if t not in best or r["vcp_score"] > best[t]["vcp_score"]:
            best[t] = dict(r, sectors=[r["sector"]])
        else:
            best[t]["sectors"].append(r["sector"])
    items = sorted(best.values(), key=lambda x: x["vcp_score"], reverse=True)
    return {"min_score": min_score, "count": len(items), "items": items}


def _mtime(path: str):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
