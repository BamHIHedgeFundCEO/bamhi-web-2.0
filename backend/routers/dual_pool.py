"""
backend/routers/dual_pool.py — 雙池選股 API

GET /api/dual-pool/scores?side=left|right
    最新 score_date 的分數列表，join watchpool 特徵

GET /api/dual-pool/events/{ticker}?days=90
    該 ticker 的事件流（前端明細用）

認證：照 insider router 慣例（Depends(get_current_user)）。
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from backend.auth import get_current_user
from backend.services import dual_pool as svc

router = APIRouter(prefix="/api/dual-pool", tags=["dual-pool"])


@router.get("/scores")
def get_scores(
    side: Optional[Literal["left", "right"]] = Query(None, description="left|right；省略回兩池"),
    _user: dict = Depends(get_current_user),
):
    """最新 score_date 分數列表（含 watchpool 特徵）。"""
    items = svc.get_scores(side)
    return {
        "side":   side or "all",
        "total":  len(items),
        "items":  items,
    }


@router.get("/events/{ticker}")
def get_events(
    ticker: str,
    days: int = Query(90, ge=1, le=365),
    _user: dict = Depends(get_current_user),
):
    """該 ticker 近 N 天事件流（前端展開明細用）。"""
    ticker = ticker.upper()
    events = svc.get_events(ticker, days)
    return {
        "ticker": ticker,
        "days":   days,
        "count":  len(events),
        "events": events,
    }
