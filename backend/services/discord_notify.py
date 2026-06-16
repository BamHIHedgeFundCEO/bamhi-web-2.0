"""Discord webhook 通知 — 每日摘要 + 超大單即時警報。"""
import os
import time

import httpx

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
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
