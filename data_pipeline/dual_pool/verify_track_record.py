"""
verify_track_record.py — track_record 每週驗證 job（§7.6）

執行流程：
  1. 載入 deadline < today 且 verified IS NULL 的 promise
  2. 對每筆 promise：
       a. 拉該 ticker 在 deadline 前後 45 天的 events（從 storage.load_events）
       b. 呼叫 LLM 判定 promise 是否兌現（Gemini → NIM → 規則降級）
       c. LLM 判定：true/false → 寫 verified + verify_date + verify_method='llm'
          LLM 判定 unknown → verify_attempts+1；≥2 次 → verify_method='manual'（人工佇列）
  3. 批次更新 track_record

LLM 降級鏈（照 llm_extract.py §2/§6.3 規範）：
  Gemini → NIM → 規則（關鍵字判斷）

Env：
  GEMINI_API_KEY       — Gemini Flash 免費層
  NVIDIA_NIM_API_KEY   — NVIDIA NIM 備援
  DUAL_POOL_DATA_DIR   — 本地資料根目錄
  SUPABASE_URL / SUPABASE_SERVICE_KEY
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

from data_pipeline.dual_pool import storage

# ── LLM 常數（與 llm_extract.py 一致）──────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"
NIM_MODEL    = "meta/llama-3.1-70b-instruct"

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    f"/{GEMINI_MODEL}:generateContent"
)
_NIM_URL    = "https://integrate.api.nvidia.com/v1/chat/completions"

# 限速
_LLM_SLEEP = 2.0   # LLM 呼叫間隔（秒）

# 人工佇列門檻
_MANUAL_THRESHOLD = 2  # unknown 累計次數 → 升級 manual

# Context 視窗（promise 前後天數）
_CONTEXT_DAYS = 45


# ──────────────────────────────────────────────────────────────────────
# 驗證 System Prompt
# ──────────────────────────────────────────────────────────────────────

_VERIFY_SYSTEM = """You are a financial promise verification assistant. Your job is to determine whether a company fulfilled a specific guidance or commitment.

STRICT RULES:
- Base your judgment ONLY on the provided events and context. Do not use external knowledge.
- Output ONLY a raw JSON object: {"result": "true"|"false"|"unknown", "reasoning": "<brief reason ≤30 chars>"}
- "true": The promise was clearly fulfilled based on available evidence.
- "false": The promise was clearly not fulfilled (missed deadline, contradicted by events).
- "unknown": Insufficient evidence to determine. Use this when you cannot reach a conclusion.
- Do not guess. Return "unknown" when in doubt.
- No markdown fences, no preamble."""


def _build_verify_prompt(promise: dict, events: list[dict]) -> str:
    """建立 LLM 驗證 prompt。"""
    deadline = promise.get("promise_deadline", "")
    text     = promise.get("promise_text", "")
    ticker   = promise.get("ticker", "")

    event_lines = []
    for e in events[:20]:  # 最多 20 個 events
        ed   = e.get("event_date") or e.get("known_at", "")[:10]
        etype = e.get("event_type", "")
        hl   = e.get("headline", "")
        mag  = e.get("magnitude_usd")
        mag_str = f" (${mag:,.0f})" if mag else ""
        event_lines.append(f"  [{ed}] {etype}: {hl}{mag_str}")

    events_text = "\n".join(event_lines) if event_lines else "  (no relevant events found)"

    return (
        f"Company: {ticker}\n"
        f"Promise made: {text}\n"
        f"Deadline: {deadline}\n\n"
        f"Relevant events (±{_CONTEXT_DAYS} days around deadline):\n"
        f"{events_text}\n\n"
        f"Did the company fulfill the promise? Respond with JSON only."
    )


# ──────────────────────────────────────────────────────────────────────
# LLM 呼叫（Gemini → NIM → 規則）
# ──────────────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> Optional[str]:
    """呼叫 Gemini，回傳 JSON 字串或 None。"""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        resp = requests.post(
            f"{_GEMINI_URL}?key={api_key}",
            json={
                "system_instruction": {"parts": [{"text": _VERIFY_SYSTEM}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 128},
            },
            timeout=30,
        )
        if resp.status_code == 200:
            candidates = resp.json().get("candidates", [])
            if candidates:
                return candidates[0]["content"]["parts"][0]["text"]
        elif resp.status_code == 429:
            time.sleep(30)
    except Exception as e:
        print(f"[verify] Gemini 呼叫失敗: {e}")
    return None


def _call_nim(prompt: str) -> Optional[str]:
    """呼叫 NVIDIA NIM，回傳 JSON 字串或 None。"""
    api_key = os.getenv("NVIDIA_NIM_API_KEY", "")
    if not api_key:
        return None
    try:
        resp = requests.post(
            _NIM_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": NIM_MODEL,
                "messages": [
                    {"role": "system", "content": _VERIFY_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 128,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            choices = resp.json().get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
    except Exception as e:
        print(f"[verify] NIM 呼叫失敗: {e}")
    return None


def _rule_verify(promise: dict, events: list[dict]) -> str:
    """
    規則引擎降級：關鍵字判斷。
    找與 promise 相關的正面/負面事件。
    無法判斷 → 'unknown'。
    """
    text = promise.get("promise_text", "").lower()
    deadline = promise.get("promise_deadline", "")

    positive_types = {
        "new_contract", "new_client", "guidance_raise", "regulatory_approval",
        "backlog_growth", "capacity_expansion",
    }
    negative_types = {
        "guidance_cut", "going_concern", "customer_loss", "restatement",
    }

    for e in events:
        etype = e.get("event_type", "")
        if etype in positive_types:
            return "true"
        if etype in negative_types:
            return "false"

    return "unknown"


def _parse_llm_result(raw: Optional[str]) -> Optional[str]:
    """解析 LLM 回傳的 JSON 字串 → 'true'/'false'/'unknown'。"""
    if not raw:
        return None
    try:
        # 去除可能的 markdown 圍欄
        clean = re.sub(r"```[a-z]*\n?", "", raw).strip()
        data  = json.loads(clean)
        result = str(data.get("result", "")).lower()
        if result in ("true", "false", "unknown"):
            return result
    except Exception:
        # 備援：正則搜尋
        m = re.search(r'"result"\s*:\s*"(true|false|unknown)"', raw, re.IGNORECASE)
        if m:
            return m.group(1).lower()
    return None


def _verify_promise(promise: dict, events: list[dict]) -> str:
    """
    驗證一筆 promise，回傳 'true'/'false'/'unknown'。
    降級鏈：Gemini → NIM → 規則引擎。
    """
    prompt = _build_verify_prompt(promise, events)

    # Gemini
    raw = _call_gemini(prompt)
    time.sleep(_LLM_SLEEP)
    if raw:
        result = _parse_llm_result(raw)
        if result:
            return result

    # NIM
    raw = _call_nim(prompt)
    time.sleep(_LLM_SLEEP)
    if raw:
        result = _parse_llm_result(raw)
        if result:
            return result

    # 規則引擎
    return _rule_verify(promise, events)


# ──────────────────────────────────────────────────────────────────────
# 主 job 函式
# ──────────────────────────────────────────────────────────────────────

def run_verify_job() -> dict:
    """
    track_record 每週驗證 job 主入口。
    回傳 dict: promises_checked, fulfilled, failed, unknown, manual_escalated, elapsed_s
    """
    run_start = datetime.now(timezone.utc)
    today     = date.today()
    print(f"[verify] === 開始 {run_start.isoformat(timespec='seconds')} ===")

    # 1. 載入到期未核 promise
    expired = storage.load_track_record_expired(today)
    print(f"[verify] 到期未核 promise: {len(expired)} 筆")
    if not expired:
        return {
            "promises_checked": 0, "fulfilled": 0, "failed": 0,
            "unknown": 0, "manual_escalated": 0, "elapsed_s": 0.0,
        }

    # 2. 批次載入所有相關 ticker 的 events（一次載入，減少 DB 查詢）
    all_events = storage.load_events(days=730)  # 兩年內 events
    events_by_ticker: dict[str, list[dict]] = {}
    for e in all_events:
        t = e.get("ticker") or ""
        events_by_ticker.setdefault(t, []).append(e)

    # 3. 逐筆驗證
    updates: list[dict] = []
    stats = {"fulfilled": 0, "failed": 0, "unknown": 0, "manual_escalated": 0}

    for promise in expired:
        ticker   = promise.get("ticker", "")
        deadline_str = promise.get("promise_deadline", "")
        attempts = int(promise.get("verify_attempts") or 0)

        # 篩選 deadline 前後 45 天的 events
        try:
            deadline_dt = date.fromisoformat(deadline_str)
        except ValueError:
            deadline_dt = today

        window_start = (deadline_dt - timedelta(days=_CONTEXT_DAYS)).isoformat()
        window_end   = (deadline_dt + timedelta(days=_CONTEXT_DAYS)).isoformat()

        context_events = [
            e for e in events_by_ticker.get(ticker, [])
            if window_start <= (e.get("event_date") or e.get("known_at", "")[:10]) <= window_end
        ]

        # LLM 驗證
        result = _verify_promise(promise, context_events)
        print(f"[verify] {ticker} [{deadline_str}]: {result} (attempts={attempts+1})")

        verify_date = today.isoformat()
        new_attempts = attempts + 1

        if result == "unknown":
            stats["unknown"] += 1
            if new_attempts >= _MANUAL_THRESHOLD:
                # 升級人工佇列
                stats["manual_escalated"] += 1
                updates.append({
                    "ticker":          ticker,
                    "promise_date":    promise.get("promise_date"),
                    "promise_text":    promise.get("promise_text"),
                    "verified":        None,       # 仍待核
                    "verify_date":     verify_date,
                    "verify_method":   "manual",   # 人工佇列
                    "verify_attempts": new_attempts,
                })
            else:
                # 記錄嘗試次數，不改 verify_method
                updates.append({
                    "ticker":          ticker,
                    "promise_date":    promise.get("promise_date"),
                    "promise_text":    promise.get("promise_text"),
                    "verified":        None,
                    "verify_date":     None,       # 未確認，不設 verify_date
                    "verify_method":   None,
                    "verify_attempts": new_attempts,
                })
        else:
            # true 或 false
            verified = result == "true"
            if verified:
                stats["fulfilled"] += 1
            else:
                stats["failed"] += 1
            updates.append({
                "ticker":          ticker,
                "promise_date":    promise.get("promise_date"),
                "promise_text":    promise.get("promise_text"),
                "verified":        verified,
                "verify_date":     verify_date,
                "verify_method":   "llm",
                "verify_attempts": new_attempts,
            })

    # 4. 批次更新
    if updates:
        storage.update_track_record(updates)
        print(f"[verify] 更新 {len(updates)} 筆 track_record")

    elapsed = (datetime.now(timezone.utc) - run_start).total_seconds()
    print(f"[verify] === 完成 elapsed={elapsed:.0f}s ===")
    print(f"[verify] 統計: {stats}")

    return {
        "promises_checked":  len(expired),
        "fulfilled":         stats["fulfilled"],
        "failed":            stats["failed"],
        "unknown":           stats["unknown"],
        "manual_escalated":  stats["manual_escalated"],
        "elapsed_s":         round(elapsed, 1),
    }


if __name__ == "__main__":
    result = run_verify_job()
    print("\n[verify] 結果摘要:")
    for k, v in result.items():
        print(f"  {k}: {v}")
