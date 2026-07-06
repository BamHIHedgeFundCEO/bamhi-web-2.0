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


# ── edgar_processed 落庫（accession 冪等記錄，解決 Render 暫態FS 問題）──────

_TABLE_PROCESSED  = "edgar_processed"
_PROCESSED_FILE   = _DATA_DIR / "processed_accessions.json"


def load_processed_accessions() -> set[str]:
    """
    載入已處理的 EDGAR accession number 集合（冪等用）。

    有 Supabase 憑證 → SELECT accession_no FROM edgar_processed（全表，跨部署持久）。
    無憑證 → fallback 本地 JSON（本機開發路徑不變）。
    """
    sb = _supabase()
    if sb:
        try:
            resp = sb.table(_TABLE_PROCESSED).select("accession_no").execute()
            return {row["accession_no"] for row in (resp.data or [])}
        except Exception as e:
            print(f"[storage] edgar_processed load error: {e}")
    # fallback
    if _PROCESSED_FILE.exists():
        try:
            return set(json.loads(_PROCESSED_FILE.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[storage] edgar_processed local load error: {e}")
    return set()


def add_processed_accessions(accessions: set[str]):
    """
    新增已處理 accession（INSERT ON CONFLICT DO NOTHING，冪等）。

    Supabase：bulk upsert with ignore_duplicates，只寫入尚未存在的記錄。
    Fallback：本地 JSON 讀 + merge + 寫（同樣冪等）。
    """
    if not accessions:
        return

    sb = _supabase()
    if sb:
        try:
            records = [{"accession_no": a} for a in accessions]
            try:
                sb.table(_TABLE_PROCESSED).upsert(
                    records,
                    on_conflict="accession_no",
                    ignore_duplicates=True,
                ).execute()
            except TypeError:
                # 舊版 supabase-py 不支援 ignore_duplicates，改普通 upsert
                sb.table(_TABLE_PROCESSED).upsert(
                    records, on_conflict="accession_no"
                ).execute()
            print(f"[storage] edgar_processed upsert {len(accessions)} rows → Supabase")
            return
        except Exception as e:
            print(f"[storage] edgar_processed Supabase upsert error: {e}")
    # fallback：本地 JSON merge
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if _PROCESSED_FILE.exists():
        try:
            existing = set(json.loads(_PROCESSED_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    merged = existing | accessions
    _PROCESSED_FILE.write_text(
        json.dumps(sorted(merged), ensure_ascii=False), encoding="utf-8"
    )
    print(f"[storage] edgar_processed fallback → {_PROCESSED_FILE} ({len(merged)} total)")


# ── events 落庫（L2 催化劑抽取輸出）────────────────────────────────

_TABLE_EVENTS  = "events"
_EVENTS_FILE   = _DATA_DIR / "events.jsonl"


def upsert_events(records: list[dict]):
    """
    upsert events 表（§3.2 + 冪等鍵 accession_no+seq_in_filing）。

    Supabase：ON CONFLICT (accession_no, seq_in_filing) DO NOTHING（§8.1 冪等）
    Fallback：本地 events.jsonl append（去重同鍵）

    注意：records 不得包含公告全文（§6.8 版權）。
    """
    if not records:
        return

    sb = _supabase()
    if sb:
        try:
            # ignore_duplicates=True → ON CONFLICT DO NOTHING（supabase-py v2+）
            try:
                sb.table(_TABLE_EVENTS).upsert(
                    records,
                    on_conflict="accession_no,seq_in_filing",
                    ignore_duplicates=True,
                ).execute()
            except TypeError:
                # 舊版 supabase-py 不支援 ignore_duplicates，改普通 upsert（仍冪等）
                sb.table(_TABLE_EVENTS).upsert(
                    records,
                    on_conflict="accession_no,seq_in_filing",
                ).execute()
            print(f"[storage] events upsert {len(records)} rows → Supabase")
        except Exception as e:
            print(f"[storage] events Supabase upsert error: {e}")
            _fallback_events(records)
    else:
        _fallback_events(records)


def _fallback_events(records: list[dict]):
    """
    本地 JSONL append，去重同鍵 (accession_no, seq_in_filing)。
    保證重跑不新增列（§8.1 冪等）。
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 載入已有 keys
    existing_keys: set[tuple] = set()
    if _EVENTS_FILE.exists():
        with _EVENTS_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    existing_keys.add(
                        (r.get("accession_no"), r.get("seq_in_filing"))
                    )
                except Exception:
                    pass

    new_count = 0
    with _EVENTS_FILE.open("a", encoding="utf-8") as fh:
        for r in records:
            key = (r.get("accession_no"), r.get("seq_in_filing"))
            if key in existing_keys:
                continue
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            existing_keys.add(key)
            new_count += 1

    skipped = len(records) - new_count
    print(
        f"[storage] events fallback → {_EVENTS_FILE} "
        f"(+{new_count} new, {skipped} skipped/dup)"
    )
