"""
storage.py — watchpool / universe_snapshot 落庫

沿用 backend/services/insider.py 的 lazy-init Supabase 模式：
  有 SUPABASE_URL + SUPABASE_SERVICE_KEY → upsert 到 Supabase
  否則 fallback → 本地檔案：
    watchpool      → data/dual_pool/watchpool.json
    universe_snap  → data/dual_pool/universe_snapshot/YYYY-MM-DD.csv
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# ── 本地 fallback 路徑 ─────────────────────────────────────────────────
_DATA_DIR = Path(os.getenv("DUAL_POOL_DATA_DIR", "data/dual_pool"))
_WATCHPOOL_FILE   = _DATA_DIR / "watchpool.json"
_SNAPSHOT_DIR     = _DATA_DIR / "universe_snapshot"

# ── Supabase lazy-init（照 insider.py 範式）────────────────────────────
_sb_client   = None
_sb_init_done = False
_sb_lock      = threading.Lock()

_TABLE_WATCHPOOL = "watchpool"
_TABLE_SNAPSHOT  = "universe_snapshot"


def _supabase():
    """Lazy-init Supabase client。無憑證回 None（fallback 本地）。"""
    global _sb_client, _sb_init_done
    if _sb_init_done:
        return _sb_client
    with _sb_lock:
        if _sb_init_done:
            return _sb_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if url and key:
            try:
                from supabase import create_client
                _sb_client = create_client(url, key)
                print("[storage] Supabase client initialized")
            except Exception as e:
                print(f"[storage] Supabase init error: {e}")
                _sb_client = None
        else:
            print("[storage] 無 Supabase 憑證 — 使用本地檔案 fallback")
        _sb_init_done = True
    return _sb_client


# ── watchpool 落庫 ────────────────────────────────────────────────────

def upsert_watchpool(records: list[dict]):
    """
    upsert watchpool 表（PK = ticker）。

    records 欄位（§3.1 + §5.6 遲滯/冷卻欄位）：
      ticker, side, market, market_cap, entangle, slope200, dist_low,
      adv_dollar, liquidity_ok, low_adv_streak (int，連續 adv<$2M 交易日數),
      status ('active'|'cooldown'，軟刪除), removed_at (DATE str|None，移出日),
      entered_at (DATE str), updated_at (ISO str)

    fallback JSON 為 schema-less（records 原樣序列化），新欄位自動同步。
    """
    if not records:
        return

    sb = _supabase()
    if sb:
        try:
            sb.table(_TABLE_WATCHPOOL).upsert(records, on_conflict="ticker").execute()
            print(f"[storage] watchpool upsert {len(records)} rows → Supabase")
        except Exception as e:
            print(f"[storage] watchpool Supabase upsert error: {e}")
            _fallback_watchpool(records)
    else:
        _fallback_watchpool(records)


def remove_from_watchpool(tickers: list[str]):
    """從 watchpool 移除指定 ticker。"""
    if not tickers:
        return
    sb = _supabase()
    if sb:
        try:
            sb.table(_TABLE_WATCHPOOL).delete().in_("ticker", tickers).execute()
            print(f"[storage] watchpool removed {len(tickers)} tickers from Supabase")
        except Exception as e:
            print(f"[storage] watchpool remove error: {e}")
    else:
        # fallback：重寫 JSON 排除被移除的
        try:
            if _WATCHPOOL_FILE.exists():
                data = json.loads(_WATCHPOOL_FILE.read_text(encoding="utf-8"))
                data = [r for r in data if r.get("ticker") not in tickers]
                _WATCHPOOL_FILE.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        except Exception as e:
            print(f"[storage] watchpool local remove error: {e}")


def load_watchpool() -> list[dict]:
    """載入目前 watchpool（用於遲滯判斷）。"""
    sb = _supabase()
    if sb:
        try:
            resp = sb.table(_TABLE_WATCHPOOL).select("*").execute()
            return resp.data or []
        except Exception as e:
            print(f"[storage] watchpool load error: {e}")
    # fallback
    if _WATCHPOOL_FILE.exists():
        try:
            return json.loads(_WATCHPOOL_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[storage] watchpool local load error: {e}")
    return []


def _fallback_watchpool(records: list[dict]):
    """本地 JSON 更新（upsert 語意：以 ticker 為鍵）。"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict] = {}
    if _WATCHPOOL_FILE.exists():
        try:
            for r in json.loads(_WATCHPOOL_FILE.read_text(encoding="utf-8")):
                existing[r["ticker"]] = r
        except Exception:
            pass
    for r in records:
        existing[r["ticker"]] = r
    _WATCHPOOL_FILE.write_text(
        json.dumps(list(existing.values()), ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"[storage] watchpool fallback → {_WATCHPOOL_FILE} ({len(existing)} rows)")


# ── universe_snapshot 落庫 ────────────────────────────────────────────

def save_universe_snapshot(snapshot_date: date, records: list[dict]):
    """
    儲存每日 universe_snapshot（§3.5）。

    records 欄位：
      snapshot_date, ticker, market_cap, adv_dollar, close

    Supabase：upsert（PK = snapshot_date + ticker）
    Fallback：data/dual_pool/universe_snapshot/YYYY-MM-DD.csv
    """
    if not records:
        return

    sb = _supabase()
    if sb:
        try:
            sb.table(_TABLE_SNAPSHOT).upsert(
                records, on_conflict="snapshot_date,ticker"
            ).execute()
            print(f"[storage] universe_snapshot {snapshot_date} upsert {len(records)} rows → Supabase")
        except Exception as e:
            print(f"[storage] universe_snapshot Supabase error: {e}")
            _fallback_snapshot(snapshot_date, records)
    else:
        _fallback_snapshot(snapshot_date, records)


def _fallback_snapshot(snapshot_date: date, records: list[dict]):
    """本地 CSV fallback。"""
    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = _SNAPSHOT_DIR / f"{snapshot_date}.csv"
    df = pd.DataFrame(records)
    df.to_csv(path, index=False)
    print(f"[storage] universe_snapshot fallback → {path} ({len(records)} rows)")
