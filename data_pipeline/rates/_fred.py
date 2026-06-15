"""
data_pipeline/rates/_fred.py
共用 FRED 抓取工具。

直接下載 FRED 的 fredgraph.csv，取代 `pandas_datareader`——後者已與新版
pandas 不相容（`deprecate_kwarg() missing 1 required positional argument`），
import 時就會炸，連帶讓整個 rates 部門靜默失效、資料凍結。
"""
import io

import pandas as pd
import requests

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_HEADERS = {"User-Agent": "Mozilla/5.0 (BamHI-Quant data pipeline)"}


def fetch(series, start="1980-01-01", retries=3, timeout=60):
    """抓取一或多個 FRED series。

    回傳 DataFrame：欄位 = ['date'] + 各 series；缺值（FRED 以 '.' 表示）轉 NaN。
    連續 `retries` 次失敗會 raise RuntimeError——讓呼叫端能察覺、而非默默吞掉。
    """
    if isinstance(series, str):
        series = [series]
    params = {"id": ",".join(series), "cosd": start}
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(FRED_CSV_URL, params=params, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            # 第一欄是日期（FRED 近期改用 observation_date，舊版為 DATE）
            df = df.rename(columns={df.columns[0]: "date"})
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            for col in series:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df.dropna(subset=["date"])
        except Exception as e:  # noqa: BLE001 - 重試後仍失敗則往外拋
            last_err = e
            print(f"   ⚠️ [FRED] 第 {attempt}/{retries} 次抓取 {series} 失敗: {e}")
    raise RuntimeError(f"FRED 抓取 {series} 連續 {retries} 次失敗: {last_err}")
