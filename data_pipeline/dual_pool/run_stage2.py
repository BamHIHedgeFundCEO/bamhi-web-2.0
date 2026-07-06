"""
run_stage2.py — 階段 2 Orchestrator

執行順序：
  讀 watchpool（active，左+右）→ 切批（TICKER_BATCH 檔/批）→
  每批：fetch → filter → extract → upsert events → add_processed_accessions

關鍵設計（§8.2 point-in-time）：
  known_at = 實際處理時刻 UTC ISO（非 filing_date）
  回測只使用 known_at < 模擬日期 的事件，確保前向一致性

§6.8 版權：公告 text 欄位在 LLM 處理後不落庫

§8.3 LLM 配額監控：
  DAILY_LLM_LIMIT = 500（保守上限）
  超過 → 本輪剩餘申報使用規則引擎（順延次日精神，§8.3）

分批持久化設計：
  每批 TICKER_BATCH 檔走完整鏈後立即落庫（events 先、accessions 後）。
  中斷後下輪從 processed_accessions 斷點續跑，不丟已完成批。

環境變數：
  SUPABASE_URL / SUPABASE_SERVICE_KEY — 無憑證時 fallback 本地檔
  GEMINI_API_KEY                      — Gemini Flash 免費層
  NVIDIA_NIM_API_KEY                  — NVIDIA NIM 備援
  EDGAR_USER_AGENT                    — SEC User-Agent
  DUAL_POOL_DATA_DIR                  — 本地資料根目錄（預設 data/dual_pool）
  DUAL_POOL_BACKFILL_DAYS             — 首次回補天數（預設 90；Render 可臨時調小）
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from data_pipeline.dual_pool import storage
from data_pipeline.dual_pool.edgar_fetch import (
    fetch_watchpool_filings,
    get_fetch_degraded_count,
    reset_fetch_degraded_count,
)
# load_processed_accessions / add_processed_accessions 已移至 storage
# （edgar_processed 表 → Supabase 跨部署持久；無憑證 fallback 本地 JSON）
from data_pipeline.dual_pool.rule_filter import filter_filings
from data_pipeline.dual_pool.llm_extract import extract_events

# ── 常數 ──────────────────────────────────────────────────────────────
DAILY_LLM_LIMIT = 500  # LLM 每日配額保守上限（§8.3；超過 → 規則引擎接手）
TICKER_BATCH    = 20   # 每批 ticker 數（分批落庫用）
BACKFILL_DAYS   = int(os.getenv("DUAL_POOL_BACKFILL_DAYS", "90"))  # 首次回補天數

# ── 回補完成旗標（確保中斷續跑不被誤切成 incremental）─────────────────
# 存為 edgar_processed 的哨兵列而非本地檔：Render 檔案系統每次部署歸零，
# 本地 flag 會讓每次部署誤觸發全量回補。哨兵走 storage 的雙路徑
# （Supabase 表 / 本地 JSON fallback），跨部署持久。
_BACKFILL_SENTINEL = "__BACKFILL_COMPLETE__"


def _backfill_done(processed_accessions: set) -> bool:
    """哨兵在已處理集合中 → 全量回補曾完整跑過，之後都用增量。"""
    return _BACKFILL_SENTINEL in processed_accessions


def _mark_backfill_done():
    """在全量回補首次完整完成（partial=False）後寫入哨兵列。"""
    storage.add_processed_accessions({_BACKFILL_SENTINEL})


def run_stage2(
    max_runtime_s: int = 0,
    progress_dict: Optional[dict] = None,
) -> dict:
    """
    主入口：L2 EDGAR 抓取 + 規則過濾 + LLM/規則抽取 + 落庫。

    max_runtime_s: 0=無限；>0=軟時限（秒）。超時停止開新批，已完成批已落庫，
                   status 標 partial=True + 訊息說明剩餘批數。下輪觸發自動從斷點續跑。
    progress_dict: 可選共享 dict，每批更新 {"batch": i, "total_batches": n,
                   "events_so_far": m}。admin status endpoint 可輪詢進度。
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
        return {"tickers": 0, "filings_fetched": 0, "events_upserted": 0, "partial": False}

    print(f"[stage2] watchpool active ticker 數：{len(active_tickers)}")

    # ── 2. 載入已處理 accession（冪等用）────────────────────────────
    # 從 Supabase edgar_processed 表讀取（Render 跨部署持久）；無憑證 fallback 本地 JSON
    processed_accessions = storage.load_processed_accessions()
    print(f"[stage2] 已處理 accession 數：{len(processed_accessions)}")

    # ── 3. 決定回補天數（一次決定，所有批統一使用）──────────────────
    # 回補旗標存在（曾完整跑過一輪）→ 增量 2 天；否則 BACKFILL_DAYS 天。
    # 注意：用旗標而非 processed_accessions 是否為空，是為了讓中斷後的續跑
    # 仍對未處理批使用 backfill 視窗，不因已落庫批的 accession 存在而誤切成增量。
    backfill_days = 2 if _backfill_done(processed_accessions) else BACKFILL_DAYS
    print(
        f"[stage2] 回補模式={'backfill' if backfill_days >= 30 else 'incremental'} "
        f"days={backfill_days}"
    )

    # ── 4. 切批 ───────────────────────────────────────────────────────
    batches = [
        active_tickers[i: i + TICKER_BATCH]
        for i in range(0, len(active_tickers), TICKER_BATCH)
    ]
    total_batches = len(batches)
    print(f"[stage2] 共 {total_batches} 批（每批 ≤{TICKER_BATCH} 檔）")

    # ── 5. 分批走完整鏈 + 立即落庫 ────────────────────────────────────
    reset_fetch_degraded_count()
    daily_llm_count = [0]   # mutable ref 跨批沿用，§8.3 LLM 配額計數
    quota_warned    = False  # 配額警告只印一次
    total_filings_fetched  = 0
    total_filings_filtered = 0
    total_events           = 0
    partial                = False
    batches_done           = 0

    for batch_idx, batch_tickers in enumerate(batches):
        # ── 軟時限檢查（超時停止開新批）────────────────────────────
        if max_runtime_s > 0:
            elapsed_now = (datetime.now(timezone.utc) - run_start).total_seconds()
            if elapsed_now >= max_runtime_s:
                remaining = total_batches - batch_idx
                print(
                    f"[stage2] ⏱ 達時限 {max_runtime_s}s，停止開新批；"
                    f"剩餘 {remaining} 批，下輪續跑"
                )
                partial = True
                break

        # ── 5a. 抓取（此批 ticker）──────────────────────────────────
        batch_filings = fetch_watchpool_filings(
            tickers=batch_tickers,
            processed_accessions=processed_accessions,
            backfill_days=backfill_days,
        )
        total_filings_fetched += len(batch_filings)

        # ── 5b. 規則過濾 ─────────────────────────────────────────────
        filtered_filings = filter_filings(batch_filings)
        total_filings_filtered += len(filtered_filings)

        # 此批所有抓到的 accession（含過濾掉的）—— 避免下輪重抓噪音申報
        batch_accessions = {f["accession_no"] for f in batch_filings}
        # 更新記憶體集合，讓後續批的 fetch 看到（本輪內去重）
        processed_accessions.update(batch_accessions)

        # ── 5c. LLM/規則抽取事件 ─────────────────────────────────────
        # known_at = 此批實際處理時刻 UTC（§8.2 point-in-time）
        known_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        batch_events: list[dict] = []

        for filing in filtered_filings:
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
            for ev in events:
                ev["known_at"] = known_at
                ev.pop("text", None)  # 不落庫（§6.8 版權）
            batch_events.extend(events)

        # ── 5d. 立即落庫（events 先，accessions 後）─────────────────
        # 順序保證：被殺時最多重抓此批，不會丟已落庫事件
        if batch_events:
            storage.upsert_events(batch_events)
        elif batch_filings and not filtered_filings:
            pass  # 全被過濾掉，正常
        elif batch_filings and filtered_filings:
            print(
                f"[stage2] ⚠ batch {batch_idx+1}: "
                f"{len(filtered_filings)} 份申報但 0 事件——檢查抽取鏈"
            )

        storage.add_processed_accessions(batch_accessions)

        total_events += len(batch_events)
        batches_done += 1

        elapsed_batch = (datetime.now(timezone.utc) - run_start).total_seconds()
        print(
            f"[stage2] batch {batch_idx+1}/{total_batches} done — "
            f"filings={len(batch_filings)} events={len(batch_events)} "
            f"elapsed={elapsed_batch:.0f}s"
        )

        # ── 活進度更新（admin status endpoint 輪詢用）────────────────
        if progress_dict is not None:
            progress_dict.update({
                "batch":         batch_idx + 1,
                "total_batches": total_batches,
                "events_so_far": total_events,
            })

    # ── 6. 收尾統計 ────────────────────────────────────────────────────
    elapsed = (datetime.now(timezone.utc) - run_start).total_seconds()

    if total_filings_fetched == 0:
        print("[stage2] 無新申報（正常）")

    fetch_degraded = get_fetch_degraded_count()
    print(
        f"[stage2] === {'部分完成' if partial else '完成'} elapsed={elapsed:.0f}s "
        f"events={total_events} llm_calls={daily_llm_count[0]} ==="
    )
    if fetch_degraded:
        print(f"[stage2] fetch_degraded={fetch_degraded}（EX-99 PR 補取失敗，已降級主文）")

    # ── 寫回補旗標（首次完整完成時；之後續跑永遠增量）──────────────
    if not partial and not _backfill_done(processed_accessions):
        _mark_backfill_done()
        print("[stage2] backfill_complete 哨兵已寫入，後續改用增量模式")

    result: dict = {
        "tickers":          len(active_tickers),
        "batches_done":     batches_done,
        "total_batches":    total_batches,
        "filings_fetched":  total_filings_fetched,
        "filings_filtered": total_filings_filtered,
        "events_upserted":  total_events,
        "llm_calls":        daily_llm_count[0],
        "fetch_degraded":   fetch_degraded,
        "elapsed_s":        round(elapsed, 1),
        "partial":          partial,
    }
    if partial:
        remaining = total_batches - batches_done
        result["message"] = f"還剩 {remaining} 批，下輪續跑"

    return result


if __name__ == "__main__":
    result = run_stage2()
    print("\n[stage2] 結果摘要:")
    for k, v in result.items():
        print(f"  {k}: {v}")
