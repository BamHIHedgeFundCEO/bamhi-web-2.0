"""拐點篩選（Inflection Screener）API。

- /api/inflection/runs           歷史 run_date 清單
- /api/inflection/pool?side=     left | right（可選 run_date）
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import get_current_user
from backend.services import inflection as svc

router = APIRouter(prefix="/api/inflection", tags=["inflection"])


@router.get("/runs")
def runs(_user: dict = Depends(get_current_user)):
    """歷史篩選 run 日期（新 → 舊）。"""
    return {"runs": svc.list_runs()}


@router.get("/pool")
def pool(
    side: str = Query(..., description="left | right"),
    run_date: str | None = Query(None, description="YYYY-MM-DD，省略取最新"),
    _user: dict = Depends(get_current_user),
):
    """左側池（基本面拐點）/ 右側池（技術確認）結果。"""
    if side not in ("left", "right"):
        raise HTTPException(status_code=404, detail=f"未知池別：{side}")
    return svc.get_pool(side, run_date)
