"""
run_stage2.py — 階段 2 Orchestrator

執行順序：
  讀 watchpool（active，左+右）→ EDGAR 抓取 → 規則過濾 → LLM 抽取 → upsert events

關鍵設計（§8.2 point-in-time）：
  known_at = 實際處理時刻 UTC ISO（非 filing_date）
  回測只使用 known_at < 模擬日期 的事件，確保前向一致性

§6.8 版權：公告 text 欄位在 LLM 處理後不落庫

§8.3 LLM 配額監控：
  DAILY_LLM_LIMIT = 500（保守上限）
  超過 → 本輪剩餘申報使用規則引擎（順延次日精神，§8.3）

環境變數：
  SUPABASE_URL / SUPABASE_SERVICE_KEY — 無憑證時 fallback 本地檔
  GEMINI_API_KEY                      — Gemini Flash 免費層
  NVIDIA_NIM_API_KEY                  — NVIDIA NIM 備援
  EDGAR_USER_AGENT                    — SEC User-Agent
  DUAL_POOL_DATA_DIR                  — 本地資料根目錄（預設 data/dual_pool）
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.dual_pool import storage
from data_pipeline.dual_pool.edgar_fetch import (
    fetch_watchpool_filings,
    get_fetch_degraded_count,
    load_processed_accessions,
    reset_fetch_degraded_count,
    save_processed_accessions,
)
from data_pipeline.dual_pool.rule_filter import filter_filings
from data_pipeline.dual_pool.llm_extract import extract_events

# ── 常數 ──────────────────────────────────────────────────────────────
DAILY_LLM_LIMIT = 500  # LLM 每日配額保守上限（§8.3；超過 → 規則引擎接手）


def run_stage2():
    """
    主入口：L2 EDGAR 抓取 + 規則過濾 + LLM/規則抽取 + 落庫。
    """
    run_start = datetime.now(timezone.utc)
    print(f"[stage2] === 開始 {run_start.isoformat(timespec='seconds')} ===")

    # ── 1. 讀 watchpool（active，左+右）──────────────────────────────
    all_rows = storage.load_watchpool()
    active_tickers = [
        r["ticker"]
        for r in all_rows
        if r.get("status", "active") == "active"
    ]
    if not active_tickers:
        print("[stage2] watchpool 無 active ticker，退出")
        return {"tickers": 0, "filings_fetched": 0, "events_upserted": 0}

    print(f"[stage2] watchpool active ticker 數：{len(active_tickers)}")

    # ── 2. 載入已處理 accession（冪等用）────────────────────────────
    processed_accessions = load_processed_accessions()
    print(f"[stage2] 已處理 accession 數：{len(processed_accessions)}")

    # ── 3. EDGAR 抓取（增量；初次 90 日回補，後續 2 日增量）─────────
    reset_fetch_degraded_count()
    raw_filings = fetch_watchpool_filings(
        tickers=active_tickers,
        processed_accessions=processed_accessions,
        backfill_days=None,  # 自動偵測（空集合 → 90 日；有記錄 → 2 日）
    )
    print(f"[stage2] 抓取申報 {len(raw_filings)} 份")

    # ── 4. 規則過濾（§6.2）────────────────────────────────────────
    filtered_filings = filter_filings(raw_filings)
    print(f"[stage2] 規則過濾後 {len(filtered_filings)} 份")

    # 所有已抓取申報（含過濾掉的）都標記為已處理，避免每日重抓噪音申報
    for f in raw_filings:
        processed_accessions.add(f["accession_no"])

    # ── 5. LLM/規則抽取事件（三層降級）──────────────────────────────
    daily_llm_count = [0]  # mutable ref 供 extract_events 計數
    all_events: list[dict] = []

    # known_at = 此次批次實際處理時刻 UTC（§8.2 point-in-time 核心）
    known_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    quota_warned = False  # 配額警告只印一次（防洗版）
    for filing in filtered_filings:
        # 配額監控（§8.3 精神）
        if daily_llm_count[0] >= DAILY_LLM_LIMIT and not quota_warned:
            print(
                f"[stage2] ⚠ LLM 每日配額 {DAILY_LLM_LIMIT} 已達，"
                f"剩餘申報改用規則引擎"
            )
            quota_warned = True

        events = extract_events(
            filing,
            daily_count_ref=daily_llm_count,
            daily_limit=DAILY_LLM_LIMIT,
        )

        # 補填 known_at（程式端填，§8.2）
        for ev in events:
            ev["known_at"] = known_at
            # 確保 text 欄位不落庫（§6.8 版權保護）
            ev.pop("text", None)

        all_events.extend(events)

    print(
        f"[stage2] 抽取事件 {len(all_events)} 筆 "
        f"（LLM 呼叫 {daily_llm_count[0]} 次）"
    )

    # ── 6. 落庫（§3.2 events 表）─────────────────────────────────────
    if all_events:
        storage.upsert_events(all_events)
    elif len(raw_filings) == 0:
        print("[stage2] 無新申報（正常）")
    else:
        # 紅旗：有抓到申報卻 0 事件——防「success 但全零」的靜默故障
        print(
            f"[stage2] ⚠ 警告：抓到 {len(raw_filings)} 份申報但 0 事件產出"
            f"——檢查 rule_filter/抽取鏈"
        )

    # ── 7. 持久化已處理 accession（冪等維護）────────────────────────
    save_processed_accessions(processed_accessions)

    elapsed = (datetime.now(timezone.utc) - run_start).total_seconds()
    print(
        f"[stage2] === 完成 elapsed={elapsed:.0f}s "
        f"events={len(all_events)} llm_calls={daily_llm_count[0]} ==="
    )

    # ── 8. 摘要統計 ──────────────────────────────────────────────────
    llm_events  = sum(1 for e in all_events if e.get("extraction_method") == "llm")
    rule_events = len(all_events) - llm_events
    form4_events = sum(1 for e in all_events if e.get("source") == "Form4")
    fetch_degraded = get_fetch_degraded_count()
    print(
        f"[stage2] 事件明細："
        f"  LLM={llm_events} / Rule={rule_events} / Form4={form4_events}"
    )
    if fetch_degraded:
        print(f"[stage2] fetch_degraded={fetch_degraded}（EX-99 PR 補取失敗，已降級主文）")

    return {
        "tickers":         len(active_tickers),
        "filings_fetched": len(raw_filings),
        "filings_filtered": len(filtered_filings),
        "events_upserted": len(all_events),
        "llm_calls":       daily_llm_count[0],
        "fetch_degraded":  fetch_degraded,
        "elapsed_s":       round(elapsed, 1),
    }


if __name__ == "__main__":
    result = run_stage2()
    print("\n[stage2] 結果摘要:")
    for k, v in result.items():
        print(f"  {k}: {v}")
