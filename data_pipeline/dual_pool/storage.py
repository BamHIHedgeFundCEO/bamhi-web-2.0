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
from datetime import date, datetime, timezone
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


def load_events(days: int = 365) -> list[dict]:
    """
    載入近 N 天的 events（給 scoring 用）。

    Supabase：SELECT * FROM events WHERE known_at >= now()-interval 'N days'
    Fallback：讀本地 events.jsonl，依 known_at 過濾。
    """
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()

    sb = _supabase()
    if sb:
        try:
            resp = (
                sb.table(_TABLE_EVENTS)
                .select("*")
                .gte("known_at", cutoff)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            print(f"[storage] events load error: {e}")

    # fallback：本地 JSONL
    records = []
    if _EVENTS_FILE.exists():
        try:
            with _EVENTS_FILE.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        ts = r.get("known_at") or r.get("event_date") or ""
                        if ts >= cutoff:
                            records.append(r)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[storage] events local load error: {e}")
    return records


# ── scores 落庫（L3 評分輸出）────────────────────────────────────────────

_TABLE_SCORES = "scores"
_SCORES_FILE  = _DATA_DIR / "scores.jsonl"


def upsert_scores(records: list[dict]):
    """
    upsert scores 表（PK = ticker + score_date，冪等，§3.3）。

    Supabase：ON CONFLICT (ticker, score_date) DO UPDATE
    Fallback：本地 JSONL（覆寫同鍵）

    欄位：ticker, score_date, side, total,
          catalyst, institution, op_leverage, partnership, insider, narrative,
          gate_passed, veto_flags(TEXT[]), data_gaps(TEXT[])
    """
    if not records:
        return

    sb = _supabase()
    if sb:
        try:
            sb.table(_TABLE_SCORES).upsert(
                records, on_conflict="ticker,score_date"
            ).execute()
            print(f"[storage] scores upsert {len(records)} rows → Supabase")
        except Exception as e:
            print(f"[storage] scores Supabase upsert error: {e}")
            _fallback_scores(records)
    else:
        _fallback_scores(records)


def load_scores(score_date: Optional[date] = None) -> list[dict]:
    """
    載入指定日期的 scores（預設：最新 score_date）。

    Supabase：
      有日期 → SELECT * WHERE score_date=X
      無日期 → SELECT * WHERE score_date=(SELECT MAX(score_date) FROM scores)
    Fallback：本地 JSONL 過濾。
    """
    sb = _supabase()
    if sb:
        try:
            if score_date:
                resp = (
                    sb.table(_TABLE_SCORES)
                    .select("*")
                    .eq("score_date", score_date.isoformat())
                    .execute()
                )
            else:
                # 先查最新日期
                latest_resp = (
                    sb.table(_TABLE_SCORES)
                    .select("score_date")
                    .order("score_date", desc=True)
                    .limit(1)
                    .execute()
                )
                if not latest_resp.data:
                    return []
                latest_date = latest_resp.data[0]["score_date"]
                resp = (
                    sb.table(_TABLE_SCORES)
                    .select("*")
                    .eq("score_date", latest_date)
                    .execute()
                )
            return resp.data or []
        except Exception as e:
            print(f"[storage] scores load error: {e}")

    # fallback：本地 JSONL
    records = []
    if _SCORES_FILE.exists():
        try:
            all_records = []
            with _SCORES_FILE.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        all_records.append(json.loads(line))
                    except Exception:
                        pass
            if score_date:
                records = [r for r in all_records if r.get("score_date") == score_date.isoformat()]
            elif all_records:
                latest = max(r.get("score_date", "") for r in all_records)
                records = [r for r in all_records if r.get("score_date") == latest]
        except Exception as e:
            print(f"[storage] scores local load error: {e}")
    return records


def _fallback_scores(records: list[dict]):
    """本地 JSONL 更新（upsert 語意：以 ticker+score_date 為鍵）。"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[tuple, dict] = {}

    if _SCORES_FILE.exists():
        try:
            with _SCORES_FILE.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        key = (r.get("ticker"), r.get("score_date"))
                        existing[key] = r
                    except Exception:
                        pass
        except Exception:
            pass

    for r in records:
        key = (r.get("ticker"), r.get("score_date"))
        existing[key] = r

    with _SCORES_FILE.open("w", encoding="utf-8") as fh:
        for r in existing.values():
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"[storage] scores fallback → {_SCORES_FILE} ({len(existing)} rows)")


# ── institution_quarterly 落庫（§6.9 13F 季度 job）───────────────────────

_TABLE_INSTITUTION = "institution_quarterly"
_INSTITUTION_FILE  = _DATA_DIR / "institution_quarterly.json"


def upsert_institution_quarterly(records: list[dict]):
    """
    upsert institution_quarterly（PK = ticker + quarter）。

    records 欄位：ticker, quarter, new_holders, total_holders, known_at
    Supabase：ON CONFLICT (ticker, quarter) DO UPDATE
    Fallback：本地 JSON（以 ticker+quarter 為鍵）
    """
    if not records:
        return

    sb = _supabase()
    if sb:
        try:
            sb.table(_TABLE_INSTITUTION).upsert(
                records, on_conflict="ticker,quarter"
            ).execute()
            print(f"[storage] institution_quarterly upsert {len(records)} rows → Supabase")
            return
        except Exception as e:
            print(f"[storage] institution_quarterly Supabase upsert error: {e}")

    # fallback：本地 JSON
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict] = {}
    if _INSTITUTION_FILE.exists():
        try:
            existing = json.loads(_INSTITUTION_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    for r in records:
        key = f"{r['ticker']}|{r['quarter']}"
        existing[key] = r
    _INSTITUTION_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"[storage] institution_quarterly fallback → {_INSTITUTION_FILE} ({len(existing)} rows)")


def load_institution_latest_batch(tickers: list[str]) -> dict[str, Optional[int]]:
    """
    批次載入各 ticker 最新季的 new_holders（scoring 用）。
    回傳 {ticker: new_holders}，無資料者對應 None。
    """
    if not tickers:
        return {}

    sb = _supabase()
    if sb:
        try:
            # Supabase 不支援 DISTINCT ON；用 ORDER BY + 逐 ticker 取最新
            resp = (
                sb.table(_TABLE_INSTITUTION)
                .select("ticker,quarter,new_holders")
                .in_("ticker", tickers)
                .order("quarter", desc=True)
                .execute()
            )
            # 每個 ticker 只取最新 quarter（已按 quarter desc 排序）
            result: dict[str, int] = {}
            for row in (resp.data or []):
                t = row["ticker"]
                if t not in result:  # 第一筆就是最新季
                    result[t] = row["new_holders"]
            return {t: result.get(t) for t in tickers}
        except Exception as e:
            print(f"[storage] institution_quarterly load error: {e}")

    # fallback：本地 JSON
    result = {}
    if _INSTITUTION_FILE.exists():
        try:
            data = json.loads(_INSTITUTION_FILE.read_text(encoding="utf-8"))
            # 找每個 ticker 最新 quarter
            ticker_quarters: dict[str, list] = {}
            for key, rec in data.items():
                t = rec.get("ticker", "")
                if t in tickers:
                    ticker_quarters.setdefault(t, []).append(rec)
            for t, recs in ticker_quarters.items():
                latest = max(recs, key=lambda r: r.get("quarter", ""))
                result[t] = latest.get("new_holders")
        except Exception as e:
            print(f"[storage] institution_quarterly local load error: {e}")

    return {t: result.get(t) for t in tickers}


# ── cusip_map（CUSIP→ticker 對映，跨部署持久）─────────────────────────

_TABLE_CUSIP_MAP = "cusip_map"
_CUSIP_MAP_FILE  = _DATA_DIR / "cusip_map.json"


def load_cusip_map() -> dict[str, Optional[str]]:
    """
    載入 CUSIP→ticker 對映（institution_13f.py 查 OpenFIGI 前先讀）。
    Supabase cusip_map 表為主（跨部署持久）；無憑證/失敗 → 本地 JSON。
    分頁讀全表（supabase-py 預設 1000 列上限）。
    """
    sb = _supabase()
    if sb:
        try:
            result: dict[str, Optional[str]] = {}
            page_size = 1000
            offset = 0
            while True:
                resp = (
                    sb.table(_TABLE_CUSIP_MAP)
                    .select("cusip,ticker")
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                rows = resp.data or []
                for row in rows:
                    result[row["cusip"]] = row.get("ticker")
                if len(rows) < page_size:
                    break
                offset += page_size
            if result:
                print(f"[storage] cusip_map loaded {len(result)} rows ← Supabase")
                return result
        except Exception as e:
            print(f"[storage] cusip_map load error: {e}")

    # fallback：本地 JSON
    if _CUSIP_MAP_FILE.exists():
        try:
            return json.loads(_CUSIP_MAP_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[storage] cusip_map local load error: {e}")
    return {}


def upsert_cusip_map(mapping: dict[str, Optional[str]]):
    """
    upsert CUSIP→ticker 對映（含查無結果的 None，避免重複查同一 CUSIP）。
    Supabase：ON CONFLICT (cusip) DO UPDATE；fallback 本地 JSON merge。
    """
    if not mapping:
        return

    sb = _supabase()
    if sb:
        try:
            now = datetime.now().astimezone().isoformat()
            records = [
                {"cusip": c, "ticker": t, "updated_at": now}
                for c, t in mapping.items()
            ]
            # 分批 upsert（避免單請求過大）
            for i in range(0, len(records), 500):
                sb.table(_TABLE_CUSIP_MAP).upsert(
                    records[i: i + 500], on_conflict="cusip"
                ).execute()
            print(f"[storage] cusip_map upsert {len(records)} rows → Supabase")
            return
        except Exception as e:
            print(f"[storage] cusip_map Supabase upsert error: {e}")

    # fallback：本地 JSON merge
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Optional[str]] = {}
    if _CUSIP_MAP_FILE.exists():
        try:
            existing = json.loads(_CUSIP_MAP_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing.update(mapping)
    _CUSIP_MAP_FILE.write_text(
        json.dumps(existing, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[storage] cusip_map fallback → {_CUSIP_MAP_FILE} ({len(existing)} rows)")


def load_institution_holders_cache(quarter: str) -> dict[str, set]:
    """
    載入某季 ticker→filer CIK 集合快取（institution_13f.py 用，計算 new_holders 用）。
    本地 JSON only（太大不進 Supabase），格式：{ticker: [cik1, cik2, ...]}
    """
    cache_file = _DATA_DIR / f"institution_holders_{quarter.replace('-','')}.json"
    if not cache_file.exists():
        return {}
    try:
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        return {t: set(ciks) for t, ciks in raw.items()}
    except Exception as e:
        print(f"[storage] institution holders cache load error ({quarter}): {e}")
        return {}


def save_institution_holders_cache(quarter: str, holders: dict[str, set]):
    """儲存某季 ticker→filer CIK 集合快取。"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _DATA_DIR / f"institution_holders_{quarter.replace('-','')}.json"
    try:
        serializable = {t: sorted(ciks) for t, ciks in holders.items()}
        cache_file.write_text(
            json.dumps(serializable, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[storage] institution holders cache → {cache_file}")
    except Exception as e:
        print(f"[storage] institution holders cache save error ({quarter}): {e}")


# ── track_record 落庫（§3.4 guidance/commitment 兌現率）────────────────────

_TABLE_TRACK_RECORD = "track_record"
_TRACK_RECORD_FILE  = _DATA_DIR / "track_record.json"


def upsert_track_record(records: list[dict]):
    """
    INSERT track_record（新 promise；ON CONFLICT DO NOTHING，不覆蓋已有紀錄）。

    records 欄位：ticker, promise_date, promise_text, promise_deadline,
                  verified(NULL), verify_date(NULL), verify_method(NULL), verify_attempts(0)
    Supabase：ON CONFLICT (ticker, promise_date, promise_text) DO NOTHING
    Fallback：本地 JSON（以 ticker+promise_date+前50字 為鍵）
    """
    if not records:
        return

    sb = _supabase()
    if sb:
        try:
            try:
                sb.table(_TABLE_TRACK_RECORD).upsert(
                    records,
                    on_conflict="ticker,promise_date,promise_text",
                    ignore_duplicates=True,
                ).execute()
            except TypeError:
                sb.table(_TABLE_TRACK_RECORD).upsert(
                    records,
                    on_conflict="ticker,promise_date,promise_text",
                ).execute()
            print(f"[storage] track_record upsert {len(records)} rows → Supabase")
            return
        except Exception as e:
            print(f"[storage] track_record Supabase upsert error: {e}")

    # fallback：本地 JSON
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict] = {}
    if _TRACK_RECORD_FILE.exists():
        try:
            existing = json.loads(_TRACK_RECORD_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    for r in records:
        key = f"{r['ticker']}|{r['promise_date']}|{str(r.get('promise_text',''))[:50]}"
        if key not in existing:  # DO NOTHING semantics
            existing[key] = r
    _TRACK_RECORD_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"[storage] track_record fallback → {_TRACK_RECORD_FILE} ({len(existing)} rows)")


def load_track_record_expired(before_date: date) -> list[dict]:
    """
    載入 promise_deadline < before_date 且 verified IS NULL 的 promise（verify job 用）。
    包含 verify_attempts 欄位供 verify job 判斷是否升級為人工佇列。
    """
    sb = _supabase()
    if sb:
        try:
            resp = (
                sb.table(_TABLE_TRACK_RECORD)
                .select("*")
                .lt("promise_deadline", before_date.isoformat())
                .is_("verified", "null")
                .execute()
            )
            return resp.data or []
        except Exception as e:
            print(f"[storage] track_record expired load error: {e}")

    # fallback
    records = []
    if _TRACK_RECORD_FILE.exists():
        try:
            all_recs = list(json.loads(_TRACK_RECORD_FILE.read_text(encoding="utf-8")).values())
            for r in all_recs:
                deadline = r.get("promise_deadline", "9999-12-31")
                if deadline < before_date.isoformat() and r.get("verified") is None:
                    records.append(r)
        except Exception as e:
            print(f"[storage] track_record local load error: {e}")
    return records


def load_track_record_completed(ticker: str) -> list[dict]:
    """
    載入 ticker 所有 verified IS NOT NULL 的紀錄（scoring guidance_missed veto 用）。
    """
    sb = _supabase()
    if sb:
        try:
            resp = (
                sb.table(_TABLE_TRACK_RECORD)
                .select("ticker,verified")
                .eq("ticker", ticker)
                .not_.is_("verified", "null")
                .execute()
            )
            return resp.data or []
        except Exception as e:
            print(f"[storage] track_record completed load error: {e}")

    # fallback
    records = []
    if _TRACK_RECORD_FILE.exists():
        try:
            all_recs = list(json.loads(_TRACK_RECORD_FILE.read_text(encoding="utf-8")).values())
            records = [
                r for r in all_recs
                if r.get("ticker") == ticker and r.get("verified") is not None
            ]
        except Exception:
            pass
    return records


# ── job state（13F 等長時任務跨 Render 重啟持久；Supabase only，無本地 fallback）──

_TABLE_JOB_STATE = "dual_pool_job_state"


def upsert_job_state(job_type: str, data: dict) -> None:
    """Upsert job state (best-effort; no-op if Supabase not configured)."""
    sb = _supabase()
    if not sb:
        return
    try:
        payload = {
            "job_type":   job_type,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **data,
        }
        sb.table(_TABLE_JOB_STATE).upsert(payload, on_conflict="job_type").execute()
    except Exception as e:
        print(f"[storage] upsert_job_state({job_type}) error: {e}")


def load_job_state(job_type: str) -> Optional[dict]:
    """Load job state from Supabase. Returns None if not found or Supabase unavailable."""
    sb = _supabase()
    if not sb:
        return None
    try:
        resp = sb.table(_TABLE_JOB_STATE).select("*").eq("job_type", job_type).execute()
        if resp.data:
            return resp.data[0]
    except Exception as e:
        print(f"[storage] load_job_state({job_type}) error: {e}")
    return None


def update_track_record(updates: list[dict]):
    """
    更新 track_record 的 verified/verify_date/verify_method/verify_attempts。

    updates 欄位：ticker, promise_date, promise_text, verified, verify_date,
                  verify_method, verify_attempts
    Supabase：UPSERT（以 id 或 ticker+promise_date+promise_text 更新）
    Fallback：本地 JSON 同鍵覆蓋
    """
    if not updates:
        return

    sb = _supabase()
    if sb:
        try:
            sb.table(_TABLE_TRACK_RECORD).upsert(
                updates,
                on_conflict="ticker,promise_date,promise_text",
            ).execute()
            print(f"[storage] track_record update {len(updates)} rows → Supabase")
            return
        except Exception as e:
            print(f"[storage] track_record Supabase update error: {e}")

    # fallback
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict] = {}
    if _TRACK_RECORD_FILE.exists():
        try:
            existing = json.loads(_TRACK_RECORD_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    for r in updates:
        key = f"{r['ticker']}|{r['promise_date']}|{str(r.get('promise_text',''))[:50]}"
        if key in existing:
            existing[key].update(r)
        else:
            existing[key] = r
    _TRACK_RECORD_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"[storage] track_record fallback update → {_TRACK_RECORD_FILE}")
