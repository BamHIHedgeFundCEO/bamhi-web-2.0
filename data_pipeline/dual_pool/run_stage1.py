"""
run_stage1.py — 階段 1 Orchestrator

執行順序：
  L0 yfscreen 粗篩 → L1 形態識別（含遲滯）→ watchpool 落庫 + universe_snapshot 落庫

§4.3 批次策略全部實作：
  - OHLCV 增量 cache（data/dual_pool/ohlcv/*.parquet）
    選擇理由：parquet 比 CSV 讀寫快 3-5x，磁碟佔用小 ~60%，適合日線大量 ticker；
    缺點是需要 pyarrow/fastparquet，若環境不支援自動 fallback 至 CSV。
  - 每批 ≤200 檔（BATCH_SIZE）
  - yfinance 失敗重試上限 2 次，仍失敗 → 記入 data_gap 清單跳過
  - 單檔失敗不中斷整批
  - 總時限 90 分鐘，超時 → 降級：只處理「昨日已在池 + 今日 L0 新出現」的檔案
  - 冷啟動標記 warming_up（全量 cache 還在建立中）

環境變數：
  SUPABASE_URL / SUPABASE_SERVICE_KEY — 無憑證時 fallback 本地檔
  DUAL_POOL_DATA_DIR                  — 本地資料根目錄（預設 data/dual_pool）
  DUAL_POOL_ENABLE_CAGR_GATE          — '1' 啟用右池 CAGR 閘門（預設關閉）
"""

from __future__ import annotations

import json
import os
import time
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)

from data_pipeline.dual_pool.l0_screen  import run_l0
from data_pipeline.dual_pool.l1_features import process_ticker
from data_pipeline.dual_pool.hysteresis  import (
    should_retain, is_cooled_down, trading_days_between,
)
from data_pipeline.dual_pool import storage

# ── 常數 ──────────────────────────────────────────────────────────────
BATCH_SIZE      = 200          # 每批最多 ticker 數
MAX_RETRIES     = 2            # yfinance 單檔重試上限
HIST_PERIOD     = "400d"       # 全量 ticker 拉取期間
INCREMENTAL_DAYS = 7           # 增量更新：只拉最新 N 日
TOTAL_TIMEOUT_S  = 90 * 60    # 總時限 90 分鐘
ADV_MIN         = 2_000_000    # 流動性底線 $2M
MARKET          = "US"

_DATA_DIR    = Path(os.getenv("DUAL_POOL_DATA_DIR", "data/dual_pool"))
_OHLCV_DIR   = _DATA_DIR / "ohlcv"
_GAP_FILE    = _DATA_DIR / "data_gap.json"
_STATUS_FILE = _DATA_DIR / "run_status.json"
_PARQUET_SUPPORT = True  # 初始假設支援，run_stage1 啟動時確認


def _check_parquet():
    global _PARQUET_SUPPORT
    try:
        import pyarrow  # noqa
        _PARQUET_SUPPORT = True
    except ImportError:
        try:
            import fastparquet  # noqa
            _PARQUET_SUPPORT = True
        except ImportError:
            _PARQUET_SUPPORT = False
            print("[stage1] pyarrow/fastparquet 不可用，OHLCV cache 改用 CSV")


def _ohlcv_path(ticker: str) -> Path:
    ext = "parquet" if _PARQUET_SUPPORT else "csv"
    return _OHLCV_DIR / f"{ticker}.{ext}"


def _load_cached_ohlcv(ticker: str) -> Optional[pd.DataFrame]:
    p = _ohlcv_path(ticker)
    if not p.exists():
        return None
    try:
        if _PARQUET_SUPPORT and p.suffix == ".parquet":
            df = pd.read_parquet(p)
        else:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index, utc=True)
        # 修復前存的 cache 帶 MultiIndex 欄位，與現在的扁平 new_data concat 會炸
        # （union MultiIndex with Index）。讀回時攤平，兼容舊 cache。
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"[stage1] cache load error {ticker}: {e}")
        return None


def _save_ohlcv_cache(ticker: str, df: pd.DataFrame):
    _OHLCV_DIR.mkdir(parents=True, exist_ok=True)
    p = _ohlcv_path(ticker)
    try:
        if _PARQUET_SUPPORT and p.suffix == ".parquet":
            df.to_parquet(p)
        else:
            df.to_csv(p)
    except Exception as e:
        print(f"[stage1] cache save error {ticker}: {e}")


def _fetch_ohlcv(ticker: str, full: bool = True) -> Optional[pd.DataFrame]:
    """
    拉 yfinance 歷史 OHLCV。
    full=True  → 拉 HIST_PERIOD（新 ticker 或 cache 缺失）
    full=False → 拉近 INCREMENTAL_DAYS 補洞
    """
    period  = HIST_PERIOD if full else f"{INCREMENTAL_DAYS}d"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = yf.download(
                ticker, period=period,
                auto_adjust=True, progress=False,
                threads=False,
            )
            if df is not None and not df.empty:
                # yfinance 1.2+ 單檔下載回 MultiIndex 欄位 ('Close','AAPL')，
                # 使 hist["Close"] 變 DataFrame，下游 float(Series) 在新版 pandas
                # 直接 TypeError。攤平成單層欄位，讓 hist["Close"] 為 Series。
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
        except Exception as e:
            print(f"[stage1] yfinance {ticker} attempt {attempt}: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(2)
    return None


def _get_ohlcv_with_cache(ticker: str) -> Optional[pd.DataFrame]:
    """
    增量 cache 策略（§4.3）：
      有 cache → 拉增量補洞，合併後覆寫 cache
      無 cache → 全量拉，寫 cache
    """
    cached = _load_cached_ohlcv(ticker)
    if cached is not None and not cached.empty:
        # 增量：只拉最新 N 日
        new_data = _fetch_ohlcv(ticker, full=False)
        if new_data is not None and not new_data.empty:
            combined = pd.concat([cached, new_data])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        else:
            combined = cached
        _save_ohlcv_cache(ticker, combined)
        return combined
    else:
        # 全量
        df = _fetch_ohlcv(ticker, full=True)
        if df is not None:
            _save_ohlcv_cache(ticker, df)
        return df


def _load_data_gaps() -> set:
    if _GAP_FILE.exists():
        try:
            return set(json.loads(_GAP_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def _save_data_gaps(gaps: set):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _GAP_FILE.write_text(json.dumps(sorted(gaps), ensure_ascii=False), encoding="utf-8")


def _load_run_status() -> dict:
    if _STATUS_FILE.exists():
        try:
            return json.loads(_STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"warming_up": True, "cached_tickers": []}


def _save_run_status(status: dict):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, default=str), encoding="utf-8")


def run_stage1(enable_cagr_gate: bool = False):
    """
    主入口：執行 L0 粗篩 + L1 形態識別 + 遲滯 + 落庫。
    """
    _check_parquet()
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _OHLCV_DIR.mkdir(parents=True, exist_ok=True)

    run_date    = date.today()
    start_time  = time.time()
    enable_cagr = enable_cagr_gate or os.getenv("DUAL_POOL_ENABLE_CAGR_GATE") == "1"

    print(f"[stage1] === 開始 run_date={run_date} ===")

    # ── 載入現有 watchpool（遲滯 + 冷卻用）───────────────────────────
    # 冷卻持久化採「watchpool 軟刪除」：移出時不刪列，改標 status='cooldown' +
    # removed_at=移出日。取捨：單一持久化路徑同時覆蓋 Supabase 與 JSON fallback、
    # 不需第三張表（守住階段 1 只建兩張表）；代價是 watchpool 含非成員列，
    # 讀取端須過濾 status='active'。
    all_rows = storage.load_watchpool()
    existing_pool: dict[str, dict] = {
        r["ticker"]: r for r in all_rows if r.get("status", "active") == "active"
    }
    cooldown_map: dict[str, dict] = {
        r["ticker"]: r for r in all_rows if r.get("status") == "cooldown"
    }
    print(f"[stage1] 現有 watchpool: active={len(existing_pool)}, cooldown={len(cooldown_map)}")

    # ── 載入 run 狀態（warming_up / cached_tickers）─────────────────
    status = _load_run_status()
    warming_up    = status.get("warming_up", True)
    cached_set    = set(status.get("cached_tickers", []))
    data_gaps     = _load_data_gaps()

    # ── L0 粗篩 ───────────────────────────────────────────────────────
    print("[stage1] === L0 粗篩 ===")
    l0_result   = run_l0()
    universe    = l0_result["universe"]
    market_caps = l0_result.get("market_caps", {})  # {ticker: 市值}（screener marketCap.raw）
    print(f"[stage1] L0 universe = {len(universe)} 檔（screener 市值覆蓋 {len(market_caps)} 檔）")

    # ── 超時降級：若已接近時限，縮小處理範圍 ─────────────────────────
    def _elapsed() -> float:
        return time.time() - start_time

    def _should_degrade() -> bool:
        return _elapsed() > TOTAL_TIMEOUT_S

    # 降級時只處理優先 ticker（已在池 + 今日 L0 新出現）
    pool_tickers    = set(existing_pool.keys())
    l0_universe_set = set(universe)
    priority_set    = pool_tickers | l0_universe_set  # 都需要處理

    # ── L1 特徵計算（分批）────────────────────────────────────────────
    print("[stage1] === L1 特徵計算 ===")

    to_process = [t for t in universe if t not in data_gaps]
    if _should_degrade():
        # 超時降級：只處理優先 ticker
        to_process = [t for t in to_process if t in priority_set]
        print(f"[stage1] 超時降級 → 僅處理 {len(to_process)} 優先 ticker")

    results: list[dict] = []
    n_batches = (len(to_process) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(n_batches):
        if _should_degrade() and batch_idx > 0:
            print(f"[stage1] 超時，第 {batch_idx}/{n_batches} 批後停止")
            break

        batch = to_process[batch_idx * BATCH_SIZE: (batch_idx + 1) * BATCH_SIZE]
        print(f"[stage1] batch {batch_idx+1}/{n_batches} ({len(batch)} 檔)...")

        for ticker in batch:
            try:
                hist = _get_ohlcv_with_cache(ticker)
                if hist is None:
                    print(f"[stage1] data_gap: {ticker}")
                    data_gaps.add(ticker)
                    continue

                result = process_ticker(
                    ticker, hist,
                    info=None,  # 省略 .info（慢）；市值走 _resolve_market_cap
                    enable_cagr_gate=enable_cagr,
                )
                # 市值回填：優先 L0 screener，缺值用 yfinance fast_info 補
                result["market_cap"] = _resolve_market_cap(ticker, market_caps)
                results.append(result)
                cached_set.add(ticker)

            except Exception as e:
                print(f"[stage1] 處理錯誤 {ticker}: {e}")
                continue

        time.sleep(0.5)  # 批間 sleep

    _save_data_gaps(data_gaps)
    print(f"[stage1] L1 處理完成 {len(results)} 檔，data_gap {len(data_gaps)} 檔")

    # ── 整理 L1 結果 ──────────────────────────────────────────────────
    left_new  = [r for r in results if r["side"] == "left"]
    right_new = [r for r in results if r["side"] == "right"]
    print(f"[stage1] L1 left={len(left_new)}, right={len(right_new)}, "
          f"discard={sum(1 for r in results if r['side']=='discard')}")

    # ── 遲滯邏輯（§5.6）──────────────────────────────────────────────
    now_str      = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    to_upsert:   list[dict] = []
    cooldown_marked: list[str] = []  # 本輪移出（軟刪除 → status='cooldown'）

    result_map = {r["ticker"]: r for r in results}

    # 1) 處理今日 L0 universe 中已計算特徵的 ticker
    for r in results:
        ticker   = r["ticker"]
        side_new = r["side"]
        features = r.get("features") or {}
        mcap     = r.get("market_cap")

        adv_dollar = features.get("adv_dollar", 0.0)

        if ticker in existing_pool:
            # 已在池 → 遲滯判斷
            existing = existing_pool[ticker]
            entered_at = date.fromisoformat(existing["entered_at"]) \
                         if isinstance(existing.get("entered_at"), str) \
                         else existing.get("entered_at", run_date)

            # 連續低流動性 rolling counter：<$2M 加一、≥$2M 歸零（讀昨日 watchpool 值累計）
            old_streak = int(existing.get("low_adv_streak") or 0)
            new_streak = old_streak + 1 if adv_dollar < ADV_MIN else 0

            decision = should_retain(
                ticker=ticker,
                entered_at=entered_at,
                today=run_date,
                new_side=side_new,
                current_side=existing["side"],
                adv_dollar=adv_dollar,
                low_adv_streak=new_streak,
            )

            if decision["action"] == "remove":
                # 軟刪除：標 cooldown + removed_at，供跨 run 冷卻檢查（§5.6）
                to_upsert.append(_to_cooldown(existing, run_date, now_str))
                cooldown_marked.append(ticker)
                print(f"[stage1] remove→cooldown {ticker}: {decision['reason']}")
            elif decision["action"] == "graduate":
                # 畢業：左→右，以新 side 更新（entered_at 重置、streak 沿用）
                to_upsert.append(_build_record(
                    ticker, "right", features, run_date, now_str,
                    market_cap=mcap, low_adv_streak=new_streak,
                ))
                print(f"[stage1] graduate {ticker}: left→right")
            else:
                # retain：更新特徵但保持 entered_at 不變
                to_upsert.append(_build_record(
                    ticker, existing["side"], features, entered_at, now_str,
                    liquidity_ok=decision["liquidity_ok"],
                    market_cap=mcap, low_adv_streak=new_streak,
                ))
        else:
            # 新進 / 重進 ticker（進池條件已含 adv≥$2M，streak 起始 0）
            if side_new in ("left", "right"):
                # 冷卻閘門（§5.6）：移出後 5 個交易日內不得重進
                # right→left 重分類也走此路徑：移出→冷卻→期滿仍判左才進左池
                cd = cooldown_map.get(ticker)
                if cd is not None:
                    removed_at = _parse_date(cd.get("removed_at"), run_date)
                    if not is_cooled_down(removed_at, run_date):
                        print(f"[stage1] cooldown blocked {ticker} "
                              f"(removed_at={removed_at}, side_new={side_new})")
                        continue
                to_upsert.append(_build_record(
                    ticker, side_new, features, run_date, now_str,
                    market_cap=mcap, low_adv_streak=0,
                ))

    # 2) 處理「已在池但今日 L0 未出現/未計算」的 ticker（可能 L0 掉出 universe）
    for ticker in list(existing_pool.keys()):
        if ticker not in result_map:
            # 今日 L0 沒有此 ticker，視為條件可能失守
            existing = existing_pool[ticker]
            entered_at = date.fromisoformat(existing["entered_at"]) \
                         if isinstance(existing.get("entered_at"), str) \
                         else existing.get("entered_at", run_date)
            held_days = trading_days_between(entered_at, run_date)
            if held_days < 10:
                # 保留期內：沿用舊資料（setdefault 補齊新欄位，避免混合 key set upsert 失敗）
                retained = {**existing, "updated_at": now_str}
                retained.setdefault("status", "active")
                retained.setdefault("removed_at", None)
                retained.setdefault("low_adv_streak", 0)
                to_upsert.append(retained)
            else:
                to_upsert.append(_to_cooldown(existing, run_date, now_str))
                cooldown_marked.append(ticker)
                print(f"[stage1] remove→cooldown {ticker}: dropped_from_l0")

    # 3) 冷卻期滿且今日未重進 → 清除軟刪除列（冷卻已無約束力）
    entered_today = {rec["ticker"] for rec in to_upsert
                     if rec.get("status", "active") == "active"}
    expired = [
        t for t, row in cooldown_map.items()
        if t not in entered_today
        and is_cooled_down(_parse_date(row.get("removed_at"), run_date), run_date)
    ]
    if expired:
        storage.remove_from_watchpool(expired)
        print(f"[stage1] 清除冷卻期滿列: {len(expired)} 檔")

    # ── 落庫 ─────────────────────────────────────────────────────────
    if to_upsert:
        storage.upsert_watchpool(to_upsert)

    # ── universe_snapshot（§3.5）─────────────────────────────────────
    snap_records = []
    for r in results:
        f = r.get("features") or {}
        if not f:
            continue
        snap_records.append({
            "snapshot_date": run_date.isoformat(),
            "ticker":        r["ticker"],
            "market_cap":    r.get("market_cap"),
            "adv_dollar":    f.get("adv_dollar"),
            "close":         f.get("price"),
        })
    storage.save_universe_snapshot(run_date, snap_records)

    # ── 更新 run_status ───────────────────────────────────────────────
    # warming_up 結束條件：全量 ticker 都已 cache
    new_warming = len(l0_universe_set - cached_set) > 100
    _save_run_status({
        "warming_up":     new_warming,
        "cached_tickers": sorted(cached_set),
        "last_run":       now_str,
        "universe_size":  len(universe),
        "watchpool_add":  len(to_upsert),
        "watchpool_cooldown": len(cooldown_marked),
        "data_gap_count": len(data_gaps),
        "elapsed_s":      round(_elapsed(), 1),
    })

    elapsed = _elapsed()
    print(f"[stage1] === 完成 elapsed={elapsed:.0f}s warming_up={new_warming} ===")
    print(f"[stage1] watchpool upsert {len(to_upsert)} / cooldown {len(cooldown_marked)}, "
          f"snapshot {len(snap_records)} 列")

    return {
        "run_date":       run_date.isoformat(),
        "universe":       len(universe),
        "left":           len(left_new),
        "right":          len(right_new),
        "watchpool_add":  len(to_upsert),
        "watchpool_cooldown": len(cooldown_marked),
        "snapshot_rows":  len(snap_records),
        "warming_up":     new_warming,
        "elapsed_s":      round(elapsed, 1),
    }


def _parse_date(v, default: date) -> date:
    """ISO 字串 / date → date；解析失敗回 default。"""
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            pass
    return default


def _to_cooldown(existing: dict, removed_at: date, updated_at: str) -> dict:
    """
    移出 → 軟刪除（§5.6 冷卻持久化）：
    保留原列、標 status='cooldown' + removed_at=移出日，跨 run 供 is_cooled_down 檢查。
    冷卻期滿且未重進時由 run_stage1 步驟 3 清列。
    """
    rec = {k: v for k, v in existing.items() if k not in ("id", "created_at")}
    rec.setdefault("low_adv_streak", 0)
    rec["status"]     = "cooldown"
    rec["removed_at"] = removed_at.isoformat()
    rec["updated_at"] = updated_at
    return rec


def _resolve_market_cap(ticker: str, market_caps: dict) -> Optional[float]:
    """
    市值來源優先序：
      1. L0 screener 回傳的 marketCap.raw（零成本）
      2. yfinance fast_info.market_cap（已在拉 OHLCV，成本近零）
      3. 仍拿不到 → None
    """
    mc = market_caps.get(ticker)
    if mc:
        return float(mc)
    try:
        fi = yf.Ticker(ticker).fast_info
        mc = getattr(fi, "market_cap", None)
        if mc:
            return float(mc)
    except Exception:
        pass
    return None


def _build_record(
    ticker: str,
    side: str,
    features: dict,
    entered_at,
    updated_at: str,
    liquidity_ok: Optional[bool] = None,
    market_cap: Optional[float] = None,
    low_adv_streak: int = 0,
) -> dict:
    if liquidity_ok is None:
        liquidity_ok = features.get("adv_dollar", 0) >= ADV_MIN
    return {
        "ticker":         ticker,
        "side":           side,
        "market":         MARKET,
        "market_cap":     market_cap,  # L0 screener → fast_info fallback（_resolve_market_cap）
        "entangle":       features.get("entangle"),
        "slope200":       features.get("slope200"),
        "dist_low":       features.get("dist_low"),
        "adv_dollar":     features.get("adv_dollar"),
        "liquidity_ok":   liquidity_ok,
        "low_adv_streak": low_adv_streak,  # 連續 adv<$2M 交易日數（遲滯 §5.6 rolling counter）
        "status":         "active",        # 'active'|'cooldown'（軟刪除，§5.6 冷卻）
        "removed_at":     None,            # 移出日；status='cooldown' 時有值
        "entered_at":     entered_at.isoformat() if hasattr(entered_at, "isoformat") else str(entered_at),
        "updated_at":     updated_at,
    }


if __name__ == "__main__":
    import sys
    enable_cagr = "--cagr" in sys.argv
    result = run_stage1(enable_cagr_gate=enable_cagr)
    print("\n[stage1] 結果摘要:")
    for k, v in result.items():
        print(f"  {k}: {v}")
