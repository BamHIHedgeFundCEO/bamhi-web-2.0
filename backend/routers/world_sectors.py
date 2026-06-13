"""全球市場強弱 API (對應 Streamlit data_engine/market/world_sectors.py)。"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import get_current_user
from backend.services import world_sectors as svc

router = APIRouter(prefix="/api/world-sectors", tags=["world-sectors"])


@router.get("/momentum")
def momentum(
    period: int = Query(20, description="回看天數：1 / 3 / 5 / 10 / 20 / 40 / 60 / 120"),
    _user: dict = Depends(get_current_user),
):
    """全球資產動能：treemap + 各區排行 + 策略 A/B/C。
    period >= 5 採波動率調整計分，否則純漲跌幅。
    """
    result = svc.get_momentum(period)
    if result is None:
        raise HTTPException(status_code=503, detail="暫無全球強弱資料：data/world_sectors.csv 不存在")
    return result
