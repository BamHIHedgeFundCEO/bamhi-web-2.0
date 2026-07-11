"""輸出層：CSV / Discord webhook / Supabase upsert（spec §6）。

Discord / Supabase 失敗不得使 pipeline 整體 fail — 記 log 即可。
"""
import datetime as dt
import json
import math
import os

import pandas as pd
import requests

from inflection_screener import config

LEFT_COLS = [
    "ticker", "name", "market_cap", "price", "dollar_vol_20d",
    "yoy_t", "accel_t", "accel_t1", "margin_slope", "eps_slope",
    "flags", "score", "latest_period", "filing_date", "data_quality",
]
RIGHT_EXTRA = [
    "rs_rank", "rs_line_high", "trend_template_pass", "weekly_pass",
    "vol_confirm", "obv_confirm", "vcp_proxy",
]


def _select(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = None
    return out[cols]


def write_csvs(left: pd.DataFrame, right: pd.DataFrame, outdir: str, run_date: str) -> tuple[str, str]:
    os.makedirs(outdir, exist_ok=True)
    tag = run_date.replace("-", "")
    left_path = os.path.join(outdir, f"left_pool_{tag}.csv")
    right_path = os.path.join(outdir, f"right_pool_{tag}.csv")
    _select(left, LEFT_COLS).to_csv(left_path, index=False, encoding="utf-8-sig")
    _select(right, LEFT_COLS + RIGHT_EXTRA).to_csv(right_path, index=False, encoding="utf-8-sig")
    print(f"[outputs] CSV → {left_path}, {right_path}", flush=True)
    return left_path, right_path


def send_discord(left: pd.DataFrame, right: pd.DataFrame, left_csv: str, right_csv: str, run_date: str):
    """embed 摘要（右側池前 10 + 🔺旗標名單）+ 兩份 CSV 附檔。失敗只記 log。"""
    url = os.getenv(config.DISCORD_WEBHOOK_ENV)
    if not url:
        print("[outputs] DISCORD_WEBHOOK_URL 未設定，跳過推送", flush=True)
        return
    try:
        top10 = right.head(10)
        top_lines = [
            f"`{r.ticker:<6}` RS {r.rs_rank:.0f} | YoY {r.yoy_t:+.0%} | {r.flags or '—'}"
            for r in top10.itertuples()
        ] or ["（本次右側池無標的）"]

        flagged = left[left["flags"].astype(str).str.len() > 0]
        flag_lines = [
            f"`{r.ticker:<6}` {r.flags}" for r in flagged.head(15).itertuples()
        ] or ["（無）"]

        embed = {
            "title": f"🎯 BamHI 拐點篩選 {run_date}",
            "color": 0x2ECC71,
            "fields": [
                {"name": f"右側池 Top 10（共 {len(right)} 檔）", "value": "\n".join(top_lines)[:1024]},
                {"name": f"🔺 旗標名單（左側池共 {len(left)} 檔）", "value": "\n".join(flag_lines)[:1024]},
            ],
        }
        with open(left_csv, "rb") as f1, open(right_csv, "rb") as f2:
            resp = requests.post(
                url,
                data={"payload_json": json.dumps({"embeds": [embed]})},
                files={
                    "file1": (os.path.basename(left_csv), f1, "text/csv"),
                    "file2": (os.path.basename(right_csv), f2, "text/csv"),
                },
                timeout=30,
            )
        resp.raise_for_status()
        print("[outputs] Discord 推送成功", flush=True)
    except Exception as e:
        print(f"[outputs] Discord 推送失敗（不中斷）：{e}", flush=True)


# ── Supabase ──

def _supabase():
    url = os.getenv(config.SUPABASE_URL_ENV)
    key = next((os.getenv(k) for k in config.SUPABASE_KEY_ENVS if os.getenv(k)), None)
    if not (url and key):
        print("[outputs] SUPABASE_URL / KEY 未設定，跳過入庫", flush=True)
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        print(f"[outputs] Supabase client 建立失敗（不中斷）：{e}", flush=True)
        return None


def _records(df: pd.DataFrame) -> list[dict]:
    """NaN/Inf → None，日期 → ISO 字串（JSON 相容）。"""
    recs = []
    for rec in df.to_dict(orient="records"):
        clean = {}
        for k, v in rec.items():
            if isinstance(v, float) and not math.isfinite(v):
                v = None
            elif isinstance(v, (pd.Timestamp, dt.date, dt.datetime)):
                v = str(v)[:10]
            elif isinstance(v, (bool,)):
                pass
            elif pd.isna(v) if not isinstance(v, (list, dict)) else False:
                v = None
            clean[k] = v
        recs.append(clean)
    return recs


def _chunked_upsert(sb, table: str, records: list[dict], on_conflict: str):
    for i in range(0, len(records), 500):
        sb.table(table).upsert(records[i:i + 500], on_conflict=on_conflict).execute()


def upsert_fundamentals(qtable: pd.DataFrame):
    """fundamentals_quarterly — upsert on (cik, period_end)，冪等。"""
    sb = _supabase()
    if sb is None or qtable.empty:
        return
    try:
        df = qtable.dropna(subset=["period_end"]).copy()
        df = df[["cik", "ticker", "period_end", "filing_date", "accn",
                 "revenue", "net_income", "eps_diluted", "data_quality"]]
        _chunked_upsert(sb, config.TABLE_FUNDAMENTALS, _records(df), "cik,period_end")
        print(f"[outputs] Supabase fundamentals upsert {len(df)} 列", flush=True)
    except Exception as e:
        print(f"[outputs] Supabase fundamentals 失敗（不中斷）：{e}", flush=True)


def upsert_pools(left: pd.DataFrame, right: pd.DataFrame, run_date: str):
    """兩池入庫，以 run_date 區分保留歷史；upsert on (run_date, ticker) 冪等。"""
    sb = _supabase()
    if sb is None:
        return
    for table, df, cols in (
        (config.TABLE_LEFT, left, LEFT_COLS),
        (config.TABLE_RIGHT, right, LEFT_COLS + RIGHT_EXTRA),
    ):
        if df.empty:
            continue
        try:
            out = _select(df, cols).copy()
            out["run_date"] = run_date
            _chunked_upsert(sb, table, _records(out), "run_date,ticker")
            print(f"[outputs] Supabase {table} upsert {len(out)} 列", flush=True)
        except Exception as e:
            print(f"[outputs] Supabase {table} 失敗（不中斷）：{e}", flush=True)
