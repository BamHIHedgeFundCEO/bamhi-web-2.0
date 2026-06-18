"""市場觀察 API。

- GET /api/market-watch/kings        — The Kings 龍頭 + Pullback_Buy
- GET /api/market-watch/rising-stars — Rising Stars 動量加速
- GET /api/market-watch/adjacency    — Macro Compass Granger 矩陣
"""
from fastapi import APIRouter, Depends

from backend.auth import get_current_user
from backend.services import market_watch as svc

router = APIRouter(prefix="/api/market-watch", tags=["market-watch"])


@router.get("/kings")
def kings(_user: dict = Depends(get_current_user)):
    return svc.get_kings()


@router.get("/rising-stars")
def rising_stars(_user: dict = Depends(get_current_user)):
    return svc.get_rising_stars()


@router.get("/adjacency")
def adjacency(_user: dict = Depends(get_current_user)):
    return svc.get_adjacency()
