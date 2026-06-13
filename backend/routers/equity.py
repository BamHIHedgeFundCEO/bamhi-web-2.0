"""個股深度搜尋 API (對應 Streamlit views/search_view.py + data_engine/equity.py)。"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import get_current_user
from backend.services import equity as svc

router = APIRouter(prefix="/api/equity", tags=["equity"])


@router.get("/profile")
def profile(
    ticker: str = Query(..., description="美股代碼 (AAPL) 或台股 (2330.TW)"),
    period: str = Query("2y", description="6mo / 1y / 2y / 5y / 10y / max"),
    interval: str = Query("1d", description="1h / 1d / 1wk"),
    _user: dict = Depends(get_current_user),
):
    """個股完整檔案：價格/估值/公司資料/K線+量化分數/財報。"""
    result = svc.get_profile(ticker, period, interval)
    if result is None:
        raise HTTPException(status_code=404, detail=f"找不到代碼 {ticker.upper()}，請確認輸入是否正確 (例如 AAPL, TSLA)。")
    return result
