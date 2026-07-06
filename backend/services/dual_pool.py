"""
backend/services/dual_pool.py — 雙池選股查詢服務

讀 Supabase scores + watchpool + events 表；
無憑證時 fallback 本地 data/dual_pool/scores.jsonl / watchpool.json / events.jsonl。

前端走 FastAPI router，不直連 Supabase（§1 鐵律）。
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Supabase lazy-init（照 insider.py / storage.py 範式）────────────────
_sb_client    = None
_sb_init_done = False
_sb_lock      = threading.Lock()

_DATA_DIR = Path(os.getenv("DUAL_POOL_DATA_DIR", "data/dual_pool"))


def _supabase():
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
            except Exception as e:
                print(f"[dual_pool svc] Supabase init error: {e}")
                _sb_client = None
        else:
            _sb_client = None
        _sb_init_done = True
    return _sb_client


# ── 本地 fallback 讀取 ────────────────────────────────────────────────────

def _local_scores(side: Optional[str] = None) -> list[dict]:
    f = _DATA_DIR / "scores.jsonl"
    if not f.exists():
        return []
    all_rows: list[dict] = []
    try:
        with f.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    all_rows.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        return []
    if not all_rows:
        return []
    latest = max(r.get("score_date", "") for r in all_rows)
    rows = [r for r in all_rows if r.get("score_date") == latest]
    if side:
        rows = [r for r in rows if r.get("side") == side]
    return rows


def _local_watchpool(tickers: Optional[list[str]] = None) -> list[dict]:
    f = _DATA_DIR / "watchpool.json"
    if not f.exists():
        return []
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
        if tickers:
            rows = [r for r in rows if r.get("ticker") in tickers]
        return rows
    except Exception:
        return []


def _local_events(ticker: str, days: int) -> list[dict]:
    f = _DATA_DIR / "events.jsonl"
    if not f.exists():
        return []
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
    rows = []
    try:
        with f.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if r.get("ticker") == ticker:
                        ts = r.get("known_at") or r.get("event_date") or ""
                        if ts >= cutoff:
                            rows.append(r)
                except Exception:
                    pass
    except Exception:
        pass
    return rows


# ── 服務函式 ──────────────────────────────────────────────────────────────

def get_scores(side: Optional[str] = None) -> list[dict]:
    """
    取最新 score_date 的分數列表，join watchpool 特徵。

    回傳欄位：ticker, score_date, side, total, 六因子分,
              gate_passed, veto_flags, data_gaps,
              entangle, slope200, dist_low, adv_dollar, market_cap
    """
    sb = _supabase()
    scores: list[dict] = []

    if sb:
        try:
            # 1. 取最新 score_date
            latest_resp = (
                sb.table("scores")
                .select("score_date")
                .order("score_date", desc=True)
                .limit(1)
                .execute()
            )
            if not latest_resp.data:
                scores = []
            else:
                latest_date = latest_resp.data[0]["score_date"]
                q = sb.table("scores").select("*").eq("score_date", latest_date)
                if side:
                    q = q.eq("side", side)
                resp = q.order("total", desc=True).execute()
                scores = resp.data or []
        except Exception as e:
            print(f"[dual_pool svc] scores load error: {e}")
            scores = _local_scores(side)
    else:
        scores = _local_scores(side)

    if not scores:
        return []

    # 2. 取 watchpool 特徵（join by ticker）
    tickers = [s["ticker"] for s in scores]
    wp_map: dict[str, dict] = {}

    if sb:
        try:
            wp_resp = (
                sb.table("watchpool")
                .select("ticker,entangle,slope200,dist_low,adv_dollar,market_cap")
                .in_("ticker", tickers)
                .execute()
            )
            wp_map = {r["ticker"]: r for r in (wp_resp.data or [])}
        except Exception as e:
            print(f"[dual_pool svc] watchpool join error: {e}")
    if not wp_map:
        for r in _local_watchpool(tickers):
            wp_map[r["ticker"]] = r

    # 3. 合併
    result = []
    for s in scores:
        wp = wp_map.get(s["ticker"], {})
        result.append({
            **s,
            "entangle":   wp.get("entangle"),
            "slope200":   wp.get("slope200"),
            "dist_low":   wp.get("dist_low"),
            "adv_dollar": wp.get("adv_dollar"),
            "market_cap": wp.get("market_cap"),
        })

    return result


def get_events(ticker: str, days: int = 90) -> list[dict]:
    """取該 ticker 近 N 天的 events（前端明細用）。"""
    sb = _supabase()
    if sb:
        try:
            cutoff = (
                datetime.now(tz=timezone.utc) - timedelta(days=days)
            ).isoformat()
            resp = (
                sb.table("events")
                .select(
                    "id,ticker,event_date,known_at,source,source_url,"
                    "event_type,headline,counterparty,counterparty_tier,"
                    "magnitude_usd,magnitude_pct_rev,timeline_months,"
                    "is_recurring,specificity,direction,"
                    "is_integrity_flag,is_dilution_flag,evidence_anchor,extraction_method"
                )
                .eq("ticker", ticker)
                .gte("known_at", cutoff)
                .order("known_at", desc=True)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            print(f"[dual_pool svc] events load error for {ticker}: {e}")

    return _local_events(ticker, days)
