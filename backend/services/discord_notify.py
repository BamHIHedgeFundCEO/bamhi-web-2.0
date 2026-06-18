"""Discord webhook 通知 — 每日摘要 + 超大單即時警報 + 市場觀察三報。"""
import os
import time

import httpx

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
_MW_KINGS   = os.getenv("MW_WEBHOOK_KINGS", "")
_MW_STARS   = os.getenv("MW_WEBHOOK_STARS", "")
_MW_COMPASS = os.getenv("MW_WEBHOOK_COMPASS", "")
MEGA_THRESHOLD = float(os.getenv("INSIDER_MEGA_THRESHOLD", "5000000"))

# 已通知 set，key = filing_date+symbol+reporting_name，TTL 24h
_NOTIFIED: dict[str, float] = {}
_NOTIFIED_TTL = 86400


def _clean_notified():
    now = time.time()
    expired = [k for k, ts in _NOTIFIED.items() if now - ts > _NOTIFIED_TTL]
    for k in expired:
        del _NOTIFIED[k]


def _post(payload: dict) -> None:
    if not WEBHOOK_URL:
        return
    try:
        httpx.post(WEBHOOK_URL, json=payload, timeout=6)
    except Exception as e:
        print(f"[discord] webhook 失敗: {e}")


def _post_to(url: str, payload: dict) -> None:
    if not url:
        return
    try:
        httpx.post(url, json=payload, timeout=6)
    except Exception as e:
        print(f"[discord] webhook 失敗 ({url[:50]}...): {e}")


def notify_mega_trade(trade: dict) -> None:
    """單筆 >= MEGA_THRESHOLD 即時推送。"""
    key = f"{trade.get('filingDate')}|{trade.get('symbol')}|{trade.get('reportingName')}"
    _clean_notified()
    if key in _NOTIFIED:
        return
    _NOTIFIED[key] = time.time()

    is_buy = trade.get("transactionType") == "P-Purchase"
    amount = trade.get("amount", 0) or 0
    payload = {
        "embeds": [
            {
                "title": f"{'🟢 超大筆買入' if is_buy else '🔴 超大筆賣出'} — {trade.get('symbol', '?')}",
                "color": 0x00FF88 if is_buy else 0xFF4444,
                "fields": [
                    {
                        "name": "內部人",
                        "value": f"{trade.get('reportingName', '—')}\n{trade.get('reportingOwner', '')}",
                        "inline": True,
                    },
                    {"name": "類型", "value": trade.get("transactionType", "—"), "inline": True},
                    {"name": "金額", "value": f"${amount:,.0f}", "inline": True},
                    {
                        "name": "股數 × 價格",
                        "value": f"{abs(trade.get('securitiesTransacted') or 0):,.0f} × ${trade.get('price') or 0:.2f}",
                        "inline": True,
                    },
                    {"name": "交易日", "value": str(trade.get("transactionDate", "—")), "inline": True},
                    {"name": "申報日", "value": str(trade.get("filingDate", "—")), "inline": True},
                ],
                "footer": {"text": "SEC Form 4 • BamHI Quant"},
            }
        ]
    }
    _post(payload)


def send_market_watch_report(date_str: str) -> None:
    """市場觀察每日三報 — Kings / Rising Stars / Macro Compass 分三頻道推送。"""
    try:
        from backend.services.market_watch import get_kings, get_rising_stars, get_adjacency
        kings_data  = get_kings()
        stars_data  = get_rising_stars()
        compass_data = get_adjacency()
    except Exception as e:
        print(f"[discord] 市場觀察資料讀取失敗: {e}")
        return

    # ── 👑 The Kings ─────────────────────────────────────────────────────────
    buy_items = [i for i in kings_data.get("items", []) if i.get("Pullback_Buy")]
    if buy_items:
        lines = []
        for item in buy_items[:15]:
            rsi = item.get("RSI14", "—")
            rank = item.get("Rank", "—")
            si = item.get("sub_industry", "")
            lines.append(f"**{item['ticker']}** `Rank={rank}` RSI={rsi} [{si}]")
        body = "\n".join(lines) or "（今日無進場訊號）"
    else:
        body = "（今日無 Pullback_Buy 訊號）"

    _post_to(_MW_KINGS, {
        "embeds": [{
            "title": f"👑 THE KINGS — Pullback_Buy 訊號 {date_str}",
            "color": 0xFFD700,
            "description": body,
            "footer": {"text": "RS Rating • BamHI Quant"},
        }]
    })

    # ── 🚀 Rising Stars ───────────────────────────────────────────────────────
    star_items = stars_data.get("items", [])
    if star_items:
        lines = []
        for item in star_items[:15]:
            r20, r60, r120 = item.get("20R","—"), item.get("60R","—"), item.get("120R","—")
            acc = item.get("Accel", "")
            lines.append(f"**{item['ticker']}** `20R={r20} > 60R={r60} > 120R={r120}` 加速+{acc}")
        body = "\n".join(lines) or "（今日無加速標的）"
    else:
        body = "（今日無 Rising Stars）"

    _post_to(_MW_STARS, {
        "embeds": [{
            "title": f"🚀 RISING STARS — 動量加速黑馬 {date_str}",
            "color": 0x00FF88,
            "description": body,
            "footer": {"text": "RS Rating • BamHI Quant"},
        }]
    })

    # ── 🕸️ Macro Compass ─────────────────────────────────────────────────────
    edges = compass_data.get("edges", [])
    sectors_map = compass_data.get("sectors", {})
    if edges:
        lines = []
        for frm, to, p in edges[:8]:
            sf = sectors_map.get(frm, "")
            st = sectors_map.get(to, "")
            lines.append(f"**{frm}** → **{to}** `p={p}`  [{sf} → {st}]")
        body = "\n".join(lines) or "（今日無顯著因果連結）"
    else:
        body = "（今日無顯著 Granger 因果連結，p<0.05）"

    _post_to(_MW_COMPASS, {
        "embeds": [{
            "title": f"🕸️ MACRO COMPASS — 資金傳導鏈 {date_str}",
            "color": 0x7289DA,
            "description": body,
            "footer": {"text": "Granger Causality (p<0.05) • BamHI Quant"},
        }]
    })


def send_daily_digest(top_buys: list[dict], top_sells: list[dict], date_str: str) -> None:
    """每日摘要 — top 5 買入 + top 5 賣出。"""
    def fmt_line(t: dict) -> str:
        return f"**{t['symbol']}** {t.get('reportingName', '—')} ${t.get('buy_amount', t.get('sell_amount', 0)):,.0f}"

    buy_lines = "\n".join(fmt_line(t) for t in top_buys[:5]) or "（無）"
    sell_lines = "\n".join(fmt_line(t) for t in top_sells[:5]) or "（無）"
    payload = {
        "embeds": [
            {
                "title": f"📋 內部人交易每日摘要 — {date_str}",
                "color": 0x7289DA,
                "fields": [
                    {"name": "🟢 Top 5 買入", "value": buy_lines, "inline": False},
                    {"name": "🔴 Top 5 賣出", "value": sell_lines, "inline": False},
                ],
                "footer": {"text": "SEC Form 4 • BamHI Quant"},
            }
        ]
    }
    _post(payload)
