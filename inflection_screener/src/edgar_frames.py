"""EDGAR Frames API 抓取 + 限速 + 本地快取（spec §2.1 / §2.2）。

⚠ 合規（不可妥協）：
- User-Agent 由環境變數 EDGAR_UA 注入，缺失直接 raise。
- 每個 request 間隔 ≥ EDGAR_SLEEP_SEC（限速 ≤ 8 req/sec）。
- 回應落地檔案快取，同一 (concept, frame) 24 小時內不重打。

已知限制（v1，已與使用者確認）：Frames API 回應不含 `filed`（申報日），
僅有 accn。filing_date 欄位保留為 NULL，另存 accn 供未來反查補齊。
"""
import datetime as dt
import json
import os
import time

import pandas as pd
import requests

from inflection_screener import config

_session = requests.Session()
_last_call = 0.0


def _headers() -> dict:
    ua = os.getenv(config.EDGAR_UA_ENV)
    if not ua:
        raise RuntimeError(
            f"環境變數 {config.EDGAR_UA_ENV} 未設定（格式：'BamHI Research you@email'），"
            "EDGAR 會回 403。"
        )
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def _throttled_get(url: str) -> requests.Response:
    global _last_call
    wait = config.EDGAR_SLEEP_SEC - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()
    return _session.get(url, headers=_headers(), timeout=30)


def _cache_path(key: str) -> str:
    return os.path.join(config.EDGAR_CACHE_DIR, f"{key}.json")


def _cache_fresh(path: str) -> bool:
    if not os.path.exists(path):
        return False
    age_h = (time.time() - os.path.getmtime(path)) / 3600
    return age_h < config.EDGAR_CACHE_TTL_HOURS


def _get_json_cached(url: str, cache_key: str):
    """GET + 24h 檔案快取。404 以 {'__404__': True} 快取，避免重打。"""
    path = _cache_path(cache_key)
    if _cache_fresh(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return None if data.get("__404__") else data

    resp = _throttled_get(url)
    if resp.status_code == 404:
        data = {"__404__": True}
    else:
        resp.raise_for_status()
        data = resp.json()

    os.makedirs(config.EDGAR_CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return None if data.get("__404__") else data


# ── 日曆季工具 ──

def _prev_quarter(year: int, q: int) -> tuple[int, int]:
    return (year - 1, 4) if q == 1 else (year, q - 1)


def _current_completed_quarter(today: dt.date | None = None) -> tuple[int, int]:
    """最近一個「已結束」的日曆季。"""
    today = today or dt.date.today()
    q = (today.month - 1) // 3 + 1
    return _prev_quarter(today.year, q)


def fetch_frame(concept: str, unit: str, frame: str) -> pd.DataFrame | None:
    """單一 frame → DataFrame(cik, entity, concept, start, end, val, accn, frame)。404 → None。"""
    url = config.EDGAR_FRAMES_URL.format(concept=concept, unit=unit, frame=frame)
    data = _get_json_cached(url, f"{concept}_{unit}_{frame}")
    if data is None or not data.get("data"):
        return None
    df = pd.DataFrame(data["data"])
    df = df.rename(columns={"entityName": "entity"})
    keep = [c for c in ("cik", "entity", "start", "end", "val", "accn") if c in df.columns]
    df = df[keep].copy()
    df["concept"] = concept
    df["frame"] = frame
    return df


def resolve_latest_quarter(today: dt.date | None = None) -> tuple[int, int]:
    """當季尚未普遍申報（frame 缺 / 列數過少）則自動回退一季（spec §2.1）。"""
    year, q = _current_completed_quarter(today)
    for _ in range(3):
        df = fetch_frame(config.REVENUE_CONCEPTS[0], config.USD_UNIT, f"CY{year}Q{q}")
        if df is not None and len(df) >= config.EDGAR_MIN_FRAME_ROWS:
            return year, q
        print(f"[edgar] CY{year}Q{q} 申報未普遍（{0 if df is None else len(df)} 列），回退一季", flush=True)
        year, q = _prev_quarter(year, q)
    return year, q


def quarter_window(n: int = config.N_QUARTERS, today: dt.date | None = None) -> list[tuple[int, int]]:
    """最近 n 個日曆季（新 → 舊）。"""
    year, q = resolve_latest_quarter(today)
    out = []
    for _ in range(n):
        out.append((year, q))
        year, q = _prev_quarter(year, q)
    return out


def fetch_all_frames(today: dt.date | None = None) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple[int, int]]]:
    """抓取全部所需 frames。

    Returns:
        quarterly: 全部季 frame facts（含窗口外、供 Q4 推導的同年 Q1–Q3）
        annual:    FY 年度 frame facts（Q4 推導用，Revenues + NetIncomeLoss）
        window:    8 季窗口（新 → 舊）
    """
    window = quarter_window(today=today)

    # Q4 推導需要：窗口內含 Q4 的年份，其 Q1–Q3 + 年度 FY 值
    need_quarters: set[tuple[int, int]] = set(window)
    q4_years = {y for (y, q) in window if q == 4}
    for y in q4_years:
        need_quarters.update({(y, 1), (y, 2), (y, 3)})

    concepts = config.REVENUE_CONCEPTS + [config.NET_INCOME_CONCEPT]
    q_frames: list[pd.DataFrame] = []
    for year, q in sorted(need_quarters, reverse=True):
        frame = f"CY{year}Q{q}"
        for concept in concepts:
            df = fetch_frame(concept, config.USD_UNIT, frame)
            if df is not None:
                q_frames.append(df)
        df = fetch_frame(config.EPS_CONCEPT, config.EPS_UNIT, frame)
        if df is not None:
            q_frames.append(df)

    a_frames: list[pd.DataFrame] = []
    for y in sorted(q4_years, reverse=True):
        for concept in concepts:
            df = fetch_frame(concept, config.USD_UNIT, f"CY{y}")
            if df is not None:
                a_frames.append(df)

    quarterly = pd.concat(q_frames, ignore_index=True) if q_frames else pd.DataFrame()
    annual = pd.concat(a_frames, ignore_index=True) if a_frames else pd.DataFrame()
    print(f"[edgar] quarterly facts={len(quarterly)}, annual facts={len(annual)}, window={window[0]}..{window[-1]}", flush=True)
    return quarterly, annual, window


def fetch_ticker_map() -> pd.DataFrame:
    """SEC 官方 CIK → ticker 映射（spec §2.3）。同 CIK 多 ticker 取序位最前（主要上市別）。"""
    data = _get_json_cached(config.EDGAR_TICKER_MAP_URL, "company_tickers")
    if data is None:
        raise RuntimeError("company_tickers.json 抓取失敗")
    rows = [
        {"cik": v["cik_str"], "ticker": v["ticker"], "name": v["title"], "_ord": int(k)}
        for k, v in data.items()
    ]
    df = pd.DataFrame(rows).sort_values("_ord").drop_duplicates("cik", keep="first")
    return df[["cik", "ticker", "name"]].reset_index(drop=True)
