"""
institution_13f.py — 13F 機構持倉季度 job（§6.9）

執行流程：
  1. 決定 reporting quarter（預設：上一個完整季度）
  2. 推算 ZIP 的 filing date 範圍 URL
  3. 下載 SEC 13F bulk ZIP（~80-200MB）
  4. 從 SUBMISSION.tsv 取該季申報（PERIODOFREPORT 篩選）→ accession + filer CIK
  5. 從 INFOTABLE.tsv 過濾對應 accession，取 CUSIP + filer CIK 對
  6. 對每個 CUSIP 批次呼叫 OpenFIGI（ID_CUSIP → ticker）建立對映快取
  7. 對比 watchpool（active）ticker，計算 new_holders/total_holders
  8. Upsert institution_quarterly；儲存本季 holders 快取供下季 new_holders 計算

已知限制（§6.9 規定必記）：
  ・45 天申報延遲對右池「快進快出」是時效錯配——institution 因子反映 1.5–4.5 個月前持倉。
    右池權重 0.20 餵舊資料，回測歸因（§9）需單獨檢視此因子對右池是否有效。
    無效時應把右池 institution 權重移給 narrative/catalyst。
  ・OpenFIGI 無 API key 限速 25 req/min（每批 100 CUSIP）。
    大量不在 cache 的 CUSIP 時可能需 5-30 分鐘。
  ・INFOTABLE 的 FIGI 欄位只有約 8.8% 填入（2025-Q1 實測），主靠 CUSIP→ticker 對映。

URL 格式（2025 年起實測確認，Actions IP 被封鎖，必須在 Render 上執行）：
  https://www.sec.gov/files/structureddata/data/form-13f-data-sets/
    {01}{start_mon}{start_yr}-{end_day}{end_mon}{end_yr}_form13f.zip

  Q1（Jan-Mar period）→ 01mar{Y}-31may{Y}_form13f.zip
  Q2（Apr-Jun period）→ 01jun{Y}-31aug{Y}_form13f.zip
  Q3（Jul-Sep period）→ 01sep{Y}-30nov{Y}_form13f.zip
  Q4（Oct-Dec period）→ 01dec{Y}-{28or29}feb{Y+1}_form13f.zip

  實測 URL（200 OK confirmed 2026-07-06）：
    01mar2025-31may2025_form13f.zip  ← Q1 2025 period data
    01jun2025-31aug2025_form13f.zip  ← Q2 2025 period data
    01dec2024-28feb2025_form13f.zip  ← Q4 2024 period data
    01mar2026-31may2026_form13f.zip  ← Q1 2026 period data

  注意：ZIP 命名是 FILING DATE 範圍（非 PERIODOFREPORT）。
        同一 ZIP 內可能含跨季的 amendment（13F-HR/A），
        務必以 PERIODOFREPORT 欄位篩選目標季度。

環境變數：
  EDGAR_USER_AGENT          — SEC User-Agent（必填，§6.1）
  DUAL_POOL_DATA_DIR        — 本地資料根目錄（預設 data/dual_pool）
  SUPABASE_URL / SUPABASE_SERVICE_KEY — Supabase 憑證
  OPENFIGI_API_KEY          — OpenFIGI API key（選填；無 key 限速 25 req/min）
  INSTITUTION_TARGET_QUARTER — 手動指定季度，如 '2025-Q1'（否則自動推算）
"""

from __future__ import annotations

import calendar
import csv
import io
import json
import os
import tempfile
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

from data_pipeline.dual_pool import storage

# ── 環境設定 ──────────────────────────────────────────────────────────
_USER_AGENT = os.getenv(
    "EDGAR_USER_AGENT",
    "BamHI research frank940702@gmail.com",
)
_DATA_DIR   = Path(os.getenv("DUAL_POOL_DATA_DIR", "data/dual_pool"))
_OPENFIGI_KEY = os.getenv("OPENFIGI_API_KEY", "")

# OpenFIGI API（官方限制：無 key 每 request 10 jobs、25 req/min；
#               有 key 每 request 100 jobs、25 req/6s）
# batch/sleep 依 OPENFIGI_API_KEY 有無自動切換——無 key 硬送 100 jobs 會 HTTP 400。
_OPENFIGI_URL   = "https://api.openfigi.com/v3/mapping"
_OPENFIGI_BATCH = 100 if _OPENFIGI_KEY else 10
_OPENFIGI_SLEEP = 0.3 if _OPENFIGI_KEY else 2.5
# 連續失敗上限：超過 → raise，abort 整個 job 標 failed（不准靜默 None 到底）
_OPENFIGI_MAX_CONSECUTIVE_FAILURES = 5


class OpenFigiError(RuntimeError):
    """OpenFIGI 連續失敗超限 — 呼叫端讓 job 標 failed。"""


# 13F bulk URL base
_SEC_13F_BASE = (
    "https://www.sec.gov/files/structureddata/data/form-13f-data-sets"
)

# 本地 CUSIP→ticker 快取（Supabase cusip_map 表為主，本地 JSON 為 fallback；
# Render 暫態 FS 每次部署歸零，故持久化走 storage.py 雙路徑）
_CUSIP_CACHE_FILE = _DATA_DIR / "cusip_ticker_cache.json"


# ──────────────────────────────────────────────────────────────────────
# 季度工具
# ──────────────────────────────────────────────────────────────────────

def _current_quarter() -> tuple[int, int]:
    """回傳「上一個完整季度」(year, quarter_int)。"""
    today = date.today()
    # 上一季
    month = today.month
    year  = today.year
    q = (month - 1) // 3 + 1  # 當前季
    q -= 1
    if q == 0:
        q = 4
        year -= 1
    return year, q


def _quarter_name(year: int, q: int) -> str:
    """回傳如 '2025-Q1'"""
    return f"{year}-Q{q}"


def _prev_quarter(year: int, q: int) -> tuple[int, int]:
    """回傳前一個季度的 (year, q)。"""
    q -= 1
    if q == 0:
        q = 4
        year -= 1
    return year, q


def _period_of_report_str(year: int, q: int) -> str:
    """
    Quarter-end date in 'DD-MON-YYYY' format as used by SEC SUBMISSION.tsv PERIODOFREPORT.
    Q1→31-MAR, Q2→30-JUN, Q3→30-SEP, Q4→31-DEC
    """
    quarter_ends = {1: "31-MAR", 2: "30-JUN", 3: "30-SEP", 4: "31-DEC"}
    return f"{quarter_ends[q]}-{year}"


def _get_zip_url(year: int, q: int) -> str:
    """
    推算季度 bulk ZIP 的 URL。

    Filing date range（13F 截止日 = 季末+45天）：
      Q1 (Jan-Mar) → 01mar-31may
      Q2 (Apr-Jun) → 01jun-31aug
      Q3 (Jul-Sep) → 01sep-30nov
      Q4 (Oct-Dec) → 01dec-{feb_last}（次年）

    URL 格式確認：每個模式都以 curl HEAD 測試通過（2026-07-06）。
    """
    MONTH_NAMES = {
        1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
        7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
    }

    if q == 1:
        start = f"01mar{year}"
        end   = f"31may{year}"
    elif q == 2:
        start = f"01jun{year}"
        end   = f"31aug{year}"
    elif q == 3:
        start = f"01sep{year}"
        end   = f"30nov{year}"
    else:  # q == 4
        next_year = year + 1
        # 閏年判斷（next_year 的 2 月）
        feb_last = 29 if calendar.isleap(next_year) else 28
        start = f"01dec{year}"
        end   = f"{feb_last:02d}feb{next_year}"

    return f"{_SEC_13F_BASE}/{start}-{end}_form13f.zip"


def _parse_periodofreport(s: str) -> tuple[int, int]:
    """
    解析 SUBMISSION.tsv 的 PERIODOFREPORT（格式 DD-MON-YYYY）→ (year, quarter)。
    31-MAR-2025 → (2025, 1)
    """
    MONTH_MAP = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }
    parts = s.strip().upper().split("-")
    if len(parts) != 3:
        return 0, 0
    try:
        month = MONTH_MAP.get(parts[1], 0)
        year  = int(parts[2])
        q     = (month - 1) // 3 + 1
        return year, q
    except Exception:
        return 0, 0


# ──────────────────────────────────────────────────────────────────────
# OpenFIGI CUSIP → ticker 對映
# ──────────────────────────────────────────────────────────────────────

def _load_cusip_cache() -> dict[str, Optional[str]]:
    """
    載入 CUSIP→ticker 快取。
    優先 Supabase cusip_map 表（跨部署持久，B2）；失敗/無憑證 → 本地 JSON。
    """
    cache = storage.load_cusip_map()
    if cache:
        return cache
    if _CUSIP_CACHE_FILE.exists():
        try:
            return json.loads(_CUSIP_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cusip_cache(cache: dict, fresh: Optional[dict] = None):
    """
    儲存 CUSIP→ticker 快取。
    Supabase 只 upsert 新查到的（fresh）；本地 JSON 存全量做離線 fallback。
    """
    if fresh:
        storage.upsert_cusip_map(fresh)
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _CUSIP_CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        print(f"[13f] CUSIP cache save error: {e}")


def _extract_ticker(entry: dict) -> Optional[str]:
    """從 OpenFIGI mapping entry 取第一個普通股 ticker。"""
    for item in entry.get("data", []):
        if item.get("securityType") in ("Common Stock", "ETP"):
            return item.get("ticker")
    return None


def _openfigi_batch(cusips: list[str]) -> dict[str, Optional[str]]:
    """
    批次呼叫 OpenFIGI，回傳 {cusip: ticker_or_None}。

    批量/限速依 key 有無切換（見 _OPENFIGI_BATCH/_OPENFIGI_SLEEP 註解）。
    HTTP 400/429/例外大聲印錯 + 計連續失敗；連續 ≥5 次 → raise OpenFigiError
    （abort 整個 job，由 admin endpoint 標 failed，不准靜默 None 到底）。
    """
    result: dict[str, Optional[str]] = {}
    headers = {"Content-Type": "application/json"}
    if _OPENFIGI_KEY:
        headers["X-OPENFIGI-APIKEY"] = _OPENFIGI_KEY

    consecutive_failures = 0
    total_batches = (len(cusips) + _OPENFIGI_BATCH - 1) // _OPENFIGI_BATCH
    print(
        f"[13f] OpenFIGI 模式={'keyed' if _OPENFIGI_KEY else 'no-key'} "
        f"batch={_OPENFIGI_BATCH} sleep={_OPENFIGI_SLEEP}s "
        f"（{len(cusips)} CUSIP / {total_batches} 批）"
    )

    for i in range(0, len(cusips), _OPENFIGI_BATCH):
        batch = cusips[i: i + _OPENFIGI_BATCH]
        body  = [{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in batch]
        batch_ok = False
        try:
            resp = requests.post(
                _OPENFIGI_URL, headers=headers, json=body, timeout=30
            )
            if resp.status_code == 200:
                for j, entry in enumerate(resp.json()):
                    result[batch[j]] = _extract_ticker(entry)
                batch_ok = True
            elif resp.status_code == 429:
                print(f"[13f] ⚠ OpenFIGI HTTP 429 rate limit（批 {i//_OPENFIGI_BATCH+1}/{total_batches}）→ sleep 60s 後重試")
                time.sleep(60)
                resp2 = requests.post(
                    _OPENFIGI_URL, headers=headers, json=body, timeout=30
                )
                if resp2.status_code == 200:
                    for j, entry in enumerate(resp2.json()):
                        result[batch[j]] = _extract_ticker(entry)
                    batch_ok = True
                else:
                    print(f"[13f] ⚠ OpenFIGI 重試仍失敗 HTTP {resp2.status_code}: {resp2.text[:200]}")
            else:
                # 400 = jobs 超限/格式錯（大聲印，不靜默）
                print(
                    f"[13f] ⚠ OpenFIGI HTTP {resp.status_code}"
                    f"（批 {i//_OPENFIGI_BATCH+1}/{total_batches}）: {resp.text[:200]}"
                )
        except Exception as e:
            print(f"[13f] ⚠ OpenFIGI 批次例外: {e}")

        if batch_ok:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            for c in batch:
                result.setdefault(c, None)
            if consecutive_failures >= _OPENFIGI_MAX_CONSECUTIVE_FAILURES:
                raise OpenFigiError(
                    f"OpenFIGI 連續失敗 {consecutive_failures} 次"
                    f"（最後批 {i//_OPENFIGI_BATCH+1}/{total_batches}）— abort 13F job"
                )

        time.sleep(_OPENFIGI_SLEEP)

    return result


def _resolve_cusips_to_tickers(
    cusips: list[str],
    cache: dict[str, Optional[str]],
) -> dict[str, Optional[str]]:
    """
    解析 CUSIP 列表 → ticker。
    先讀快取（Supabase cusip_map 為主），只對 miss 查 OpenFIGI，查完 upsert 回表。
    """
    missing = [c for c in cusips if c not in cache]
    if missing:
        print(f"[13f] OpenFIGI 查詢 {len(missing)} 個 CUSIP（快取 miss）")
        fresh = _openfigi_batch(missing)
        cache.update(fresh)
        _save_cusip_cache(cache, fresh=fresh)
    return {c: cache.get(c) for c in cusips}


# ──────────────────────────────────────────────────────────────────────
# 13F ZIP 下載與解析
# ──────────────────────────────────────────────────────────────────────

def _download_13f_zip(url: str) -> Optional[str]:
    """
    下載 13F bulk ZIP 到暫存檔，回傳檔案路徑或 None（失敗）。

    串流寫入磁碟而非全載入 RAM：Render free tier 僅 512MB，ZIP 80-200MB
    全放記憶體（再包 io.BytesIO）會 OOM，process 被殺 + 重啟 → 背景任務狀態歸零
    （status 卡在 never_run）。zipfile 直接讀磁碟檔支援串流解壓，峰值 RAM <100MB。
    呼叫端負責用完刪除暫存檔（os.remove）。
    """
    print(f"[13f] 下載 {url}")
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=300,  # 最大 5 分鐘（ZIP 可能 80-200MB）
            stream=True,
        )
        if resp.status_code != 200:
            print(f"[13f] 下載失敗 HTTP {resp.status_code}: {url}")
            return None
        fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="form13f_")
        total = 0
        with os.fdopen(fd, "wb") as out:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                out.write(chunk)
                total += len(chunk)
        print(f"[13f] 下載完成 {total / 1_000_000:.1f} MB → {tmp_path}")
        return tmp_path
    except Exception as e:
        print(f"[13f] 下載例外: {e}")
        return None


def _parse_submission_tsv(z: zipfile.ZipFile, target_period: str) -> dict[str, str]:
    """
    解析 SUBMISSION.tsv，篩選 PERIODOFREPORT == target_period。
    回傳 {ACCESSION_NUMBER: CIK}（每個 CIK 保留最新 FILING_DATE 的申報，處理 amendment）。
    """
    accession_to_cik: dict[str, str] = {}       # 最終結果
    cik_latest: dict[str, tuple[str, str]] = {}  # {cik: (latest_filing_date, accession)}

    try:
        with z.open("SUBMISSION.tsv") as f:
            reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                delimiter="\t",
            )
            for row in reader:
                period = row.get("PERIODOFREPORT", "").strip()
                if period != target_period:
                    continue
                acc = row.get("ACCESSION_NUMBER", "").strip()
                cik = row.get("CIK", "").strip()
                fd  = row.get("FILING_DATE", "").strip()
                if not acc or not cik:
                    continue
                # 同一 CIK 取最新 FILING_DATE（處理 13F-HR/A amendment）
                prev = cik_latest.get(cik)
                if prev is None or fd > prev[0]:
                    cik_latest[cik] = (fd, acc)

        for cik, (_, acc) in cik_latest.items():
            accession_to_cik[acc] = cik

    except Exception as e:
        print(f"[13f] SUBMISSION.tsv 解析錯誤: {e}")

    print(f"[13f] SUBMISSION: {len(accession_to_cik)} 個申報（PERIODOFREPORT={target_period}）")
    return accession_to_cik


def _parse_infotable_tsv(
    z: zipfile.ZipFile,
    target_accessions: set[str],
) -> dict[str, set[str]]:
    """
    解析 INFOTABLE.tsv，只取 target_accessions 內的申報。
    回傳 {cusip: {cik1, cik2, ...}}（持有該 CUSIP 的機構 CIK 集合）。
    accession_to_cik 用來從 ACCESSION_NUMBER 取回 CIK。
    """
    # 需要能從 accession 查到 cik
    # 此函式僅接受 target_accessions 集合，CIK 由呼叫端傳入
    # → 改為直接由外層呼叫處理，此函式回傳 {cusip: {accession_number}} 中間結果
    # 外層再 join accession_to_cik
    cusip_to_accessions: dict[str, set[str]] = {}

    try:
        with z.open("INFOTABLE.tsv") as f:
            reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                delimiter="\t",
            )
            for row in reader:
                acc = row.get("ACCESSION_NUMBER", "").strip()
                if acc not in target_accessions:
                    continue
                cusip = row.get("CUSIP", "").strip()
                if not cusip or len(cusip) < 8:  # 過濾空值與格式異常
                    continue
                cusip_to_accessions.setdefault(cusip, set()).add(acc)
    except Exception as e:
        print(f"[13f] INFOTABLE.tsv 解析錯誤: {e}")

    print(f"[13f] INFOTABLE: {len(cusip_to_accessions)} 個 unique CUSIP")
    return cusip_to_accessions


# ──────────────────────────────────────────────────────────────────────
# 主 job 函式
# ──────────────────────────────────────────────────────────────────────

def run_institution_job(
    target_quarter: Optional[str] = None,
    download_prev_for_new_holders: bool = True,
) -> dict:
    """
    13F 機構持倉季度 job 主入口。

    target_quarter: 如 '2025-Q1'；None → 自動推算上一個完整季度。
    download_prev_for_new_holders: True → 同時處理前季資料以計算 new_holders；
                                   False → new_holders = total_holders（首次執行快速模式）。

    回傳 dict：tickers_processed, new_holders_total, total_holders_sum, quarter, elapsed_s
    """
    run_start = datetime.now(timezone.utc)
    print(f"[13f] === 開始 {run_start.isoformat(timespec='seconds')} ===")

    # 1. 決定目標季度
    if target_quarter:
        year, q = int(target_quarter.split("-Q")[0]), int(target_quarter.split("-Q")[1])
    else:
        year, q = _current_quarter()

    quarter_name = _quarter_name(year, q)
    print(f"[13f] 目標季度: {quarter_name}")

    # 2. 讀 watchpool active ticker
    watchpool = storage.load_watchpool()
    active_tickers = {
        r["ticker"]
        for r in watchpool
        if r.get("status", "active") == "active"
    }
    if not active_tickers:
        print("[13f] watchpool 無 active ticker，退出")
        return {"quarter": quarter_name, "tickers_processed": 0, "error": "empty watchpool"}
    print(f"[13f] watchpool active: {len(active_tickers)} 個 ticker")

    # 3. 下載目標季 ZIP（串流寫磁碟，避免 200MB 進 RAM 撐爆 Render free tier）
    zip_url = _get_zip_url(year, q)
    zip_path = _download_13f_zip(zip_url)
    if not zip_path:
        return {"quarter": quarter_name, "error": f"download failed: {zip_url}"}

    # 4. 解析 SUBMISSION + INFOTABLE
    target_period_str = _period_of_report_str(year, q)  # e.g. "31-MAR-2025"
    data_gaps: list[str] = []

    try:
        with zipfile.ZipFile(zip_path) as z:
            accession_to_cik = _parse_submission_tsv(z, target_period_str)
            if not accession_to_cik:
                return {
                    "quarter": quarter_name,
                    "error": f"no filings for PERIODOFREPORT={target_period_str} in {zip_url}",
                }

            target_accessions = set(accession_to_cik.keys())
            cusip_to_accessions = _parse_infotable_tsv(z, target_accessions)
    except zipfile.BadZipFile as e:
        return {"quarter": quarter_name, "error": f"bad ZIP: {e}"}
    finally:
        # 解析完立即刪暫存檔（釋放磁碟；下季 ZIP 才有空間）
        try:
            os.remove(zip_path)
        except OSError:
            pass

    # 5. CUSIP → ticker 對映（OpenFIGI）
    all_cusips = list(cusip_to_accessions.keys())
    print(f"[13f] 共 {len(all_cusips)} 個 unique CUSIP，開始對映 ticker...")

    cusip_cache = _load_cusip_cache()
    cusip_to_ticker = _resolve_cusips_to_tickers(all_cusips, cusip_cache)

    # 6. 建立 ticker→filer CIK 集合（當季）
    ticker_to_filers: dict[str, set[str]] = {}
    for cusip, accessions in cusip_to_accessions.items():
        ticker = cusip_to_ticker.get(cusip)
        if not ticker or ticker not in active_tickers:
            continue
        ciks = {accession_to_cik[acc] for acc in accessions if acc in accession_to_cik}
        ticker_to_filers.setdefault(ticker, set()).update(ciks)

    print(f"[13f] watchpool 內找到 {len(ticker_to_filers)} 個 ticker 有持倉")

    # 7. 載入前季資料計算 new_holders
    prev_year, prev_q = _prev_quarter(year, q)
    prev_quarter_name = _quarter_name(prev_year, prev_q)
    prev_holders: dict[str, set] = {}

    if download_prev_for_new_holders:
        # 先嘗試從本地快取取前季 filer 集合
        prev_holders = storage.load_institution_holders_cache(prev_quarter_name)
        if not prev_holders:
            print(f"[13f] 前季 {prev_quarter_name} 快取不存在，嘗試下載前季 ZIP")
            prev_url      = _get_zip_url(prev_year, prev_q)
            prev_zip_path = _download_13f_zip(prev_url)
            if prev_zip_path:
                prev_target_period = _period_of_report_str(prev_year, prev_q)
                try:
                    with zipfile.ZipFile(prev_zip_path) as z_prev:
                        prev_acc_to_cik = _parse_submission_tsv(z_prev, prev_target_period)
                        prev_cusip_to_acc = _parse_infotable_tsv(z_prev, set(prev_acc_to_cik.keys()))
                except zipfile.BadZipFile:
                    prev_cusip_to_acc = {}
                    prev_acc_to_cik   = {}
                finally:
                    try:
                        os.remove(prev_zip_path)
                    except OSError:
                        pass

                # 對 active tickers 建前季 holders
                for cusip, accessions in prev_cusip_to_acc.items():
                    ticker = cusip_cache.get(cusip) or cusip_to_ticker.get(cusip)
                    if not ticker or ticker not in active_tickers:
                        continue
                    ciks = {prev_acc_to_cik[acc] for acc in accessions if acc in prev_acc_to_cik}
                    prev_holders.setdefault(ticker, set()).update(ciks)

                storage.save_institution_holders_cache(prev_quarter_name, prev_holders)
            else:
                print(f"[13f] 前季 ZIP 下載失敗，new_holders = total_holders（保守值）")

    # 8. 計算 new_holders / total_holders
    records: list[dict] = []
    known_at = run_start.isoformat(timespec="seconds")
    tickers_matched: list[str] = []

    for ticker in active_tickers:
        current_ciks = ticker_to_filers.get(ticker, set())
        if not current_ciks:
            # 無任何機構持倉，記 data_gap
            data_gaps.append(ticker)
            continue

        prev_ciks   = prev_holders.get(ticker, set())
        new_ciks    = current_ciks - prev_ciks
        new_holders = len(new_ciks)
        total_holders = len(current_ciks)

        records.append({
            "ticker":        ticker,
            "quarter":       quarter_name,
            "new_holders":   new_holders,
            "total_holders": total_holders,
            "known_at":      known_at,
        })
        tickers_matched.append(ticker)

    # 9. Upsert institution_quarterly
    if records:
        storage.upsert_institution_quarterly(records)
    print(f"[13f] upserted {len(records)} 筆 institution_quarterly")

    # 10. 儲存本季 holders 快取（供下季計算 new_holders 用）
    storage.save_institution_holders_cache(quarter_name, ticker_to_filers)

    # 11. 收尾
    if data_gaps:
        print(f"[13f] 無持倉資料（data_gap）ticker 數: {len(data_gaps)}")
        if len(data_gaps) <= 10:
            print(f"[13f] 無持倉: {data_gaps}")

    elapsed = (datetime.now(timezone.utc) - run_start).total_seconds()
    print(f"[13f] === 完成 elapsed={elapsed:.0f}s ===")

    return {
        "quarter":            quarter_name,
        "tickers_in_watchpool": len(active_tickers),
        "tickers_with_holdings": len(records),
        "tickers_no_holdings":   len(data_gaps),
        "new_holders_total":     sum(r["new_holders"] for r in records),
        "total_holders_sum":     sum(r["total_holders"] for r in records),
        "elapsed_s":             round(elapsed, 1),
    }


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_institution_job(target_quarter=target)
    print("\n[13f] 結果摘要:")
    for k, v in result.items():
        print(f"  {k}: {v}")
