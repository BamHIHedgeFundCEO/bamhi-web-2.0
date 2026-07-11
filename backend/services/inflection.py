"""拐點篩選（Inflection Screener）結果讀取 — 資料來源 Supabase。

表由 inflection_screener pipeline（GitHub Actions 每週六）寫入：
  screen_left_pool / screen_right_pool（primary key: run_date, ticker）
此服務只讀，不做計算。
"""
import os
import threading

_sb = None
_sb_lock = threading.Lock()

_TABLES = {"left": "screen_left_pool", "right": "screen_right_pool"}


def _supabase():
    global _sb
    with _sb_lock:
        if _sb is not None:
            return _sb
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if url and key:
            try:
                from supabase import create_client
                _sb = create_client(url, key)
            except Exception as e:
                print(f"[inflection] Supabase client 失敗: {e}")
        else:
            print("[inflection] SUPABASE_URL / SUPABASE_SERVICE_KEY 未設定")
        return _sb


def list_runs(limit: int = 30) -> list[str]:
    """歷史 run_date 清單（新 → 舊）。"""
    sb = _supabase()
    if sb is None:
        return []
    resp = (
        sb.table(_TABLES["left"])
        .select("run_date")
        .order("run_date", desc=True)
        .limit(5000)
        .execute()
    )
    seen: list[str] = []
    for row in resp.data or []:
        d = row["run_date"]
        if d not in seen:
            seen.append(d)
        if len(seen) >= limit:
            break
    return seen


def get_pool(side: str, run_date: str | None = None) -> dict:
    """單一池結果。run_date 省略 → 最新一次 run。"""
    sb = _supabase()
    if sb is None:
        return {"run_date": None, "items": [], "error": "Supabase 未設定"}

    table = _TABLES[side]
    if run_date is None:
        runs = list_runs(limit=1)
        if not runs:
            return {"run_date": None, "items": []}
        run_date = runs[0]

    order_col = "rs_rank" if side == "right" else "score"
    resp = (
        sb.table(table)
        .select("*")
        .eq("run_date", run_date)
        .order(order_col, desc=True)
        .limit(2000)
        .execute()
    )
    items = resp.data or []
    # 🔺 旗標置頂（與 pipeline 排序一致）
    items.sort(key=lambda r: (not bool(r.get("flags")), -(r.get(order_col) or 0)))
    return {"run_date": run_date, "items": items}
