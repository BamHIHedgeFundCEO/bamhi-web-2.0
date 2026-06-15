"""
data_pipeline/rates/_fred.py
共用 FRED 抓取工具 —— 改用 FRED **官方 API**（api.stlouisfed.org）。

背景：
- 舊版用 pandas_datareader，已與新版 pandas 不相容（import 即炸）。
- 接著試 fredgraph.csv（graph 主機），但該端點對程式化存取逾時/封鎖
  （本機與 GitHub Actions 皆 read timeout）。
- 官方 API 主機 api.stlouisfed.org 正常可達，只需一組免費 API key。

key 來源：環境變數 `FRED_API_KEY`（GitHub Actions 設為 secret）。
申請：https://fredaccount.stlouisfed.org/apikeys
"""
import os

import pandas as pd
import requests

FRED_API = "https://api.stlouisfed.org/fred/series/observations"
_HEADERS = {"User-Agent": "Mozilla/5.0 (BamHI-Quant data pipeline)"}


def fetch(series, start="1980-01-01", api_key=None, retries=3, timeout=30):
    """用 FRED 官方 API 抓一或多個 series，回傳 DataFrame：欄位 = ['date'] + 各 series。

    缺值（FRED 以 '.' 表示）轉 NaN。缺 key 或連續 `retries` 次失敗會 raise，
    讓呼叫端能察覺、而非默默吞掉。
    """
    api_key = api_key or os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 FRED_API_KEY（請設環境變數 / GitHub secret）")
    if isinstance(series, str):
        series = [series]

    frames = []
    for sid in series:
        params = {
            "series_id": sid,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start,
        }
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(FRED_API, params=params, headers=_HEADERS, timeout=timeout)
                resp.raise_for_status()
                obs = resp.json().get("observations", [])
                df = pd.DataFrame(obs)[["date", "value"]].rename(columns={"value": sid})
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df[sid] = pd.to_numeric(df[sid], errors="coerce")
                frames.append(df)
                break
            except Exception as e:  # noqa: BLE001 - 重試後仍失敗則往外拋
                last_err = e
                print(f"   ⚠️ [FRED] {sid} 第 {attempt}/{retries} 次失敗: {e}")
        else:
            raise RuntimeError(f"FRED API 抓 {sid} 連續 {retries} 次失敗: {last_err}")

    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="date", how="outer")
    return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
