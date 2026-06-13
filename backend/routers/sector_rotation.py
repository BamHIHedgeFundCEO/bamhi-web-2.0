"""板塊輪動與 VCP 監控 API (對應 Streamlit views/sector_rotation.py)。

整併自專案原本的 api.py。全板塊一次 bulk download (yfinance) 後行程內快取。
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import get_current_user
from backend.services import sector_rotation as svc

router = APIRouter(prefix="/api/sector-rotation", tags=["sector-rotation"])


@router.get("/sectors")
def sectors(_user: dict = Depends(get_current_user)):
    """所有追蹤板塊清單 + 成分股 + 龍頭股。"""
    return {"sectors": svc.list_sectors()}


@router.get("/signals")
def signals(
    period: str = Query("1y", description="6mo / 1y / 2y ..."),
    _user: dict = Depends(get_current_user),
):
    """首頁板塊即時訊號推播（所有板塊進出場狀態）。"""
    result = svc.signals_cached(period)
    if result is None:
        raise HTTPException(status_code=503, detail="資料獲取失敗（yfinance 下載為空）")
    return result


@router.get("/overview")
def overview(
    period: str = Query("2y", description="6mo / 1y / 2y / 5y / 10y / max"),
    _user: dict = Depends(get_current_user),
):
    """全板塊全覽：動能熱力圖 + RRG 即時 + RRG 軌跡 + 相關係數矩陣。"""
    result = svc.overview_cached(period)
    if result is None:
        raise HTTPException(status_code=503, detail="資料獲取失敗（yfinance 下載為空）")
    return result


@router.get("/detail")
def detail(
    sector: str = Query(..., description="板塊名稱，需與 /sectors 回傳一致"),
    period: str = Query("2y"),
    _user: dict = Depends(get_current_user),
):
    """單一板塊深度：頂部指標 + 狀態 + K線/RS/寬度/機構流/動能圖序列 + VCP 掃描。"""
    result = svc.detail_cached(sector, period)
    if result is None:
        raise HTTPException(status_code=404, detail=f"未知板塊：{sector}")
    return result
