"""
rule_engine.py -- 規則引擎 fallback（§6.7）

LLM 全掛時保底，確保管線永不斷線。
extraction_method = 'rule'

規則覆蓋（§6.7）：
  - Item 編號 -> event_type 映射
  - 正則抓金額：$[digits]+ ?(M|B|million|billion)
  - 正則抓季度日期：Q[1-4] 20xx
  - tier1 字典比對（§6.5 名單小寫）
  - specificity 封頂 3（規則無法判斷 binding/recurring）
  - is_dilution_flag：正則 offering|ATM|shelf|convertible|warrant

Form 4 也在此模組產生事件（買/賣直接映射，不需 LLM）。
"""

from __future__ import annotations

import re
from typing import Optional

# ── Item → event_type 映射（§6.1 先驗）──────────────────────────────
ITEM_EVENT_MAP: dict[str, str] = {
    "1.01": "new_contract",
    "1.02": "customer_loss",
    "1.03": "going_concern",
    "2.01": "mna_target",
    "2.02": "guidance",
    "2.03": "other",
    "2.04": "other_negative",
    "2.05": "other_negative",
    "2.06": "other_negative",
    "3.01": "other_negative",
    "3.02": "dilution_offering",
    "3.03": "other",
    "4.01": "auditor_change",
    "4.02": "restatement",
    "5.01": "strategic_investment",
    "5.02": "other",
    "7.01": "other",
    "8.01": "other",
}

# event_type → direction 映射
_DIRECTION_MAP: dict[str, str] = {
    "new_contract":         "bullish",
    "new_client":           "bullish",
    "new_product":          "bullish",
    "market_entry":         "bullish",
    "policy_beneficiary":   "bullish",
    "guidance_raise":       "bullish",
    "capacity_expansion":   "bullish",
    "strategic_investment": "bullish",
    "mna_target":           "bullish",
    "backlog_growth":       "bullish",
    "regulatory_approval":  "bullish",
    "insider_buy":          "bullish",
    "guidance":             "neutral",
    "commitment":           "neutral",
    "dilution_offering":    "bearish",
    "guidance_cut":         "bearish",
    "insider_sell":         "bearish",
    "restatement":          "bearish",
    "auditor_change":       "bearish",
    "going_concern":        "bearish",
    "litigation":           "bearish",
    "customer_loss":        "bearish",
    "other_negative":       "bearish",
    "other":                "neutral",
}

# 完整性旗標 event_type
_INTEGRITY_TYPES = frozenset({"restatement", "auditor_change", "going_concern"})

# ── 正則 ──────────────────────────────────────────────────────────────
_AMOUNT_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion|M\b|B\b)",
    re.IGNORECASE,
)
_QUARTER_RE  = re.compile(r"Q[1-4]\s+20\d\d", re.IGNORECASE)
_DILUTION_RE = re.compile(r"\b(offering|ATM|shelf|convertible|warrant)\b", re.IGNORECASE)

# ── tier1 字典（§6.5，小寫比對）─────────────────────────────────────
TIER1_GIANTS: frozenset[str] = frozenset({
    "apple", "nvidia", "microsoft", "amazon", "alphabet", "google",
    "meta", "broadcom", "tsmc", "samsung", "aws", "azure",
    "amazon web services", "google cloud", "microsoft azure",
    "department of defense", "dod", "nasa", "doe", "department of energy",
    "toyota", "volkswagen", "stellantis", "ford", "general motors",
    "pfizer", "johnson & johnson", "abbvie", "merck", "eli lilly",
    "tesla", "intel", "qualcomm", "amd", "arm",
})

# ── 8-K 規則抽取 ──────────────────────────────────────────────────────

def _parse_magnitude(text: str) -> Optional[float]:
    """從文字抽取第一個金額（美元，百萬/十億換算）。"""
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        if unit in ("billion", "b"):
            num *= 1_000_000_000
        else:
            num *= 1_000_000
        return num
    except ValueError:
        return None


def _parse_timeline(text: str) -> Optional[int]:
    """從文字抽取季度日期，估算距今月數（Q[1-4] 20xx → 近似月數）。"""
    m = _QUARTER_RE.search(text)
    if not m:
        return None
    try:
        parts = m.group().split()
        q = int(parts[0][1])
        yr = int(parts[1])
        from datetime import datetime
        now = datetime.utcnow()
        est_month = q * 3  # Q1→3, Q2→6, Q3→9, Q4→12
        months = (yr - now.year) * 12 + (est_month - now.month)
        return max(1, months) if months > 0 else None
    except Exception:
        return None


def _detect_tier(text: str) -> str:
    """
    比對 tier1 字典（小寫）；找到回 tier1_giant，
    其他具名視為 tier2（規則層無法區分，保守 unknown）。
    """
    text_lower = text.lower()
    for name in TIER1_GIANTS:
        if name in text_lower:
            return "tier1_giant"
    return "unknown"  # 規則層無法可靠判 tier2，保守回 unknown


def _item_headline(item: str, event_type: str) -> str:
    """根據 Item 編號產生中文事件標題（≤20 字）。"""
    _MAP = {
        "1.01": "簽訂重大協議",
        "1.02": "重大協議終止",
        "1.03": "申請破產或接管",
        "2.01": "完成收購或出售資產",
        "2.02": "公布業績或財務指引",
        "2.03": "新增重大財務義務",
        "2.04": "觸發加速還款條款",
        "2.05": "宣布重組退出計畫",
        "2.06": "認列重大資產減值",
        "3.01": "收到下市通知",
        "3.02": "宣布未登記股權出售",
        "3.03": "修改股東權利條款",
        "4.01": "更換認證會計師",
        "4.02": "財報資料不可信賴",
        "5.01": "發生控制權變更",
        "5.02": "高管人員異動",
        "7.01": "Reg FD 揭露重大資訊",
        "8.01": "其他重大事件揭露",
    }
    return _MAP.get(item, "重大事件揭露")


def extract_8k_events(filing: dict) -> list[dict]:
    """
    對一份 8-K 申報執行規則引擎抽取（§6.7）。
    specificity 封頂 3，extraction_method='rule'。
    """
    items    = filing.get("items", [])
    text     = filing.get("text", "")
    ticker   = filing.get("ticker", "")
    acc_no   = filing.get("accession_no", "")
    filing_date = filing.get("filing_date", "")
    source_url  = filing.get("source_url", "")

    if not items:
        items = ["8.01"]  # 無解析到 Item → 兜底

    events: list[dict] = []
    magnitude = _parse_magnitude(text)
    timeline  = _parse_timeline(text)
    tier      = _detect_tier(text)
    is_dilution = bool(_DILUTION_RE.search(text))

    # 對每個 PASS Item 產生一個事件
    for seq, item in enumerate(items):
        event_type = ITEM_EVENT_MAP.get(item, "other")
        direction  = _DIRECTION_MAP.get(event_type, "neutral")
        headline   = _item_headline(item, event_type)

        # specificity：有金額 → 3；有季度日期 → 2；否則 → 1（§6.7 封頂 3）
        if magnitude is not None:
            specificity = 3
        elif timeline is not None:
            specificity = 2
        else:
            specificity = 1

        is_integrity = event_type in _INTEGRITY_TYPES
        # dilution：item 3.02 或文字含稀釋關鍵字
        ev_dilution = (item == "3.02") or is_dilution

        # evidence_anchor：取文字前 15 字（逐字錨，§6.3）
        anchor = text[:15].strip() if text else None

        events.append({
            "accession_no":      acc_no,
            "seq_in_filing":     seq,
            "ticker":            ticker,
            "event_date":        filing_date,
            "source":            "8-K",
            "source_url":        source_url,
            "event_type":        event_type,
            "headline":          headline,
            "counterparty":      None,
            "counterparty_tier": tier,
            "magnitude_usd":     magnitude,
            "magnitude_pct_rev": None,
            "timeline_months":   timeline,
            "is_recurring":      False,
            "specificity":       specificity,
            "direction":         direction,
            "is_integrity_flag": is_integrity,
            "is_dilution_flag":  ev_dilution,
            "evidence_anchor":   anchor,
            "extraction_method": "rule",
        })

    return events


def extract_form4_events(filing: dict) -> list[dict]:
    """
    Form 4 規則解析（§L2 Form4 處理）：
    不走 LLM，規則直接產 insider_buy/insider_sell 事件。
    """
    transactions = filing.get("transactions", [])
    ticker       = filing.get("ticker", "")
    acc_no       = filing.get("accession_no", "")
    filing_date  = filing.get("filing_date", "")
    source_url   = filing.get("source_url", "")

    events: list[dict] = []
    for seq, txn in enumerate(transactions):
        code = txn.get("code", "")
        if code not in ("P", "S"):
            continue

        event_type = "insider_buy" if code == "P" else "insider_sell"
        direction  = "bullish" if code == "P" else "bearish"
        magnitude  = txn.get("magnitude_usd")
        owner      = txn.get("owner_name", "")
        title      = txn.get("owner_title", "")

        headline = (
            f"{'高管' if title else '內部人'}公開市場買入股份"
            if code == "P"
            else f"{'高管' if title else '內部人'}公開市場賣出股份"
        )

        anchor = f"{owner[:10]} {code}" if owner else code

        events.append({
            "accession_no":      acc_no,
            "seq_in_filing":     seq,
            "ticker":            ticker,
            "event_date":        txn.get("date") or filing_date,
            "source":            "Form4",
            "source_url":        source_url,
            "event_type":        event_type,
            "headline":          headline[:20],
            "counterparty":      None,
            "counterparty_tier": "unknown",
            "magnitude_usd":     magnitude,
            "magnitude_pct_rev": None,
            "timeline_months":   None,
            "is_recurring":      False,
            "specificity":       3 if magnitude else 2,
            "direction":         direction,
            "is_integrity_flag": False,
            "is_dilution_flag":  False,
            "evidence_anchor":   anchor[:15],
            "extraction_method": "rule",
        })

    return events


def extract_events(filing: dict) -> list[dict]:
    """
    通用入口：依申報類型分派規則引擎。
    Form 4 → extract_form4_events
    8-K   → extract_8k_events
    """
    form = filing.get("form_type", "")
    if form == "4":
        return extract_form4_events(filing)
    return extract_8k_events(filing)
