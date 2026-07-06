"""
dual_pool_admin.py — Render 端 Stage 2 觸發與狀態查詢

POST /api/dual-pool/run-stage2
  驗 X-Trigger-Token header 對 env DUAL_POOL_TRIGGER_TOKEN
  env 未設  → 503
  token 錯  → 401
  已在跑    → 409
  成功      → 202 + {"started": true}

GET /api/dual-pool/stage2-status
  回最近一次 run 的狀態（無需 token，唯讀）。
  狀態欄位：status(running|done|failed|never_run)、started_at、finished_at、
             result(run_stage2 回傳 dict，含 filings_fetched/events_upserted/fetch_degraded)、
             error(str)
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

router = APIRouter(prefix="/api/dual-pool", tags=["dual_pool_admin"])

# ── in-memory 執行狀態（Render 重啟歸零；只做監控，不需持久化）────────
_state_lock     = threading.Lock()
_stage2_state: Optional[dict] = None  # 最近一次 run 的狀態 dict
_stage2_running: bool          = False  # 是否有 run 正在進行


def _run_stage2_bg(started_at: str) -> None:
    """
    BackgroundTask 實際執行 stage2 並更新 _stage2_state。
    try/except 保證例外不消失：失敗寫進 status='failed' + error 欄位（§6.1 防靜默故障）。
    Render 工作目錄是 repo 根，可直接 import data_pipeline。
    """
    global _stage2_state, _stage2_running
    try:
        from data_pipeline.dual_pool.run_stage2 import run_stage2  # noqa: PLC0415

        result = run_stage2()

        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _state_lock:
            _stage2_state = {
                "status":      "done",
                "started_at":  started_at,
                "finished_at": finished_at,
                "result":      result,
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
    """
    觸發 stage2 背景執行（GitHub Actions 每晚呼叫）。
    驗 X-Trigger-Token header 對 env DUAL_POOL_TRIGGER_TOKEN。
    """
    global _stage2_running, _stage2_state

    token_expected = os.getenv("DUAL_POOL_TRIGGER_TOKEN")
    if not token_expected:
        raise HTTPException(
            status_code=503,
            detail="DUAL_POOL_TRIGGER_TOKEN not configured on server",
        )

    token_received = request.headers.get("X-Trigger-Token")
    if token_received != token_expected:
        raise HTTPException(status_code=401, detail="Invalid trigger token")

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
            "error":       None,
        }

    background_tasks.add_task(_run_stage2_bg, started_at)
    return {"started": True}


@router.get("/stage2-status")
def get_stage2_status():
    """回最近一次 stage2 run 的狀態（無需 token，唯讀）。"""
    with _state_lock:
        if _stage2_state is None:
            return {"status": "never_run"}
        return dict(_stage2_state)
