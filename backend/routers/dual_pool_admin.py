"""
dual_pool_admin.py — Render 端背景任務觸發（§6.1 stage2 / §6.9 13F / §7.6 verify）

共同規範：
  驗 X-Trigger-Token header 對 env DUAL_POOL_TRIGGER_TOKEN（同一個 token）
  env 未設  → 503 / token 錯  → 401 / 已在跑  → 409 / 成功  → 202

端點清單：
  POST /api/dual-pool/run-stage2       — L2 EDGAR 抓取
  GET  /api/dual-pool/stage2-status

  POST /api/dual-pool/run-13f          — 13F 機構持倉季度 job（§6.9）
  GET  /api/dual-pool/13f-status

  POST /api/dual-pool/run-verify-track-record — track_record 每週驗證（§7.6）
  GET  /api/dual-pool/verify-status

所有 job 都用相同 token 保護（DUAL_POOL_TRIGGER_TOKEN），
各自維護獨立的 in-memory 執行狀態。
13F 額外在 Supabase dual_pool_job_state 持久化狀態 + 每 5 分鐘心跳，
讓 Render 重啟後 poll 仍能讀到正確狀態（或偵測 process 已死）。

13F body 可選參數（JSON）：
  quarter: str — 如 '2025-Q1'；不傳 → 自動推算上一個完整季度
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request
from typing import Any

router = APIRouter(prefix="/api/dual-pool", tags=["dual_pool_admin"])

# ── in-memory 執行狀態（Render 重啟歸零）────────────────────────────
_state_lock     = threading.Lock()
_stage2_state: Optional[dict] = None
_stage2_running: bool          = False

_13f_state: Optional[dict] = None
_13f_running: bool         = False

_verify_state: Optional[dict] = None
_verify_running: bool         = False

# ── 13F heartbeat 常數 ─────────────────────────────────────────────
_HB_INTERVAL_S = 300   # 每 5 分鐘更新 Supabase heartbeat_at
_HB_STALE_S    = 900   # 超過 15 分鐘無心跳 → process 已死 → interrupted


def _check_token(request: Request) -> None:
    """驗 X-Trigger-Token；不符合直接 raise HTTPException。"""
    token_expected = os.getenv("DUAL_POOL_TRIGGER_TOKEN")
    if not token_expected:
        raise HTTPException(
            status_code=503,
            detail="DUAL_POOL_TRIGGER_TOKEN not configured on server",
        )
    token_received = request.headers.get("X-Trigger-Token")
    if token_received != token_expected:
        raise HTTPException(status_code=401, detail="Invalid trigger token")


def _run_stage2_bg(started_at: str) -> None:
    """
    BackgroundTask 實際執行 stage2 並更新 _stage2_state。
    try/except 保證例外不消失：失敗寫進 status='failed' + error 欄位（§6.1 防靜默故障）。
    Render 工作目錄是 repo 根，可直接 import data_pipeline。
    """
    global _stage2_state, _stage2_running

    # 共享進度 dict（每批更新；status endpoint 輪詢可見到有沒有前進）
    progress: dict = {}

    try:
        from data_pipeline.dual_pool.run_stage2 import run_stage2  # noqa: PLC0415

        result = run_stage2(
            max_runtime_s=5400,   # 90 分鐘軟時限；超時留斷點，下輪續跑
            progress_dict=progress,
        )

        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _state_lock:
            _stage2_state = {
                "status":      "done",
                "started_at":  started_at,
                "finished_at": finished_at,
                "result":      result,
                "progress":    progress,
                "error":       None,
            }
    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        err_msg = str(exc)
        print(f"[dual_pool_admin] stage2 background task 失敗: {err_msg}")
        with _state_lock:
            _stage2_state = {
                "status":      "failed",
                "started_at":  started_at,
                "finished_at": finished_at,
                "result":      None,
                "progress":    progress,
                "error":       err_msg,
            }
    finally:
        with _state_lock:
            _stage2_running = False


@router.post("/run-stage2", status_code=202)
async def trigger_stage2(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """觸發 stage2 背景執行（GitHub Actions 每晚呼叫）。"""
    global _stage2_running, _stage2_state
    _check_token(request)

    with _state_lock:
        if _stage2_running:
            raise HTTPException(status_code=409, detail="stage2 already running")
        _stage2_running = True
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _stage2_state = {
            "status":      "running",
            "started_at":  started_at,
            "finished_at": None,
            "result":      None,
            "progress":    {},
            "error":       None,
        }

    background_tasks.add_task(_run_stage2_bg, started_at)
    return {"started": True}


@router.get("/stage2-status")
def get_stage2_status(request: Request):
    """回最近一次 stage2 run 的狀態（需 token——狀態含 ticker/錯誤細節）。"""
    _check_token(request)
    with _state_lock:
        if _stage2_state is None:
            return {"status": "never_run"}
        return dict(_stage2_state)


# ──────────────────────────────────────────────────────────────────────────
# 13F 機構持倉季度 job（§6.9）
# ──────────────────────────────────────────────────────────────────────────

def _13f_heartbeat_worker(stop_event: threading.Event) -> None:
    """Daemon thread：每 _HB_INTERVAL_S 秒更新 Supabase heartbeat_at。
    Render 若重啟（process 死亡），心跳停止；poll 端偵測到 stale → interrupted。
    """
    while not stop_event.wait(timeout=_HB_INTERVAL_S):
        try:
            from data_pipeline.dual_pool import storage as _storage  # noqa: PLC0415
            _storage.upsert_job_state(
                "13f",
                {"heartbeat_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            )
        except Exception as e:
            print(f"[dual_pool_admin] 13F heartbeat error: {e}")


def _run_13f_bg(
    started_at: str,
    target_quarter: Optional[str],
    hb_stop: Optional[threading.Event],
) -> None:
    """BackgroundTask：執行 institution_13f.run_institution_job。"""
    global _13f_state, _13f_running
    try:
        from data_pipeline.dual_pool.institution_13f import run_institution_job  # noqa: PLC0415
        from data_pipeline.dual_pool import storage as _storage                  # noqa: PLC0415
        result = run_institution_job(target_quarter=target_quarter)
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        final_state = {
            "status":      "done",
            "started_at":  started_at,
            "finished_at": finished_at,
            "result":      result,
            "error":       None,
        }
        with _state_lock:
            _13f_state = final_state
        _storage.upsert_job_state("13f", final_state)
    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        err_msg = str(exc)
        print(f"[dual_pool_admin] 13F background task 失敗: {err_msg}")
        try:
            from data_pipeline.dual_pool import storage as _storage  # noqa: PLC0415
        except Exception:
            _storage = None  # type: ignore[assignment]
        failed_state = {
            "status":      "failed",
            "started_at":  started_at,
            "finished_at": finished_at,
            "result":      None,
            "error":       err_msg,
        }
        with _state_lock:
            _13f_state = failed_state
        if _storage:
            _storage.upsert_job_state("13f", failed_state)
    finally:
        with _state_lock:
            _13f_running = False
        if hb_stop is not None:
            hb_stop.set()


@router.post("/run-13f", status_code=202)
async def trigger_13f(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict = Body(default={}),
):
    """
    觸發 13F 機構持倉季度 job（§6.9）。
    可選 body JSON：{"quarter": "2025-Q1"}；不傳 → 自動推算上一個完整季度。
    狀態同步寫入 Supabase dual_pool_job_state；Render 重啟後 poll 仍可讀到進度。
    """
    global _13f_running, _13f_state
    _check_token(request)

    target_quarter = (body or {}).get("quarter")

    with _state_lock:
        if _13f_running:
            raise HTTPException(status_code=409, detail="13F job already running")
        _13f_running = True
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _13f_state = {
            "status":      "running",
            "started_at":  started_at,
            "finished_at": None,
            "result":      None,
            "quarter":     target_quarter or "auto",
            "heartbeat_at": started_at,
            "error":       None,
        }

    # Supabase 持久化（best-effort；失敗不影響 job 啟動）
    try:
        from data_pipeline.dual_pool import storage as _storage  # noqa: PLC0415
        _storage.upsert_job_state("13f", {
            "status":       "running",
            "started_at":   started_at,
            "finished_at":  None,
            "heartbeat_at": started_at,
            "quarter":      target_quarter or "auto",
            "result":       None,
            "error":        None,
        })
    except Exception as e:
        print(f"[dual_pool_admin] 13F trigger Supabase write error: {e}")

    # 啟動心跳執行緒
    hb_stop = threading.Event()
    hb_thread = threading.Thread(
        target=_13f_heartbeat_worker, args=(hb_stop,), daemon=True, name="13f-heartbeat"
    )
    hb_thread.start()

    background_tasks.add_task(_run_13f_bg, started_at, target_quarter, hb_stop)
    return {"started": True, "quarter": target_quarter or "auto"}


@router.get("/13f-status")
def get_13f_status(request: Request):
    """回最近一次 13F job 的狀態（需 token——狀態含 ticker/錯誤細節）。
    in-memory 有值 → 直接回（最準確）。
    in-memory 為 None（Render 重啟）→ 讀 Supabase；
      status=running 但 heartbeat 超過 15 分鐘 → 回 interrupted（可重觸）。
    """
    _check_token(request)
    with _state_lock:
        mem = _13f_state

    if mem is not None:
        return dict(mem)

    # Render 重啟後 in-memory 歸零 → 讀 Supabase
    try:
        from data_pipeline.dual_pool import storage as _storage  # noqa: PLC0415
        db = _storage.load_job_state("13f")
    except Exception as e:
        print(f"[dual_pool_admin] 13F Supabase status read error: {e}")
        return {"status": "never_run"}

    if not db:
        return {"status": "never_run"}

    # zombie 偵測：running 但 heartbeat 已 stale
    if db.get("status") == "running":
        hb = db.get("heartbeat_at")
        if hb:
            try:
                hb_dt = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                age_s = (datetime.now(timezone.utc) - hb_dt).total_seconds()
                if age_s > _HB_STALE_S:
                    db = {**db, "status": "interrupted", "interrupted_age_s": int(age_s)}
            except Exception:
                pass

    return db


# ──────────────────────────────────────────────────────────────────────────
# track_record 每週驗證 job（§7.6）
# ──────────────────────────────────────────────────────────────────────────

def _run_verify_bg(started_at: str) -> None:
    """BackgroundTask：執行 verify_track_record.run_verify_job。"""
    global _verify_state, _verify_running
    try:
        from data_pipeline.dual_pool.verify_track_record import run_verify_job  # noqa: PLC0415
        result = run_verify_job()
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _state_lock:
            _verify_state = {
                "status":      "done",
                "started_at":  started_at,
                "finished_at": finished_at,
                "result":      result,
                "error":       None,
            }
    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        err_msg = str(exc)
        print(f"[dual_pool_admin] verify background task 失敗: {err_msg}")
        with _state_lock:
            _verify_state = {
                "status":      "failed",
                "started_at":  started_at,
                "finished_at": finished_at,
                "result":      None,
                "error":       err_msg,
            }
    finally:
        with _state_lock:
            _verify_running = False


@router.post("/run-verify-track-record", status_code=202)
async def trigger_verify(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """觸發 track_record 每週驗證 job（§7.6）。"""
    global _verify_running, _verify_state
    _check_token(request)

    with _state_lock:
        if _verify_running:
            raise HTTPException(status_code=409, detail="verify job already running")
        _verify_running = True
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _verify_state = {
            "status":      "running",
            "started_at":  started_at,
            "finished_at": None,
            "result":      None,
            "error":       None,
        }

    background_tasks.add_task(_run_verify_bg, started_at)
    return {"started": True}


@router.get("/verify-status")
def get_verify_status(request: Request):
    """回最近一次 verify job 的狀態（需 token——狀態含 ticker/錯誤細節）。"""
    _check_token(request)
    with _state_lock:
        if _verify_state is None:
            return {"status": "never_run"}
        return dict(_verify_state)
