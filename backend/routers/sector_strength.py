"""美股板塊強弱 API (對應 Streamlit data_engine/market/strength.py)。"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import get_current_user
from backend.services import sector_strength as svc

router = APIRouter(prefix="/api/sector-strength", tags=["sector-strength"])


@router.get("/metrics")
def metrics(_user: dict = Depends(get_current_user)):
    """全板塊指標總覽 + 策略 A/B/C 掃描 + 60 日 Trend。"""
    result = svc.get_overview()
    if result is None:
        raise HTTPException(status_code=503, detail="暫無板塊強弱資料：data/sector_strength.csv 不存在")
    return result


@router.get("/heatmap")
def heatmap(
    period: int = Query(20, description="回看天數：1 / 3 / 5 / 20 / 60"),
    _user: dict = Depends(get_current_user),
):
    """動能熱力圖 (treemap) 資料：各 ETF 在指定週期的漲跌與強弱分數。"""
    result = svc.get_heatmap(period)
    if result is None:
        raise HTTPException(status_code=503, detail="暫無板塊強弱資料")
    return result


@router.get("/holdings")
def holdings(
    etf: str = Query(..., description="ETF 代號，例 XLK"),
    _user: dict = Depends(get_current_user),
):
    """ETF 成分股即時動能掃描 (黃金伏擊清單 + 全成分股總覽)。"""
    try:
        result = svc.get_holdings_metrics(etf)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if result is None:
        raise HTTPException(status_code=503, detail="暫無 etf_holdings.json")
    return result


@router.get("/relative-strength")
def relative_strength(
    tickers: str = Query(..., description="逗號分隔，例 XLK,XLF,SMH"),
    _user: dict = Depends(get_current_user),
):
    """相對強度線 (各標的 / VTI，正規化起點=1)。"""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    result = svc.get_relative_strength(ticker_list)
    if result is None:
        raise HTTPException(status_code=503, detail="暫無板塊強弱資料")
    return result
