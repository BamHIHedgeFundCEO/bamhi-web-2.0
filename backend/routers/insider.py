"""內部人追蹤 API — SEC Form 4。

GET /api/insider/radar?days=7&sort=buy_amount   → top 20 from cache (instant)
GET /api/insider/stock?symbol=AAPL&limit=50     → real-time single stock (1 year)
GET /api/insider/daily-digest                   → trigger Discord digest
"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from backend.auth import get_current_user
from backend.services import insider as svc
from backend.services.discord_notify import send_daily_digest

router = APIRouter(prefix="/api/insider", tags=["insider"])

SortKey = Literal["buy_amount", "sell_amount", "net_buy", "latest_date"]


@router.get("/radar")
def get_radar(
    days: int = Query(30, ge=1, le=90),
    sort: SortKey = Query("buy_amount"),
    _user: dict = Depends(get_current_user),
):
    items, updated_at, cache_size = svc.get_radar(days, sort)
    return {
        "as_of": date.today().isoformat(),
        "days": days,
        "sort": sort,
        "total": len(items),
        "cache_size": cache_size,
        "last_updated": updated_at,
        "items": items,
    }


@router.get("/stock")
def get_stock(
    symbol: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(50, ge=1, le=200),
    _user: dict = Depends(get_current_user),
):
    items = svc.fetch_stock(symbol.upper(), limit)
    return {"symbol": symbol.upper(), "count": len(items), "items": items}


@router.get("/daily-digest")
def trigger_digest(_user: dict = Depends(get_current_user)):
    items, _, _ = svc.get_radar(1, "buy_amount")
    top_buys = sorted(items, key=lambda x: x["buy_amount"], reverse=True)[:5]
    top_sells = sorted(items, key=lambda x: x["sell_amount"], reverse=True)[:5]
    send_daily_digest(top_buys, top_sells, date.today().isoformat())
    return {"status": "sent", "buy_count": len(top_buys), "sell_count": len(top_sells)}
