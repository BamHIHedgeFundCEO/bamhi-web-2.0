"""
edgar_fetch.py — EDGAR 申報增量抓取（§6.1）

功能：
  - ticker → CIK 對映：SEC company_tickers.json（下載一次 cache 到 data/dual_pool/）
  - 增量拉 watchpool（active）ticker 的 8-K（含附件 PR 文字）與 Form 4
  - 初次回補近 90 日；之後每日只拉前一日新申報
  - 已處理 accession 記錄冪等判斷（重跑不重複處理）
  - Header User-Agent 從 env EDGAR_USER_AGENT 讀
  - 限速：≤ 1 req/s（§6.1）

注意：不存公告全文（§6.8 版權）；text 欄位只在記憶體中傳遞給 LLM，不落庫
"""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

import requests

# ── 環境設定 ─────────────────────────────────────────────────────────
_USER_AGENT = os.getenv(
    "EDGAR_USER_AGENT",
    "BamHI research frank940702@gmail.com",
)
_DATA_DIR = Path(os.getenv("DUAL_POOL_DATA_DIR", "data/dual_pool"))
_CIK_CACHE_FILE      = _DATA_DIR / "cik_cache.json"
_PROCESSED_FILE      = _DATA_DIR / "processed_accessions.json"
_BACKFILL_DAYS       = 90   # 初次回補天數
_INCREMENTAL_DAYS    = 2    # 每日增量天數
_TEXT_MAX_CHARS      = 4000 # LLM 輸入上限（不落庫，§6.8）
_RATE_INTERVAL       = 1.0  # ≥1 req/s（§6.1 SEC 限速規定）

# SEC API 基礎 URL
_TICKERS_URL     = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_ARCHIVES_BASE   = "https://www.sec.gov/Archives/edgar/data"

# ── 限速狀態（module-level，跨呼叫共用）──────────────────────────────
_last_request_ts: float = 0.0


def _rate_limited_get(
    url: str,
    timeout: int = 30,
    retry_503: int = 0,
) -> Optional[requests.Response]:
    """
    帶限速的 GET 請求（§6.1：≤ 1 req/s）。
    retry_503 > 0 → 遇 503 指數退避重試（2s/4s/...）。
    失敗回 None（呼叫端自行處理）。
    """
    global _last_request_ts
    for attempt in range(retry_503 + 1):
        elapsed = time.time() - _last_request_ts
        if elapsed < _RATE_INTERVAL:
            time.sleep(_RATE_INTERVAL - elapsed)  # ← 限速 1 req/s，§6.1 規定（此行）
        _last_request_ts = time.time()
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            status = e.response.status_code
            if status == 503 and attempt < retry_503:
                wait = 2.0 * (2 ** attempt)  # 2s, 4s 指數退避
                print(f"[edgar] HTTP 503 → retry {attempt+1}/{retry_503} in {wait:.0f}s: {url}")
                time.sleep(wait)
                continue
            print(f"[edgar] HTTP {status} → {url}")
            return None
        except Exception as e:
            print(f"[edgar] GET error {url}: {e}")
            return None
    return None


# ── 抓取降級計數（run 結尾印出，供監控 EDGAR 品質）──────────────────
_fetch_degraded_count: int = 0


def get_fetch_degraded_count() -> int:
    """回傳本次 process 累計的抓取降級次數（如 EX-99 補取失敗降級主文）。"""
    return _fetch_degraded_count


def reset_fetch_degraded_count():
    global _fetch_degraded_count
    _fetch_degraded_count = 0


# ── CIK 對映（§6.1：ticker → CIK，cache 到本地）────────────────────

def _download_cik_map() -> dict[str, str]:
    """
    下載 SEC company_tickers.json，回傳 {TICKER_UPPER: cik_str(10位數補零)} 對映。
    """
    resp = _rate_limited_get(_TICKERS_URL)
    if not resp:
        return {}
    try:
        data = resp.json()
        result = {}
        for entry in data.values():
            tk = entry.get("ticker", "").upper()
            cik_raw = str(entry.get("cik_str", ""))
            if tk and cik_raw:
                result[tk] = cik_raw.zfill(10)
        print(f"[edgar] CIK map 下載完成：{len(result)} 筆")
        return result
    except Exception as e:
        print(f"[edgar] CIK map 解析失敗：{e}")
        return {}


def _load_cik_map(tickers: list[str]) -> dict[str, str]:
    """
    載入 CIK 對映（優先本地 cache，缺失才重新下載）。
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache: dict[str, str] = {}
    if _CIK_CACHE_FILE.exists():
        try:
            cache = json.loads(_CIK_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    needed = [t.upper() for t in tickers if t.upper() not in cache]
    if needed:
        print(f"[edgar] CIK 缺少 {len(needed)} 筆，重新下載 company_tickers.json")
        fresh = _download_cik_map()
        if fresh:
            cache.update(fresh)
            _CIK_CACHE_FILE.write_text(
                json.dumps(cache, ensure_ascii=False),
                encoding="utf-8",
            )

    return cache


# ── Processed accessions（冪等判斷）──────────────────────────────────

def load_processed_accessions() -> set[str]:
    """載入已處理的 accession number 集合（冪等用）。"""
    if _PROCESSED_FILE.exists():
        try:
            return set(json.loads(_PROCESSED_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def save_processed_accessions(accessions: set[str]):
    """持久化已處理 accession 集合。"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _PROCESSED_FILE.write_text(
        json.dumps(sorted(accessions), ensure_ascii=False),
        encoding="utf-8",
    )


# ── 申報文件取得 ──────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """簡單去除 HTML 標籤，還原常見 HTML 實體。"""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _get_filing_text(
    cik_int: int,
    accession_nodash: str,
    primary_doc: str,
) -> str:
    """
    取主要申報文件文字（去 HTML，截斷至 _TEXT_MAX_CHARS）。
    不落庫（§6.8 版權）。
    """
    url = f"{_ARCHIVES_BASE}/{cik_int}/{accession_nodash}/{primary_doc}"
    resp = _rate_limited_get(url)
    if not resp:
        return ""
    raw = resp.text
    return _strip_html(raw)[:_TEXT_MAX_CHARS]


def _get_form4_xml(
    cik_int: int,
    accession_no: str,
    accession_nodash: str,
) -> str:
    """
    取 Form 4 完整 XML。
    EDGAR Form 4 的 primaryDocument 指向 HTML 瀏覽器，實際 XML 嵌在
    {acc}.txt 完整申報文件中（SGML wrapper 內含 <ownershipDocument> XML）。
    """
    txt_url = f"{_ARCHIVES_BASE}/{cik_int}/{accession_nodash}/{accession_no}.txt"
    resp = _rate_limited_get(txt_url)
    if not resp:
        return ""
    raw = resp.text
    # 從 SGML 容器中萃取 XML 段落
    start = raw.find("<ownershipDocument>")
    end   = raw.find("</ownershipDocument>")
    if start >= 0 and end > start:
        return raw[start: end + len("</ownershipDocument>")]
    return ""


def _get_exhibit_99_url(
    cik_int: int,
    accession_nodash: str,
) -> Optional[str]:
    """
    從申報 index 頁找 EX-99.1 附件 URL（8-K 附件 PR，§6.1）。
    503 時指數退避重試 2 次（2s/4s），仍失敗 → 回 None（呼叫端降級主文）。
    """
    global _fetch_degraded_count
    index_url = (
        f"{_ARCHIVES_BASE}/{cik_int}/{accession_nodash}"
        f"/{accession_nodash}-index.htm"
    )
    resp = _rate_limited_get(index_url, retry_503=2)
    if not resp:
        _fetch_degraded_count += 1  # 補取失敗 → 降級主文（run 結尾統計）
        return None
    # 正則找 EX-99.1 連結
    matches = re.findall(
        r'href="([^"]+)"[^>]*>[^<]*</a>\s*</td>\s*<td[^>]*>EX-99',
        resp.text,
        re.IGNORECASE,
    )
    if not matches:
        # 備援格式：href 在 EX-99 之後
        matches = re.findall(
            r'EX-99[^<]*</td>\s*<td[^>]*>\s*<a href="(/Archives/[^"]+)"',
            resp.text,
            re.IGNORECASE,
        )
    if matches:
        href = matches[0]
        if href.startswith("/"):
            return f"https://www.sec.gov{href}"
        return href
    return None


# ── 8-K Item 解析 ─────────────────────────────────────────────────────

_ITEM_RE = re.compile(r"Item\s+(\d+\.\d+)", re.IGNORECASE)


def _parse_8k_items(text: str) -> list[str]:
    """從 8-K 文字解析 Item 編號（§6.1 先驗映射）。"""
    return list(dict.fromkeys(_ITEM_RE.findall(text)))  # 保序去重


# ── Form 4 XML 解析 ───────────────────────────────────────────────────

def _xml_text(element: ET.Element, path: str) -> str:
    """安全取 XML 子元素文字。"""
    el = element.find(path)
    return el.text.strip() if el is not None and el.text else ""


def _parse_form4_xml(xml_text: str) -> list[dict]:
    """
    解析 Form 4 XML，抽取非衍生品買賣交易（code P/S）。
    不走 LLM——規則直接產 insider_buy/insider_sell 事件（§6.1、§L2 Form4 處理）。
    """
    transactions: list[dict] = []
    # 嘗試移除 XML 宣告前的垃圾內容（有些 EDGAR 文件包 HTML wrapper）
    xml_start = xml_text.find("<?xml")
    if xml_start < 0:
        xml_start = xml_text.find("<ownershipDocument")
    if xml_start > 0:
        xml_text = xml_text[xml_start:]
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"[edgar] Form 4 XML 解析失敗：{e}")
        return transactions

    owner_name = _xml_text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName")
    owner_title = _xml_text(root, ".//reportingOwner/reportingOwnerRelationship/officerTitle")
    period_str = _xml_text(root, ".//periodOfReport")

    for txn in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
        code = _xml_text(txn, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        shares_str = _xml_text(txn, "transactionAmounts/transactionShares/value")
        price_str  = _xml_text(txn, "transactionAmounts/transactionPricePerShare/value")
        date_str   = _xml_text(txn, "transactionDate/value") or period_str
        try:
            shares = float(shares_str) if shares_str else 0.0
            price  = float(price_str)  if price_str  else 0.0
            magnitude_usd = round(shares * price, 2) if shares and price else None
        except ValueError:
            magnitude_usd = None

        transactions.append({
            "code":          code,
            "shares":        shares_str,
            "price":         price_str,
            "magnitude_usd": magnitude_usd,
            "date":          date_str,
            "owner_name":    owner_name,
            "owner_title":   owner_title,
        })

    return transactions


# ── 主要函式 ─────────────────────────────────────────────────────────

def _parse_recent_filings(
    recent: dict,
    ticker: str,
    cik: str,
    cutoff_date: date,
    processed_accessions: set[str],
) -> list[dict]:
    """
    解析 EDGAR submissions.recent，回傳未處理且在 cutoff_date 後的申報記錄。
    每筆記錄含 metadata + 原始文字（僅記憶體，不落庫）。
    """
    global _fetch_degraded_count
    filings_out: list[dict] = []
    cik_int = int(cik)

    acc_nos      = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    forms        = recent.get("form", [])
    primary_docs = recent.get("primaryDocument", [])

    for i, acc in enumerate(acc_nos):
        form = forms[i] if i < len(forms) else ""
        # 只處理 8-K 與 Form 4
        if form not in ("8-K", "4"):
            continue

        fd_str = filing_dates[i] if i < len(filing_dates) else ""
        try:
            filing_dt = date.fromisoformat(fd_str)
        except ValueError:
            continue
        if filing_dt < cutoff_date:
            continue  # 日期範圍外

        # accession_no 格式：帶破折號（XXXXXXXXXX-YY-ZZZZZZ）
        acc_dashed = acc  # submissions JSON 已含破折號格式
        if acc_dashed in processed_accessions:
            continue  # 已處理，冪等跳過

        primary_doc = primary_docs[i] if i < len(primary_docs) else ""
        acc_nodash  = acc.replace("-", "")
        source_url  = (
            f"{_ARCHIVES_BASE}/{cik_int}/{acc_nodash}/{primary_doc}"
            if primary_doc else f"{_ARCHIVES_BASE}/{cik_int}/{acc_nodash}/"
        )

        record: dict = {
            "ticker":       ticker,
            "cik":          cik,
            "accession_no": acc_dashed,
            "filing_date":  fd_str,
            "form_type":    form,
            "source_url":   source_url,
            "items":        [],
            "text":         "",
            "transactions": [],
        }

        if form == "8-K":
            # 取主文字（含 Item 解析）
            text = _get_filing_text(cik_int, acc_nodash, primary_doc) if primary_doc else ""
            record["items"] = _parse_8k_items(text)
            # 嘗試補取 EX-99.1 附件 PR（§6.1 含附件 PR 文字）
            ex_url = _get_exhibit_99_url(cik_int, acc_nodash)
            if ex_url:
                ex_resp = _rate_limited_get(ex_url, retry_503=2)
                if ex_resp:
                    ex_text = _strip_html(ex_resp.text)[:_TEXT_MAX_CHARS]
                    # 合併：Item 解析用主文，LLM 用 PR（若有）
                    record["text"] = ex_text if ex_text else text
                else:
                    _fetch_degraded_count += 1  # PR 抓取失敗 → 降級主文
                    record["text"] = text
            else:
                record["text"] = text

        elif form == "4":
            # Form 4: 從 {acc}.txt 完整申報取 ownershipDocument XML
            # primaryDocument 指向 HTML 瀏覽器，不含原始 XML（見 _get_form4_xml）
            xml_text = _get_form4_xml(cik_int, acc_dashed, acc_nodash)
            record["transactions"] = _parse_form4_xml(xml_text)

        filings_out.append(record)

    return filings_out


def fetch_watchpool_filings(
    tickers: list[str],
    processed_accessions: set[str],
    backfill_days: Optional[int] = None,
) -> list[dict]:
    """
    拉 watchpool ticker 的新申報（8-K + Form 4）。

    backfill_days: None → 自動偵測（processed_accessions 為空 → 90 日；
                          否則 → 2 日增量）。
    回傳 list[dict]，每筆代表一份未處理申報；text 欄位僅記憶體，不得落庫（§6.8）。
    """
    if backfill_days is None:
        backfill_days = _BACKFILL_DAYS if not processed_accessions else _INCREMENTAL_DAYS
    cutoff_date = (datetime.utcnow() - timedelta(days=backfill_days)).date()
    print(
        f"[edgar] 抓取模式={'backfill' if backfill_days >= 30 else 'incremental'} "
        f"cutoff={cutoff_date}，ticker 數={len(tickers)}"
    )

    cik_map = _load_cik_map(tickers)
    all_filings: list[dict] = []

    for ticker in tickers:
        cik = cik_map.get(ticker.upper())
        if not cik:
            print(f"[edgar] {ticker}: CIK 未找到，跳過")
            continue

        sub_url = _SUBMISSIONS_URL.format(cik=int(cik))
        resp = _rate_limited_get(sub_url)
        if not resp:
            print(f"[edgar] {ticker}: submissions 抓取失敗")
            continue

        try:
            sub_data = resp.json()
        except Exception as e:
            print(f"[edgar] {ticker}: submissions JSON 解析失敗：{e}")
            continue

        recent = sub_data.get("filings", {}).get("recent", {})
        filings = _parse_recent_filings(
            recent, ticker, cik, cutoff_date, processed_accessions
        )
        print(f"[edgar] {ticker}: 新申報 {len(filings)} 份")
        all_filings.extend(filings)

    print(f"[edgar] 總計新申報 {len(all_filings)} 份")
    return all_filings
