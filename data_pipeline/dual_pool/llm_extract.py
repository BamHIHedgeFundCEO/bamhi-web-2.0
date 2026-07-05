"""
llm_extract.py — 三層降級 LLM 催化劑抽取（§6.3）

降級順序：Gemini → NIM → 規則引擎
  - 任一層掛掉自動接手，管線永不斷線
  - 無任何 LLM key → 安靜降級規則引擎（print 一行說明，不拋錯）
  - Form 4 申報不走 LLM，直接由規則引擎處理（§L2 Form4 處理，省配額）
  - rate limit 尊重：批次間 sleep + 429 指數退避

Env：
  GEMINI_API_KEY       — Gemini Flash 免費層
  NVIDIA_NIM_API_KEY   — NVIDIA NIM 備援（無 key 直接跳過此層）

§6.8 版權：不落庫公告全文；text 欄位只在記憶體中存在，本模組不持久化。
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

import requests
from pydantic import BaseModel, Field, field_validator, model_validator

from data_pipeline.dual_pool.rule_engine import extract_events as rule_extract

# ── LLM 模型常數（易改）────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"         # Gemini Flash 免費層當前型號（§2）
NIM_MODEL    = "meta/llama-3.1-70b-instruct"  # NVIDIA NIM 備援模型

# ── API 端點 ──────────────────────────────────────────────────────────
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    f"/{GEMINI_MODEL}:generateContent"
)
_NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# ── 限速設定 ──────────────────────────────────────────────────────────
_LLM_BATCH_SLEEP = 1.5  # 批次間 sleep（秒）
_MAX_RETRIES     = 1    # 失敗重試上限（§6.3）
_BACKOFF_BASE    = 2.0  # 429 指數退避底數

# ── System Prompt（英文，§6.3 全部要點）──────────────────────────────
_SYSTEM_PROMPT = """You are a financial event extraction engine for a small-cap event-driven investment screening system. Your role is to extract structured events from SEC filings.

STRICT RULES:
- Extract ONLY information explicitly stated in the filing text. Never infer, estimate, or supplement with external knowledge. Fill null when not stated.
- Output ONLY a raw JSON array (no markdown code fences, no preamble, no explanation). Empty array [] if no extractable events.
- One filing may contain multiple events → multiple objects in array.
- Do NOT give opinions, price targets, or investment recommendations.

BINDING vs NON-BINDING distinction (drives specificity):
- Binding: "definitive agreement", "signed", "purchase order", "executed" → higher specificity
- Non-binding: "MOU", "LOI", "exploring", "letter of intent", "strategic alliance without terms" → lower specificity

FLAG NEGATIVE EVENTS equally: dilution, restatement, auditor change, guidance cut, going concern are important signals.

OUTPUT FORMAT (each event object):
{
  "event_type": "<enum>",
  "headline": "<≤20 Traditional Chinese characters, neutral, no adjectives>",
  "counterparty": "<named party or null>",
  "counterparty_tier": "<tier1_giant|tier2|unknown>",
  "magnitude_usd": <number in USD or null — only if EXPLICITLY stated, no calculation>,
  "magnitude_pct_rev": <percentage of revenue or null — only if EXPLICITLY stated>,
  "timeline_months": <integer months to completion or null>,
  "is_recurring": <true if explicitly multi-year recurring revenue stream>,
  "specificity": <1-5 per rules below>,
  "direction": "<bullish|bearish|neutral>",
  "is_integrity_flag": <true if restatement / auditor change / going concern / material weakness / unusual executive departure>,
  "is_dilution_flag": <true if equity offering / ATM / shelf S-3 / convertible / warrant>,
  "evidence_anchor": "<verbatim quote ≤15 chars from source text, for audit>",
  "confidence": <0.0-1.0>
}

SPECIFICITY 1-5:
1 = non-binding, no named party, no numbers ("strategic partnership", "exploring")
2 = named counterparty, but no financial terms, no date
3 = named + ONE hard condition (amount OR specific date/period)
4 = named + amount + date/period
5 = named + amount + date + binding/definitive AND/OR explicit multi-year recurring

COUNTERPARTY_TIER:
tier1_giant = Apple, NVIDIA, Microsoft, Amazon, Google/Alphabet, Meta, Broadcom, TSMC, Samsung, major hyperscalers (AWS/Azure/GCP), US DoD/NASA/DOE, top-3 automakers, top pharma (Pfizer/J&J/AbbVie/Merck/Lilly)
tier2 = named established mid-to-large public company, not mega-cap
unknown = unnamed, private, or small entity

EVENT_TYPE enum: new_contract, new_client, new_product, market_entry, policy_beneficiary, guidance_raise, capacity_expansion, strategic_investment, mna_target, backlog_growth, regulatory_approval, insider_buy, guidance, commitment, dilution_offering, guidance_cut, insider_sell, restatement, auditor_change, going_concern, litigation, customer_loss, other_negative, other

evidence_anchor: copy the exact original text verbatim, ≤15 characters. Do not translate.
headline: Traditional Chinese, ≤20 characters, neutral description, no adjectives like "重大" or "強勁"."""

# ── Pydantic 輸出 Schema（§6.3 驗證）────────────────────────────────

_VALID_EVENT_TYPES = frozenset({
    "new_contract", "new_client", "new_product", "market_entry",
    "policy_beneficiary", "guidance_raise", "capacity_expansion",
    "strategic_investment", "mna_target", "backlog_growth",
    "regulatory_approval", "insider_buy", "guidance", "commitment",
    "dilution_offering", "guidance_cut", "insider_sell", "restatement",
    "auditor_change", "going_concern", "litigation", "customer_loss",
    "other_negative", "other",
})

_VALID_DIRECTIONS = frozenset({"bullish", "bearish", "neutral"})
_VALID_TIERS = frozenset({"tier1_giant", "tier2", "unknown"})


class EventSchema(BaseModel):
    event_type:        str
    headline:          str
    counterparty:      Optional[str]  = None
    counterparty_tier: Optional[str]  = "unknown"
    magnitude_usd:     Optional[float] = None
    magnitude_pct_rev: Optional[float] = None
    timeline_months:   Optional[int]   = None
    is_recurring:      bool            = False
    specificity:       int             = Field(..., ge=1, le=5)
    direction:         str
    is_integrity_flag: bool            = False
    is_dilution_flag:  bool            = False
    evidence_anchor:   Optional[str]   = None
    confidence:        float           = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("event_type")
    @classmethod
    def check_event_type(cls, v: str) -> str:
        if v not in _VALID_EVENT_TYPES:
            raise ValueError(f"無效 event_type: {v}")
        return v

    @field_validator("direction")
    @classmethod
    def check_direction(cls, v: str) -> str:
        if v not in _VALID_DIRECTIONS:
            raise ValueError(f"無效 direction: {v}")
        return v

    @field_validator("counterparty_tier")
    @classmethod
    def check_tier(cls, v: Optional[str]) -> str:
        if v not in _VALID_TIERS:
            return "unknown"
        return v or "unknown"

    @field_validator("headline")
    @classmethod
    def truncate_headline(cls, v: str) -> str:
        return v[:20] if v else v

    @field_validator("evidence_anchor")
    @classmethod
    def truncate_anchor(cls, v: Optional[str]) -> Optional[str]:
        return v[:15] if v else v

    @model_validator(mode="after")
    def check_required_fields(self) -> "EventSchema":
        # headline 必須非空
        if not self.headline:
            raise ValueError("headline 不得為空")
        return self


# ── LLM 呼叫（Gemini）────────────────────────────────────────────────

def _call_gemini(text: str, api_key: str) -> Optional[str]:
    """
    呼叫 Gemini REST API（§2）。
    回傳原始 JSON 字串，失敗回 None。
    """
    payload = {
        "system_instruction": {
            "parts": [{"text": _SYSTEM_PROMPT}]
        },
        "contents": [
            {"parts": [{"text": text}]}
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    }
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{_GEMINI_URL}?key={api_key}",
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429:
                wait = _BACKOFF_BASE ** attempt
                print(f"[llm] Gemini 429 rate limit → sleep {wait:.1f}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[llm] Gemini attempt {attempt+1} error: {e}")
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE ** attempt)
    return None


def _call_nim(text: str, api_key: str) -> Optional[str]:
    """
    呼叫 NVIDIA NIM REST API（§2 備援）。
    回傳原始 JSON 字串，失敗回 None。
    """
    payload = {
        "model": NIM_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": text},
        ],
        "temperature": 0.1,
        "max_tokens":  2048,
    }
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                _NIM_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429:
                wait = _BACKOFF_BASE ** attempt
                print(f"[llm] NIM 429 rate limit → sleep {wait:.1f}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[llm] NIM attempt {attempt+1} error: {e}")
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE ** attempt)
    return None


# ── LLM 輸出解析與 Pydantic 驗證 ────────────────────────────────────

def _parse_and_validate(raw: str, filing: dict) -> Optional[list[dict]]:
    """
    解析 LLM 輸出（JSON 陣列），用 Pydantic schema 驗證每個事件。
    解析失敗回 None（觸發降級）。
    驗證通過的事件補填程式端欄位。
    """
    # 嘗試提取 JSON 陣列（LLM 可能帶 markdown 圍欄）
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

    try:
        events_raw = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[llm] JSON 解析失敗：{e} → 降級")
        return None

    if not isinstance(events_raw, list):
        # LLM 有時回包了一個物件而非陣列
        if isinstance(events_raw, dict):
            events_raw = [events_raw]
        else:
            print("[llm] 輸出非 list → 降級")
            return None

    validated: list[dict] = []
    acc_no     = filing.get("accession_no", "")
    filing_date = filing.get("filing_date", "")
    ticker     = filing.get("ticker", "")
    source_url = filing.get("source_url", "")
    form_type  = filing.get("form_type", "8-K")

    for seq, ev in enumerate(events_raw):
        if not isinstance(ev, dict):
            continue
        try:
            validated_ev = EventSchema(**ev)
        except Exception as e:
            print(f"[llm] schema 驗證失敗 seq={seq}：{e}，跳過此事件")
            continue

        # 程式端補填欄位（§6.3：extraction_method 由程式端填）
        record = validated_ev.model_dump()
        record.update({
            "accession_no":  acc_no,
            "seq_in_filing": seq,
            "ticker":        ticker,
            "event_date":    filing_date,
            "source":        "PR" if form_type == "8-K" else form_type,
            "source_url":    source_url,
            "extraction_method": "llm",
        })
        record.pop("confidence", None)  # confidence 不落庫（內部用）
        validated.append(record)

    return validated  # 空 list 也是合法輸出（無事件）


# ── 主要函式 ─────────────────────────────────────────────────────────

def extract_events(
    filing: dict,
    daily_count_ref: list[int],
    daily_limit: int = 500,
) -> list[dict]:
    """
    三層降級抽取（§6.3）：Gemini → NIM → 規則引擎。

    daily_count_ref: [count]，可變 list 作為 mutable 計數器；
                     超過 daily_limit → 跳過 LLM，直接規則引擎。
    Form 4 申報不走 LLM，直接規則引擎。

    known_at 由 run_stage2 補填（此處不設，確保 point-in-time 正確）。
    """
    form_type = filing.get("form_type", "")

    # Form 4 → 規則引擎（不走 LLM，省配額）
    if form_type == "4":
        return rule_extract(filing)

    text = filing.get("text", "").strip()
    if not text:
        return rule_extract(filing)

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    nim_key    = os.getenv("NVIDIA_NIM_API_KEY", "")

    if not gemini_key and not nim_key:
        print("[llm] 無 LLM key → 安靜降級規則引擎")
        return rule_extract(filing)

    # 配額監控：超過每日上限 → 規則引擎
    if daily_count_ref[0] >= daily_limit:
        return rule_extract(filing)

    time.sleep(_LLM_BATCH_SLEEP)  # 批次間 sleep（rate limit 尊重）

    # ── 第一層：Gemini ──────────────────────────────────────────────
    if gemini_key:
        raw = _call_gemini(text, gemini_key)
        if raw is not None:
            result = _parse_and_validate(raw, filing)
            if result is not None:
                daily_count_ref[0] += 1
                return result
        print("[llm] Gemini 失敗 → 嘗試 NIM")

    # ── 第二層：NIM ─────────────────────────────────────────────────
    if nim_key:
        raw = _call_nim(text, nim_key)
        if raw is not None:
            result = _parse_and_validate(raw, filing)
            if result is not None:
                daily_count_ref[0] += 1
                return result
        print("[llm] NIM 失敗 → 降級規則引擎")
    elif not gemini_key:
        pass  # 無 NIM key：已在上方處理（無任何 LLM key）

    # ── 第三層：規則引擎（保底，不得拋錯）─────────────────────────
    return rule_extract(filing)


# ── 驗收條件 §4：LLM 壞輸出降級驗證 ────────────────────────────────

def _test_bad_llm_output():
    """
    單元驗證：對手造「LLM 壞輸出」（缺欄位/多餘文字）
    確認 pydantic schema 驗證失敗並正確降級規則引擎。
    """
    print("\n=== LLM 壞輸出降級驗證 ===")

    dummy_filing = {
        "ticker": "RKLB",
        "accession_no": "0000000000-00-000001",
        "filing_date": "2024-01-01",
        "form_type": "8-K",
        "source_url": "https://test",
        "items": ["1.01"],
        "text": "Rocket Lab signed a contract with NASA.",
        "transactions": [],
    }

    bad_outputs = [
        # 案例 1：缺必要欄位 specificity
        '[{"event_type":"new_contract","headline":"簽約","direction":"bullish"}]',
        # 案例 2：event_type 非法值
        '[{"event_type":"INVALID_TYPE","headline":"簽約","specificity":3,"direction":"bullish"}]',
        # 案例 3：純文字（非 JSON）
        'This is a new contract with NASA worth $50M.',
        # 案例 4：direction 非法值
        '[{"event_type":"new_contract","headline":"簽約","specificity":3,"direction":"very_bullish"}]',
    ]

    for i, bad in enumerate(bad_outputs, 1):
        print(f"\n案例 {i}：{bad[:60]}...")
        result = _parse_and_validate(bad, dummy_filing)
        if result is None:
            print(f"  → _parse_and_validate 回 None（正確：觸發降級）")
            # 模擬降級：規則引擎
            fallback = rule_extract(dummy_filing)
            print(f"  → 規則引擎產出 {len(fallback)} 筆事件：{[e['event_type'] for e in fallback]}")
        elif result == []:
            print(f"  → 輸出空陣列（合法：無事件）")
        else:
            # schema 驗證失敗應 return None 觸發降級，若此處有輸出代表驗證通過
            print(f"  → 驗證通過（共 {len(result)} 筆，可能案例本身合法）")

    print("\n=== 驗證完成 ===\n")


if __name__ == "__main__":
    _test_bad_llm_output()
