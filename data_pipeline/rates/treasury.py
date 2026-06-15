"""
data_pipeline/rates/treasury.py
負責抓取美國公債利率 (FRED DGS10/DGS2) -> 存成 data/rates.csv

改用直接下載 FRED CSV（見 _fred.py），取代與新版 pandas 不相容的 pandas_datareader。
並改為「合併既有歷史」而非整檔覆寫，單次抓取異常不會清空或讓資料凍結。
"""
import os

import pandas as pd

from data_pipeline.rates._fred import fetch

RATES_PATH = os.path.join("data", "rates.csv")


def update():
    print("   ↳ 📉 [Treasury] 正在下載公債殖利率 (FRED)...")
    df = fetch(["DGS10", "DGS2"])
    df = df.dropna(subset=["DGS10", "DGS2"]).copy()
    df["Spread"] = df["DGS10"] - df["DGS2"]
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    fresh = df[["date", "DGS10", "DGS2", "Spread"]]

    # 合併既有歷史：以新抓的為準，但保留舊資料，避免單次失敗清空或回補不足
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
