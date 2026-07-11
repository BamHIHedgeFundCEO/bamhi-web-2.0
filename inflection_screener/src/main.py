"""BamHI 拐點篩選 — orchestration（spec §7）。

用法：
    python -m inflection_screener.src.main                    # 全量 run
    python -m inflection_screener.src.main --tickers NVDA,AAPL,CVNA,SOUN,COST --dry-run
    python -m inflection_screener.src.main --skip-discord --skip-supabase
"""
import argparse
import datetime as dt

import pandas as pd

from inflection_screener import config
from inflection_screener.src import clean, edgar_frames, fundamentals, outputs, prices, screener


def _print_revenue_series(qtable: pd.DataFrame, tickers: list[str]):
    """dry-run 用：印出 8 季營收/淨利序列，供人工核對 IR 頁面（驗收 #2）。"""
    for t in tickers:
        sub = qtable[qtable["ticker"] == t].sort_values(["year", "q"])
        if sub.empty:
            print(f"\n── {t}: 無資料（可能非日曆財年或未映射到 CIK）──", flush=True)
            continue
        print(f"\n── {t}（data_quality={sub['data_quality'].iloc[0]}）──", flush=True)
        view = sub[["year", "q", "period_end", "revenue", "net_income", "eps_diluted"]]
        print(view.to_string(index=False), flush=True)


def run(tickers_filter: list[str] | None = None, dry_run: bool = False,
        skip_discord: bool = False, skip_supabase: bool = False, outdir: str = config.OUTPUT_DIR):
    run_date = dt.date.today().isoformat()
    print(f"[main] run_date={run_date}, dry_run={dry_run}", flush=True)

    # 1) EDGAR frames（全市場批量，~40 calls）
    quarterly, annual, window = edgar_frames.fetch_all_frames()
    ticker_map = edgar_frames.fetch_ticker_map()

    # 2) 清洗 → 逐季寬表
    qtable = clean.build_quarterly_table(quarterly, annual, window)
    qtable = qtable.merge(ticker_map, on="cik", how="left")

    if tickers_filter:
        wanted = {t.upper() for t in tickers_filter}
        qtable = qtable[qtable["ticker"].isin(wanted)].copy()
        _print_revenue_series(qtable, sorted(wanted))

    # 3) 指標
    metrics = fundamentals.compute_metrics(qtable)
    if metrics.empty:
        print("[main] 無可計算指標公司，結束", flush=True)
        return
    metrics = metrics.merge(ticker_map, on="cik", how="left").dropna(subset=["ticker"])

    # 4) 閘門 ②（先於 yfinance，絕不全市場掃價格）
    candidates = screener.accel_candidates(metrics)
    if dry_run and tickers_filter:
        cols = ["ticker", "yoy_t", "accel_t", "accel_t1", "margin_slope", "eps_slope",
                "flag_turn_positive", "flag_near_positive"]
        print("\n── 指標總表（含未通過閘門者）──", flush=True)
        print(metrics[cols].to_string(index=False), flush=True)

    # 5) 價格（僅候選清單 + SPY）
    tickers = candidates["ticker"].tolist()
    hists, caps, failed = prices.fetch_all(tickers)
    spy = prices.fetch_history(config.BENCHMARK)
    if spy is None:
        print("[main] ⚠ SPY 抓取失敗，右側池 RS 無法計算，僅出左側池", flush=True)

    # 6) 兩池
    left = screener.assemble_left(candidates, hists, caps)
    right = (
        screener.assemble_right(left, hists, spy["Close"])
        if spy is not None and not left.empty
        else pd.DataFrame()
    )

    # 7) 輸出
    left_csv, right_csv = outputs.write_csvs(left, right, outdir, run_date)
    if not skip_supabase:
        outputs.upsert_fundamentals(qtable)
        outputs.upsert_pools(left, right, run_date)
    if not skip_discord:
        outputs.send_discord(left, right, left_csv, right_csv, run_date)

    print(f"[main] 完成：左側池 {len(left)} 檔 / 右側池 {len(right)} 檔 / 價格失敗 {len(failed)} 檔", flush=True)


def main():
    p = argparse.ArgumentParser(description="BamHI 拐點篩選系統")
    p.add_argument("--tickers", help="逗號分隔，限定 universe（dry-run 核對用）")
    p.add_argument("--dry-run", action="store_true", help="印出營收序列與指標總表，並跳過 Discord/Supabase")
    p.add_argument("--skip-discord", action="store_true")
    p.add_argument("--skip-supabase", action="store_true")
    p.add_argument("--outdir", default=config.OUTPUT_DIR)
    a = p.parse_args()
    run(
        tickers_filter=a.tickers.split(",") if a.tickers else None,
        dry_run=a.dry_run,
        skip_discord=a.skip_discord or a.dry_run,
        skip_supabase=a.skip_supabase or a.dry_run,
        outdir=a.outdir,
    )


if __name__ == "__main__":
    main()
