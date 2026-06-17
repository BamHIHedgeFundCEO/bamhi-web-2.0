"""SEC Form 4 內部人交易服務 — edgartools + 背景累積 cache。

Transaction code 語意：
  P  公開市場買入  → 真實看多訊號（本人花錢買）
  S  公開市場賣出  → 真實看空訊號
  M  行權取股      → 中性（履約期權義務，非自願買入）
  C  期權轉換      → 同 M
  F  稅務代售      → 噪音（sell-to-cover，強制賣出抵稅款）
  A/G 獎勵/贈與   → 不追蹤

持久化層：
  若 SUPABASE_URL + SUPABASE_SERVICE_KEY 設定 → 使用 Supabase DB。
  否則 fallback → data/insider_cache.json（本地 / Render Persistent Disk）。
"""
import gc
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import edgar
import pandas as pd

from backend.services.discord_notify import MEGA_THRESHOLD, notify_mega_trade

edgar.set_identity("frank940702@gmail.com")

_cache_dir = Path(os.getenv("INSIDER_CACHE_DIR", "data"))
CACHE_FILE = _cache_dir / "insider_cache.json"

_STOCK_CACHE: dict[str, dict] = {}
_STOCK_TTL = 900

BUY_CODES = {"P"}
SELL_CODES = {"S"}
TAX_CODES = {"F"}
ALL_TRACKED = BUY_CODES | SELL_CODES | TAX_CODES

TYPE_LABEL = {
    "P": "P-Purchase",  # 公開市場買入（真實看多訊號）
    "S": "S-Sale",      # 公開市場賣出（真實看空訊號）
    "F": "F-TaxSale",   # 稅務代售（強制賣出，非訊號）
}

# In-memory accumulation cache
_CACHE_TXNS: list[dict] = []
_CACHE_ACCESSIONS: set[str] = set()
_CACHE_LOCK = threading.Lock()
_CACHE_UPDATED_AT: str = ""

# ── Supabase client (lazy init) ───────────────────────────────────────────────

_sb_client = None
_sb_init_done = False
_sb_lock = threading.Lock()

_SUPABASE_TABLE = "insider_transactions"
_SUPABASE_STRIP_KEYS = {"id", "created_at"}


def _supabase():
    """Lazy-init Supabase client. Returns None if env vars not set."""
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
                print("[insider] Supabase client initialized")
            except Exception as e:
                print(f"[insider] Supabase init error: {e}")
                _sb_client = None
        else:
            print("[insider] SUPABASE_SERVICE_KEY not set — using local JSON cache")
        _sb_init_done = True
    return _sb_client


def _strip_sb_fields(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in _SUPABASE_STRIP_KEYS}


def _load_from_supabase(sb) -> list[dict]:
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    try:
        resp = (
            sb.table(_SUPABASE_TABLE)
            .select("*")
            .gte("transaction_date", cutoff)
            .execute()
        )
        rows = resp.data or []
        return [_strip_sb_fields(r) for r in rows]
    except Exception as e:
        print(f"[insider] Supabase load error: {e}")
        return []


def _upsert_to_supabase(sb, txns: list[dict]):
    if not txns:
        return
    try:
        records = [_strip_sb_fields(t) for t in txns]
        sb.table(_SUPABASE_TABLE).upsert(records, on_conflict="accession_no").execute()
    except Exception as e:
        print(f"[insider] Supabase upsert error: {e}")


# ── filing parser ─────────────────────────────────────────────────────────────

def _filing_to_txns(f, file_date: str = "", accession_no: str = "") -> list[dict]:
    """edgartools Filing → transaction dicts (P / S / F; S tagged is_exercise_sale if M/C also present)."""
    try:
        obj = f.obj()
        df = obj.to_dataframe()
    except Exception as e:
        print(f"[insider] parse error {accession_no}: {e}")
        return []

    if df is None or df.empty:
        return []

    # First pass: detect option exercise in this filing (cashless exercise = M + S same Form 4)
    all_codes = {str(r).strip() for r in df["Code"].dropna() if pd.notna(r)}
    has_exercise = bool(all_codes & {"M", "C"})

    PROCESS_CODES = {"P", "S", "F"}
    txns = []
    for _, row in df.iterrows():
        code = str(row.get("Code", "") or "").strip()
        if code not in PROCESS_CODES:
            continue

        shares_raw = row.get("Shares")
        price_raw = row.get("Price")
        value_raw = row.get("Value")

        shares = float(shares_raw) if shares_raw is not None and pd.notna(shares_raw) else 0.0
        price = float(price_raw) if price_raw is not None and pd.notna(price_raw) else 0.0
        value = float(value_raw) if value_raw is not None and pd.notna(value_raw) else round(shares * price, 2)

        txn_date_raw = row.get("Date", "")
        if hasattr(txn_date_raw, "date"):
            txn_date = txn_date_raw.date().isoformat()
        elif txn_date_raw:
            txn_date = str(txn_date_raw)[:10]
        else:
            txn_date = file_date

        ticker = str(row.get("Ticker", "") or "").strip().upper()
        company = str(row.get("Issuer", "") or "").strip()
        insider_name = str(row.get("Insider", "") or "").strip()
        position = str(row.get("Position", "") or "").strip()

        # S in same filing as M/C = cashless exercise sale, not a real bearish signal
        is_exercise_sale = (code == "S" and has_exercise)
        txn_type = "S-ExerciseSale" if is_exercise_sale else TYPE_LABEL.get(code, code)

        is_buy = code in BUY_CODES
        txns.append({
            "symbol": ticker,
            "company": company,
            "reporting_name": insider_name,
            "reporting_role": position,
            "transaction_type": txn_type,
            "transaction_code": code,
            "is_exercise_sale": is_exercise_sale,
            "shares": shares if is_buy else -shares,
            "price": price,
            "amount": abs(value),
            "transaction_date": txn_date,
            "filing_date": file_date,
            "accession_no": accession_no,
        })
    return txns


# ── cache persistence (local JSON fallback) ───────────────────────────────────

def _load_cache_file() -> tuple[list[dict], set[str]]:
    if not CACHE_FILE.exists():
        return [], set()
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        txns = data.get("transactions", [])
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        txns = [t for t in txns if t.get("transaction_date", "") >= cutoff]
        return txns, {t["accession_no"] for t in txns}
    except Exception as e:
        print(f"[insider] cache load error: {e}")
        return [], set()


def _save_cache_file(txns: list[dict], updated_at: str):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps({"updated_at": updated_at, "transactions": txns}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[insider] cache save error: {e}")


def init_cache():
    """Startup: load persisted cache into memory (Supabase → JSON fallback)."""
    global _CACHE_TXNS, _CACHE_ACCESSIONS, _CACHE_UPDATED_AT
    sb = _supabase()
    if sb:
        txns = _load_from_supabase(sb)
        source = "supabase"
    else:
        txns, _ = _load_cache_file()
        source = "json"
    with _CACHE_LOCK:
        _CACHE_TXNS = txns
        _CACHE_ACCESSIONS = {t["accession_no"] for t in txns}
        _CACHE_UPDATED_AT = datetime.now().isoformat(timespec="seconds")
    print(f"[insider] cache loaded: {len(txns)} transactions (source={source})")


# ── background accumulator ────────────────────────────────────────────────────

def bg_update(n: int = 200):
    """Fetch n newest Form 4 filings, skip already processed, append new ones."""
    global _CACHE_TXNS, _CACHE_ACCESSIONS, _CACHE_UPDATED_AT
    print(f"[insider] bg_update called (n={n})", flush=True)

    try:
        filings_obj = edgar.get_filings(form="4")
        filing_list = list(filings_obj.head(n))
    except Exception as e:
        print(f"[insider] bg_update listing error: {e}")
        return

    with _CACHE_LOCK:
        seen = set(_CACHE_ACCESSIONS)

    to_process = [f for f in filing_list if f.accession_no not in seen]
    if not to_process:
        print(f"[insider] bg_update: no new filings (fetched {n})")
        return

    print(f"[insider] bg_update: processing {len(to_process)} new filings")

    def _parse_one(f):
        acc = f.accession_no
        fd = str(getattr(f, "filing_date", "") or "")[:10]
        return _filing_to_txns(f, fd, acc), acc

    new_txns: list[dict] = []
    new_accs: set[str] = set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(_parse_one, f): f for f in to_process}
        for fut in as_completed(futures):
            try:
                txns, acc = fut.result()
            except Exception:
                continue
            new_accs.add(acc)
            for t in txns:
                new_txns.append(t)
                # Mega alert: open market buy/sell only (P or S, not tax withholding)
                if t["amount"] >= MEGA_THRESHOLD and t["transaction_code"] in ("P", "S"):
                    notify_mega_trade({
                        "symbol": t["symbol"],
                        "reportingName": t["reporting_name"],
                        "reportingOwner": t["reporting_role"],
                        "transactionType": t["transaction_type"],
                        "securitiesTransacted": abs(t["shares"]),
                        "price": t["price"],
                        "amount": t["amount"],
                        "transactionDate": t["transaction_date"],
                        "filingDate": t["filing_date"],
                    })

    if not new_txns and not new_accs:
        return

    now_str = datetime.now().isoformat(timespec="seconds")
    cutoff = (date.today() - timedelta(days=90)).isoformat()

    with _CACHE_LOCK:
        _CACHE_TXNS.extend(new_txns)
        _CACHE_ACCESSIONS.update(new_accs)
        _CACHE_TXNS = [t for t in _CACHE_TXNS if t.get("transaction_date", "") >= cutoff]
        _CACHE_ACCESSIONS = {t["accession_no"] for t in _CACHE_TXNS}
        _CACHE_UPDATED_AT = now_str
        snapshot = list(_CACHE_TXNS)

    # Persist: Supabase (only new txns) → JSON fallback (full snapshot)
    sb = _supabase()
    if sb:
        _upsert_to_supabase(sb, new_txns)
    else:
        _save_cache_file(snapshot, now_str)

    gc.collect()
    print(f"[insider] bg_update done: +{len(new_txns)} txns ({len(new_accs)} filings), cache={len(snapshot)}")


# ── public API ────────────────────────────────────────────────────────────────

def get_radar(days: int, sort: str) -> tuple[list[dict], str, int]:
    """
    Aggregate from cache, separate P/S/M/F buckets.
    Returns (top20_items, last_updated, cache_size).
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    with _CACHE_LOCK:
        relevant = [t for t in _CACHE_TXNS if t.get("transaction_date", "") >= cutoff]
        updated_at = _CACHE_UPDATED_AT
        cache_size = len(_CACHE_TXNS)

    agg: dict[str, dict] = {}
    for t in relevant:
        sym = t.get("symbol", "")
        if not sym:
            continue
        entry = agg.setdefault(sym, {
            "symbol": sym,
            "company": t.get("company", ""),
            "latest_date": "",
            "buy_amount": 0.0,           # P — 公開買入（真實訊號）
            "sell_amount": 0.0,          # S — 公開賣出（真實訊號，排除行權套現）
            "exercise_sale_amount": 0.0, # S+M — 行權套現（中性，非看空訊號）
            "tax_sale_amount": 0.0,      # F — 稅務代售（非訊號）
            "net_buy": 0.0,              # P - S（僅真實訊號）
            "insiders": set(),
        })
        dt = t.get("transaction_date", "")
        if dt > entry["latest_date"]:
            entry["latest_date"] = dt
        code = t["transaction_code"]
        amt = t["amount"]
        if code == "P":
            entry["buy_amount"] += amt
        elif code == "S":
            if t.get("is_exercise_sale"):
                entry["exercise_sale_amount"] += amt
            else:
                entry["sell_amount"] += amt
        elif code in TAX_CODES:
            entry["tax_sale_amount"] += amt
        if t["reporting_name"]:
            entry["insiders"].add(t["reporting_name"])

    items = []
    for entry in agg.values():
        entry["net_buy"] = entry["buy_amount"] - entry["sell_amount"]
        entry["insider_count"] = len(entry["insiders"])
        del entry["insiders"]
        items.append(entry)

    valid_sorts = {"buy_amount", "sell_amount", "net_buy", "latest_date", "tax_sale_amount"}
    sort_key = sort if sort in valid_sorts else "buy_amount"
    items.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=True)

    return items[:20], updated_at, cache_size


def fetch_stock(symbol: str, limit: int = 50) -> list[dict]:
    """即時抓單股 Form 4，限 1 年，P/S/M/F 交易。"""
    sym = symbol.upper()
    now = time.time()
    if sym in _STOCK_CACHE and now - _STOCK_CACHE[sym]["ts"] < _STOCK_TTL:
        return _STOCK_CACHE[sym]["items"]

    cutoff = (date.today() - timedelta(days=365)).isoformat()

    try:
        company_obj = edgar.Company(sym)
        filing_list = list(company_obj.get_filings(form="4").head(limit * 3))
    except Exception as e:
        print(f"[insider] stock listing error {sym}: {e}")
        return []

    all_txns: list[dict] = []
    for f in filing_list:
        fd = str(getattr(f, "filing_date", "") or "")[:10]
        if fd and fd < cutoff:
            break
        acc = f.accession_no
        txns = _filing_to_txns(f, fd, acc)
        all_txns.extend(t for t in txns if t["symbol"] == sym)
        if len(all_txns) >= limit:
            break

    all_txns.sort(key=lambda x: x.get("transaction_date", ""), reverse=True)
    result = all_txns[:limit]
    _STOCK_CACHE[sym] = {"ts": now, "items": result}
    return result
