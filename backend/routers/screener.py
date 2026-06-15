"""BamHI 模型選股 API。

- /api/screener/vcp              跨板塊 VCP 彙整候選
- /api/screener/models?engine=   Alpha / Genesis 市值分級篩選
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import get_current_user
from backend.services import screener as svc

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("/vcp")
def vcp(
    min_score: int = Query(60, description="最低 VCP 分數門檻"),
    _user: dict = Depends(get_current_user),
):
    """跨 17 板塊彙整 VCP 掃描的強訊 / 高分標的。"""
    return svc.screen_vcp(min_score)


@router.get("/models")
def models(
    engine: str = Query(..., description="alpha | genesis"),
    _user: dict = Depends(get_current_user),
):
    """Alpha / Genesis 戰報套 SCREENING_PLAYBOOK 市值分級篩選。"""
    if engine not in ("alpha", "genesis"):
        raise HTTPException(status_code=404, detail=f"未知引擎：{engine}")
    return svc.screen_models(engine)
