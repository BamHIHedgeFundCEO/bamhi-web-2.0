"""
data_pipeline/market/market_radar.py
全市場 RS Rating 雷達 — 每日更新三大戰情儀表板。

輸出：
  data/mr_kings.csv         — 各板塊龍頭 + Pullback_Buy 訊號
  data/mr_rising_stars.csv  — 動量加速黑馬
  data/mr_adjacency.json    — Granger 因果鄰接矩陣（各板塊 #1 龍頭）
"""

import gc
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
from sector_config import TRACKED_SECTORS

DATA_DIR = ROOT_DIR / "data"
RUSSELL_XLSX = ROOT_DIR / "羅素1000.xlsx"

MIN_ADV = 300_000
DAYS = 260  # ≥252 個交易日，供 52 週高距離（OffHigh）計算
GRANGER_LAG = 3
GRANGER_ALPHA = 0.05
BATCH = 100          # smaller batches → less rate-limit pressure
BATCH_SLEEP = 2      # seconds between batches
BATCH_RETRIES = 3    # retry failed batch up to 3x with exponential backoff


class StaleDataError(RuntimeError):
    """新抓到的資料比現有 CSV 還舊 —— 中止寫檔，不要用舊資料蓋掉好資料。

    2026-07-26 的排程跑出這個狀況：job 回報 success，但 Yahoo 回的整批資料
    只到 07-23（週四），把 07-24（週五）的正確資料覆蓋掉。CSV 當時沒有日期欄位，
    前端顯示的「更新時間」是檔案 mtime（＝跑批次的時間），所以畫面上完全看不出來。
    """


def update():
    print("   [Market Radar] start...")
    try:
        _run()
        print("   [Market Radar] done")
    except Exception as e:
        print(f"   [Market Radar] error: {e}")
        raise


def _existing_as_of(path: Path) -> pd.Timestamp | None:
    """讀現有 CSV 的 as_of。舊格式沒有這欄 → None（第一次跑不擋）。"""
    if not path.exists():
        return None
    try:
        col = pd.read_csv(path, usecols=["as_of"])["as_of"]
    except (ValueError, KeyError, pd.errors.EmptyDataError):
        return None
    parsed = pd.to_datetime(col, errors="coerce").dropna()
    return parsed.max() if not parsed.empty else None


def _run():
    universe = _build_universe()
    all_tickers = universe["ticker"].tolist()
    print(f"      Universe: {len(all_tickers)} tickers")

    print(f"      downloading {len(all_tickers) + 1} tickers x {DAYS} days...")
    close, volume, failed_batches = _fetch_prices(all_tickers + ["SPY"])

    if close.empty:
        raise StaleDataError("下載結果為空，不寫檔")

    # 資料日期閘門：拿到的最後一根 bar 比現有 CSV 舊就中止，讓 job 以非零碼結束。
    as_of = pd.Timestamp(close.index[-1]).normalize()
    prev_as_of = _existing_as_of(DATA_DIR / "mr_kings.csv")
    print(f"      as_of: {as_of.date()}  (現有 CSV: {prev_as_of.date() if prev_as_of is not None else '無'})")
    if prev_as_of is not None and as_of < prev_as_of:
        raise StaleDataError(
            f"新資料 {as_of.date()} 比現有 CSV {prev_as_of.date()} 還舊"
            f"（{failed_batches} 個 batch 下載失敗）—— 中止寫檔，保留原資料"
        )
    if failed_batches:
        print(f"      [warn] {failed_batches} 個 batch 下載失敗，本次資料可能不完整")

    spy = close["SPY"].copy() if "SPY" in close.columns else None
    close = close.drop(columns=["SPY"], errors="ignore")
    volume = volume.drop(columns=["SPY"], errors="ignore")

    if spy is None or spy.dropna().empty:
        print("      [warn] SPY download failed, Pullback_Buy disabled")

    liquid = _liquidity_filter(close, volume)
    print(f"      after liquidity filter: {len(liquid)} tickers")
    close = close[[t for t in liquid if t in close.columns]]

    df_rank = _rs_rating(close)

    uni = universe.set_index("ticker")
    df_rank = df_rank.join(uni, how="left")
    df_rank["sector"] = df_rank["sector"].fillna("Other")
    df_rank["sub_industry"] = df_rank["sub_industry"].fillna("Other")
    df_rank = df_rank.dropna(subset=["Rank"])

    # 🆕 比對前一次名單（在覆寫 CSV 前讀舊檔）
    prev_kings = _prev_tickers(DATA_DIR / "mr_kings.csv")
    prev_stars = _prev_tickers(DATA_DIR / "mr_rising_stars.csv")

    kings = _kings(df_rank, close, spy)
    stars = _rising_stars(df_rank, close)

    # 市值：只對上榜的 ~200 檔抓 fast_info
    caps = _fetch_mktcaps(sorted(set(kings["ticker"]) | set(stars["ticker"])))
    kings["MktCap"] = kings["ticker"].map(caps)
    stars["MktCap"] = stars["ticker"].map(caps)

    kings["Is_New"] = kings["ticker"].apply(lambda t: t not in prev_kings) if prev_kings is not None else False
    stars["Is_New"] = stars["ticker"].apply(lambda t: t not in prev_stars) if prev_stars is not None else False

    # 資料日期寫進檔案本身，前端才能顯示「資料是哪一天的」而不是「批次何時跑的」
    kings["as_of"] = as_of.strftime("%Y-%m-%d")
    stars["as_of"] = as_of.strftime("%Y-%m-%d")

    kings.to_csv(DATA_DIR / "mr_kings.csv", index=False)
    print(f"      Kings: {len(kings)} (new: {int(kings['Is_New'].sum())})")
    stars.to_csv(DATA_DIR / "mr_rising_stars.csv", index=False)
    print(f"      Rising Stars: {len(stars)} (new: {int(stars['Is_New'].sum())})")

    # Macro Compass: top 1 per sector
    top1 = (
        kings.sort_values("Rank", ascending=False)
        .groupby("sector")
        .head(1)
        .reset_index(drop=True)
    )
    compass_tickers = [t for t in top1["ticker"].tolist() if t in close.columns]
    if len(compass_tickers) >= 4:
        adj = _granger_adjacency(close, compass_tickers, top1)
    else:
        adj = {"nodes": compass_tickers, "edges": [], "sectors": {}, "computed_at": _now()}

    with open(DATA_DIR / "mr_adjacency.json", "w", encoding="utf-8") as f:
        json.dump(adj, f, ensure_ascii=False)
    print(f"      Macro Compass: {len(compass_tickers)} nodes, {len(adj['edges'])} edges")

    gc.collect()


def _build_universe() -> pd.DataFrame:
    df_r = pd.read_excel(
        RUSSELL_XLSX, header=None, names=["ticker_raw", "sector", "sub_industry"]
    )
    df_r["ticker"] = (
        df_r["ticker_raw"]
        .str.replace(r"\s+\w+\s+Equity$", "", regex=True)
        .str.strip()
        .str.upper()
    )
    df_r = df_r[["ticker", "sector", "sub_industry"]].copy()
    r_set = set(df_r["ticker"])

    rows = []
    for sector_name, tickers in TRACKED_SECTORS.items():
        for t in tickers:
            t = t.strip().upper()
            if t not in r_set:
                rows.append({"ticker": t, "sector": "BamHI", "sub_industry": sector_name})

    df_bamhi = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["ticker", "sector", "sub_industry"])
    universe = pd.concat([df_r, df_bamhi], ignore_index=True).drop_duplicates(subset="ticker")
    return universe.reset_index(drop=True)


def _download_batch(batch: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download one batch; returns (close_df, vol_df) or empty DataFrames on failure."""
    raw = yf.download(batch, period=f"{DAYS}d", auto_adjust=True, threads=False, progress=False)
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        close_df = raw["Close"]
        vol_df = raw["Volume"]
        if isinstance(close_df, pd.Series):
            close_df = close_df.to_frame(name=batch[0])
            vol_df = vol_df.to_frame(name=batch[0])
    else:
        close_df = raw[["Close"]].rename(columns={"Close": batch[0]}) if "Close" in raw.columns else pd.DataFrame()
        vol_df = raw[["Volume"]].rename(columns={"Volume": batch[0]}) if "Volume" in raw.columns else pd.DataFrame()
    return close_df, vol_df


def _fetch_prices(tickers: list) -> tuple:
    """回傳 (close, volume, failed_batches)。failed_batches 供 _run 判斷資料完整度。"""
    all_close = {}
    all_vol = {}
    failed_batches = 0

    batches = [
        [t for t in tickers[i : i + BATCH] if t]
        for i in range(0, len(tickers), BATCH)
    ]

    for idx, batch in enumerate(batches):
        if not batch:
            continue
        if idx > 0:
            time.sleep(BATCH_SLEEP)

        close_df, vol_df = pd.DataFrame(), pd.DataFrame()
        for attempt in range(BATCH_RETRIES):
            try:
                close_df, vol_df = _download_batch(batch)
                if not close_df.empty:
                    break
            except Exception as e:
                wait = 5 * (2 ** attempt)
                print(f"      [warn] batch {idx} attempt {attempt+1} failed: {e}; retry in {wait}s")
                time.sleep(wait)

        if close_df.empty:
            print(f"      [warn] batch {idx} gave up after {BATCH_RETRIES} attempts")
            failed_batches += 1
            continue

        for t in close_df.columns:
            if t in batch:
                all_close[t] = close_df[t].ffill()
                if t in vol_df.columns:
                    all_vol[t] = vol_df[t].ffill()

    if not all_close:
        return pd.DataFrame(), pd.DataFrame(), failed_batches

    close = pd.DataFrame(all_close).ffill()
    volume = pd.DataFrame(all_vol).ffill()

    # Drop today's bar only if market is still open (before 16:00 ET)
    now_et = pd.Timestamp.now(tz="America/New_York")
    cutoff = now_et.normalize().tz_localize(None)
    if now_et.hour >= 16:
        cutoff += pd.Timedelta(days=1)
    close = close[close.index < cutoff]
    volume = volume[volume.index < cutoff]

    return close, volume, failed_batches


def _liquidity_filter(close: pd.DataFrame, volume: pd.DataFrame) -> list:
    common = [t for t in close.columns if t in volume.columns]
    adv = volume[common].tail(30).mean()
    return adv[adv >= MIN_ADV].index.tolist()


def _rs_rating(close: pd.DataFrame) -> pd.DataFrame:
    roc20  = close.pct_change(20).iloc[-1]
    roc60  = close.pct_change(60).iloc[-1]
    roc120 = close.pct_change(120).iloc[-1]

    r20  = roc20.rank(pct=True)  * 100
    r60  = roc60.rank(pct=True)  * 100
    r120 = roc120.rank(pct=True) * 100
    rank = 0.2 * r20 + 0.4 * r60 + 0.4 * r120

    df = pd.DataFrame({
        "20R":   r20,
        "60R":   r60,
        "120R":  r120,
        "Rank":  rank,
        "Price": close.ffill().iloc[-1],
    })
    df.index.name = "ticker"
    return df


def _rsi14(series: pd.Series) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    v = rsi.dropna()
    return float(v.iloc[-1]) if not v.empty else 50.0


def _pullback_buy(ticker: str, close: pd.DataFrame, spy: pd.Series | None) -> bool:
    if spy is None:
        return False
    c = close[ticker].dropna()
    if len(c) < 55:
        return False
    rsi = _rsi14(c)
    if rsi >= 60 or rsi <= 30:
        return False
    spy_aligned = spy.reindex(c.index).ffill()
    rel = c / spy_aligned.replace(0, np.nan)
    ma50 = rel.rolling(50).mean()
    if pd.isna(ma50.iloc[-1]) or rel.iloc[-1] <= ma50.iloc[-1]:
        return False
    return True


def _prev_tickers(path) -> set | None:
    """上一次輸出的 ticker 名單；檔案不存在/壞掉 → None（Is_New 全 False，避免首跑全標 🆕）。"""
    try:
        return set(pd.read_csv(path)["ticker"])
    except Exception:
        return None


def _fetch_mktcaps(tickers: list) -> dict:
    """僅對上榜 ticker 逐檔抓市值（fast_info），失敗記 None 不中斷。"""
    caps = {}
    for t in tickers:
        try:
            fi = yf.Ticker(t).fast_info
            mc = fi.get("marketCap") or fi.get("market_cap")
            caps[t] = float(mc) if mc else None
        except Exception:
            caps[t] = None
    n_miss = sum(1 for v in caps.values() if v is None)
    if n_miss:
        print(f"      [warn] 市值缺失 {n_miss}/{len(caps)} 檔")
    return caps


def _off_high(ticker: str, close: pd.DataFrame) -> float | None:
    """離 52 週高距離（%，負值 = 低於高點）。"""
    if ticker not in close.columns:
        return None
    c = close[ticker].dropna().tail(252)
    if c.empty or c.max() <= 0:
        return None
    return round((c.iloc[-1] / c.max() - 1) * 100, 1)


_KINGS_RS_FLOOR = 80  # 絕對 RS Rank 下限：只留全市場動能前 20% 的真龍頭（IBD 風格）


def _kings(df_rank: pd.DataFrame, close: pd.DataFrame, spy) -> pd.DataFrame:
    df = df_rank.reset_index()
    # 先過絕對門檻（濾掉「矮子裡的高個」），再各 sub_industry 取前 3
    df = df[df["Rank"] >= _KINGS_RS_FLOOR]
    top3 = (
        df.sort_values("Rank", ascending=False)
        .groupby("sub_industry")
        .head(3)
        .reset_index(drop=True)
    )
    top3["Pullback_Buy"] = top3["ticker"].apply(
        lambda t: _pullback_buy(t, close, spy) if t in close.columns else False
    )
    top3["RSI14"] = top3["ticker"].apply(
        lambda t: round(_rsi14(close[t].dropna()), 1) if t in close.columns else None
    )
    top3["OffHigh"] = top3["ticker"].apply(lambda t: _off_high(t, close))
    cols = ["ticker", "sector", "sub_industry", "Rank", "20R", "60R", "120R", "RSI14", "OffHigh", "Pullback_Buy", "Price"]
    return top3[[c for c in cols if c in top3.columns]].round({"Rank": 1, "20R": 1, "60R": 1, "120R": 1, "Price": 2})


def _rising_stars(df_rank: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    df = df_rank.reset_index()
    mask = (
        (df["20R"] > df["60R"]) &
        (df["60R"] > df["120R"]) &
        ((df["20R"] - df["120R"]) >= 30) &
        (df["20R"] >= 75)
    )
    stars = df[mask].copy()
    stars["Accel"] = (stars["20R"] - stars["120R"]).round(1)

    def _rsi_safe(t):
        return _rsi14(close[t].dropna()) if t in close.columns else 50.0

    stars["RSI14"] = stars["ticker"].apply(_rsi_safe).round(1)
    # 兩訊號以 RSI 55 切開互斥（55–75 追、30–55 等），同一檔只會亮一個
    stars["Entry_Momentum"] = (stars["RSI14"] >= 55) & (stars["RSI14"] < 75) & (stars["Accel"] > 40)
    stars["Entry_Pullback"] = (stars["RSI14"] > 30) & (stars["RSI14"] < 55) & (stars["Accel"] > 40)

    stars["OffHigh"] = stars["ticker"].apply(lambda t: _off_high(t, close))
    cols = ["ticker", "sector", "sub_industry", "20R", "60R", "120R", "Accel", "Rank", "RSI14", "OffHigh", "Entry_Momentum", "Entry_Pullback", "Price"]
    return (
        stars[[c for c in cols if c in stars.columns]]
        .sort_values("Accel", ascending=False)
        .round({"20R": 1, "60R": 1, "120R": 1, "Accel": 1, "Rank": 1, "Price": 2})
    )


def _granger_adjacency(close: pd.DataFrame, node_tickers: list, node_info: pd.DataFrame) -> dict:
    import warnings
    from statsmodels.tsa.stattools import grangercausalitytests

    ret = close[node_tickers].pct_change().tail(90).dropna(how="all")
    pairs = [(a, b) for a in node_tickers for b in node_tickers if a != b]

    def _test(args):
        a, b = args
        try:
            data = ret[[b, a]].dropna()
            if len(data) < GRANGER_LAG + 5:
                return (a, b, 1.0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                res = grangercausalitytests(data.values, maxlag=GRANGER_LAG, verbose=False)
            p = min(res[lag][0]["ssr_ftest"][1] for lag in range(1, GRANGER_LAG + 1))
            return (a, b, round(float(p), 4))
        except Exception:
            return (a, b, 1.0)

    edges = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for a, b, p in pool.map(_test, pairs):
            if p < GRANGER_ALPHA:
                edges.append([a, b, p])

    edges.sort(key=lambda x: x[2])

    ni = node_info.set_index("ticker")
    sectors_map = {t: (ni.loc[t, "sub_industry"] if t in ni.index else "") for t in node_tickers}

    return {
        "nodes": node_tickers,
        "edges": edges,
        "sectors": sectors_map,
        "computed_at": _now(),
    }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


if __name__ == "__main__":
    update()
