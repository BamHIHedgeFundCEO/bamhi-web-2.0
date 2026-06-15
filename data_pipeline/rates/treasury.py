"""
data_pipeline/rates/treasury.py
負責抓取美國公債殖利率 (2Y / 10Y) -> 存成 data/rates.csv

資料來源改為 **美國財政部 Treasury.gov 每日殖利率曲線 CSV**：
- FRED 的 fredgraph.csv 端點已對程式化存取逾時/封鎖（本機與 GitHub Actions 皆讀不到），
  且 pandas_datareader 又與新版 pandas 不相容。
- Treasury.gov 是 FRED DGS 系列的原始權威來源（DGS = CMT），免 API key、可靠。

並改為「合併既有歷史」而非整檔覆寫，單次抓取異常不會清空或讓資料凍結。
"""
import datetime as dt
import io
import os

import pandas as pd
import requests

# {year} 會帶入西元年；該端點回傳該年度所有交易日的殖利率曲線
TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (BamHI-Quant data pipeline)"}
RATES_PATH = os.path.join("data", "rates.csv")


def _fetch_year(year, retries=3, timeout=60):
    """抓取某一年度的 Treasury.gov 每日殖利率 CSV，連續失敗則 raise。"""
    url = TREASURY_URL.format(year=year)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            return pd.read_csv(io.StringIO(resp.text))
        except Exception as e:  # noqa: BLE001 - 重試後仍失敗則往外拋
            last_err = e
            print(f"   ⚠️ [Treasury] 第 {attempt}/{retries} 次抓取 {year} 失敗: {e}")
    raise RuntimeError(f"Treasury.gov {year} 連續 {retries} 次失敗: {last_err}")


def update():
    print("   ↳ 📉 [Treasury] 正在下載公債殖利率 (US Treasury)...")
    year = dt.datetime.now().year
    raw = _fetch_year(year)

    # 也抓前一年，避免年初當年資料過少而漏接（前一年抓不到不致命）
    try:
        raw = pd.concat([_fetch_year(year - 1), raw], ignore_index=True)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ [Treasury] 前一年度資料略過: {e}")

    # Treasury.gov 欄位：Date, "1 Mo", ..., "2 Yr", ..., "10 Yr", ...
    df = raw.rename(columns={"Date": "date", "2 Yr": "DGS2", "10 Yr": "DGS10"})
    df = df[["date", "DGS10", "DGS2"]].copy()
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y", errors="coerce")
    df["DGS10"] = pd.to_numeric(df["DGS10"], errors="coerce")
    df["DGS2"] = pd.to_numeric(df["DGS2"], errors="coerce")
    df = df.dropna(subset=["date", "DGS10", "DGS2"])
    df["Spread"] = df["DGS10"] - df["DGS2"]
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    fresh = df[["date", "DGS10", "DGS2", "Spread"]]

    # 合併既有歷史：以新抓的為準，但保留舊資料（含 1980 年起的長歷史）
    if os.path.exists(RATES_PATH):
        old = pd.read_csv(RATES_PATH)
        fresh = (
            pd.concat([old, fresh])
            .drop_duplicates("date", keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )

    if fresh.empty:
        raise RuntimeError("[Treasury] 合併後資料為空，拒絕覆寫 rates.csv")

    os.makedirs("data", exist_ok=True)
    fresh.to_csv(RATES_PATH, index=False)
    print(f"   ✅ [Treasury] 儲存成功 {RATES_PATH}（{len(fresh)} 列，最新 {fresh['date'].iloc[-1]}）")


if __name__ == "__main__":
    update()
