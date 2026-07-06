"""
run_stage3.py — 階段 3 Orchestrator

執行順序：
  讀 watchpool(active) + events(近 365 天)
  → 逐檔算分（scoring.py）
  → upsert scores（PK ticker+score_date，冪等）
  → 告警：total 較前一日跳升 >15 → print ⚠ + Discord

批次策略（照 run_stage1 風格）：
  - yfinance 呼叫（op_leverage + cash_runway）分批，失敗不中斷整批
  - stage2 逾時 partial 也照跑——用已有的 events 算（§A workflow 附注）

環境變數：
  SUPABASE_URL / SUPABASE_SERVICE_KEY — 無憑證時 fallback 本地檔
  DISCORD_WEBHOOK_URL                 — 有則推送告警（沿用現有習慣）
  DUAL_POOL_DATA_DIR                  — 本地資料根目錄（預設 data/dual_pool）
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Optional

from data_pipeline.dual_pool import storage
from data_pipeline.dual_pool.scoring import (
    WEIGHTS,
    compute_insider_ratio,
    factor_insider,
    factor_narrative,
    factor_catalyst,
    factor_institution,
    factor_op_leverage,
    factor_partnership,
    compute_veto,
    compute_gate,
    _build_sector_rs_map,
    _load_sector_cache,
    _save_sector_cache,
    score_ticker,
)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
JUMP_THRESHOLD = 15.0  # §7.1 告警門檻

_DATA_DIR = Path(os.getenv("DUAL_POOL_DATA_DIR", "data/dual_pool"))


# ── 工具：Discord 推送（沿用現有 webhook 慣例）────────────────────────────

def _discord_post(message: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        import httpx
        httpx.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message},
            timeout=6,
        )
    except Exception as e:
        print(f"[stage3] Discord 推送失敗: {e}")


# ── 載入前一日 scores 做告警比對 ─────────────────────────────────────────

def _load_prev_scores() -> dict[str, float]:
    """回傳 {ticker: total} 的前一日快照（用最近已有的非今日 score_date）。"""
    today = date.today().isoformat()
    try:
        sb = storage._supabase()
        if sb:
            resp = (
                sb.table("scores")
                .select("score_date")
                .lt("score_date", today)
                .order("score_date", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                prev_date = resp.data[0]["score_date"]
                rows = (
                    sb.table("scores")
                    .select("ticker,total")
                    .eq("score_date", prev_date)
                    .execute()
                )
                return {r["ticker"]: r["total"] for r in (rows.data or [])}
    except Exception:
        pass

    # fallback：本地 scores.jsonl
    scores_file = _DATA_DIR / "scores.jsonl"
    if not scores_file.exists():
        return {}
    try:
        all_rows: list[dict] = []
        with scores_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if r.get("score_date", "") < today:
                        all_rows.append(r)
                except Exception:
                    pass
        if not all_rows:
            return {}
        latest = max(r.get("score_date", "") for r in all_rows)
        return {r["ticker"]: r["total"] for r in all_rows if r.get("score_date") == latest}
    except Exception:
        return {}


# ── 主流程 ────────────────────────────────────────────────────────────────

def run() -> None:
    today = date.today()
    print(f"[stage3] 開始 — score_date={today}", flush=True)

    # 1. 載入 watchpool (active)
    watchpool = storage.load_watchpool()
    active = [w for w in watchpool if w.get("status") == "active"]
    if not active:
        print("[stage3] watchpool 無 active 記錄，跳過", flush=True)
        return
    print(f"[stage3] watchpool active: {len(active)} 檔", flush=True)

    # 2. 載入近 365 天 events
    events_all = storage.load_events(days=365)
    print(f"[stage3] events loaded: {len(events_all)} 筆", flush=True)

    # 依 ticker 分組
    events_by_ticker: dict[str, list[dict]] = {}
    for e in events_all:
        t = e.get("ticker") or ""
        events_by_ticker.setdefault(t, []).append(e)

    # 3. 建共用資源
    sector_cache = _load_sector_cache()
    rs_map = _build_sector_rs_map()
    if not rs_map:
        print("[stage3] rs_map 空（signals.json 不存在或無資料），narrative 因子將回中性", flush=True)

    # 4. 第一輪：計算 insider ratio（需要 pool 層級 percentile）
    #    分左右池分別建 pool_insider_ratios
    left_tickers  = [w["ticker"] for w in active if w.get("side") == "left"]
    right_tickers = [w["ticker"] for w in active if w.get("side") == "right"]

    ticker_to_wp = {w["ticker"]: w for w in active}

    def _get_insider_ratios(tickers: list[str]) -> dict[str, Optional[float]]:
        ratios: dict[str, Optional[float]] = {}
        for t in tickers:
            evts = events_by_ticker.get(t, [])
            mc = ticker_to_wp.get(t, {}).get("market_cap") or 0.0
            ratios[t] = compute_insider_ratio(evts, mc)
        return ratios

    left_ratios_map  = _get_insider_ratios(left_tickers)
    right_ratios_map = _get_insider_ratios(right_tickers)

    left_pool_ratios  = [v for v in left_ratios_map.values()  if v is not None]
    right_pool_ratios = [v for v in right_ratios_map.values() if v is not None]

    # 5. 逐檔計分
    prev_scores = _load_prev_scores()
    results: list[dict] = []
    data_gap_counts: dict[str, int] = {}
    jump_alerts: list[str] = []

    for wp in active:
        ticker = wp["ticker"]
        side   = wp.get("side", "left")
        evts   = events_by_ticker.get(ticker, [])
        mc     = wp.get("market_cap") or 0.0
        adv    = wp.get("adv_dollar")

        pool_ratios = left_pool_ratios if side == "left" else right_pool_ratios

        try:
            result = score_ticker(
                ticker=ticker,
                side=side,
                events=evts,
                adv_dollar=adv,
                market_cap=mc,
                pool_insider_ratios=pool_ratios,
                sector_cache=sector_cache,
                rs_map=rs_map,
                score_date=today,
            )
        except Exception as e:
            print(f"[stage3] ⚠ {ticker} 計分失敗: {e}", flush=True)
            traceback.print_exc()
            continue

        results.append(result)

        # 統計 data_gaps
        for gap in result.get("data_gaps", []):
            data_gap_counts[gap] = data_gap_counts.get(gap, 0) + 1

        # 告警：total 較前一日跳升 >15（§7.1）
        prev_total = prev_scores.get(ticker)
        if prev_total is not None:
            jump = result["total"] - prev_total
            if jump > JUMP_THRESHOLD:
                msg = f"⚠ [stage3] {ticker} total 跳升 {jump:.1f}（{prev_total:.1f}→{result['total']:.1f}）"
                print(msg, flush=True)
                jump_alerts.append(msg)

    # 6. 儲存 sector_cache（本輪 narrative 可能新增項目）
    _save_sector_cache(sector_cache)

    # 7. Upsert scores
    if results:
        storage.upsert_scores(results)
        print(f"[stage3] upserted {len(results)} scores", flush=True)
    else:
        print("[stage3] 無 scores 產出", flush=True)

    # 8. 告警推送 Discord
    if jump_alerts and DISCORD_WEBHOOK_URL:
        header = f"📈 **L3 大跳升告警** — score_date={today}\n"
        body = "\n".join(jump_alerts[:10])
        _discord_post(header + body)

    # 9. 輸出統計
    print(f"\n[stage3] 完成。scores={len(results)} 檔", flush=True)
    print("[stage3] data_gap 統計：", flush=True)
    for gap, cnt in sorted(data_gap_counts.items()):
        print(f"  {gap}: {cnt} 檔", flush=True)


if __name__ == "__main__":
    run()
