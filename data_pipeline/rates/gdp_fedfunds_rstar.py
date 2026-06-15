"""
data_pipeline/rates/gdp_fedfunds_rstar.py
功能：自動下載 名目GDP、聯邦基金利率、r-star 並存成 gdp_fedfunds_rstar.csv
"""
import pandas as pd
import os

from data_pipeline.rates._fred import fetch

def update():
    print("   ↳ 🌐 [Macro Data] 正在同步：名目GDP成長率、聯邦基金利率、r-star...")

    try:
        # 1. 抓取 FRED 數據 (GDP 與 FEDFUNDS) — 改用直接下載 FRED CSV
        df_fred = fetch(["GDP", "FEDFUNDS"]).set_index("date")

        # 因為加入了月頻率的 FEDFUNDS，DataFrame 會變成月頻率
        # 必須先 forward fill GDP，再計算 YoY (12個月 = 12 periods)
        df_fred["GDP"] = df_fred["GDP"].ffill()
        df_fred["GDP_Growth"] = df_fred["GDP"].pct_change(periods=12) * 100
        
        # 2. 抓取 紐約聯銀 r-star (黃線要用的數據) - 使用獨立 try-except 避免 WAF 阻擋導致全盤失敗
        try:
            # 最新正確的紐約聯銀 r-star 數據隱藏網址 (舊的 hp_model_estimates.xlsx 已經變成 404 死檔了！)
            r_url = "https://www.newyorkfed.org/medialibrary/media/research/economists/williams/data/Holston_Laubach_Williams_current_estimates.xlsx"
            
            import urllib.request
            import io
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }
            req = urllib.request.Request(r_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                excel_data = response.read()
                
            # 新版的檔案沒有 'United States' 工作表，而是 'HLW Estimates'
            df_raw = pd.read_excel(io.BytesIO(excel_data), sheet_name='HLW Estimates', header=None, engine='openpyxl')
            
            # 動態尋找 Date 與 r-star 的欄位索引
            date_col_idx = -1
            date_row_idx = -1
            for r in range(10):
                for c in range(df_raw.shape[1]):
                    if 'date' in str(df_raw.iat[r, c]).lower():
                        date_row_idx = r
                        date_col_idx = c
                        break
                if date_row_idx != -1: break
                
            rstar_col_idx = -1
            for r in range(10):
                for c in range(df_raw.shape[1]):
                    val = str(df_raw.iat[r, c]).lower()
                    if 'natural rate' in val or 'r*' in val or 'r-star' in val:
                        # 在 Natural Rate 的標題附近尋找 US
                        for dr in [0, 1, 2]:
                            for dc in [0, 1, 2, 3]:
                                if r + dr < df_raw.shape[0] and c + dc < df_raw.shape[1]:
                                    sub_val = str(df_raw.iat[r+dr, c+dc]).lower().strip()
                                    if sub_val == 'us' or sub_val == 'united states':
                                        rstar_col_idx = c + dc
                                        break
                            if rstar_col_idx != -1: break
                    if rstar_col_idx != -1: break
                if rstar_col_idx != -1: break
                
            if date_col_idx == -1 or rstar_col_idx == -1:
                print("   ↳ 🔍 [Debug] 無法定位 Date 或 US r-star 欄位，前四列資料為：")
                for i in range(4): print(f"       {df_raw.iloc[i].tolist()}")
                raise Exception("Excel 格式解析失敗，找不到 Date 或 r-star 欄位")
                
            # 萃取資料並轉型
            df_rstar = pd.DataFrame()
            df_rstar['date'] = df_raw.iloc[date_row_idx+1:, date_col_idx]
            df_rstar['r_star'] = df_raw.iloc[date_row_idx+1:, rstar_col_idx]
            
            df_rstar = df_rstar.dropna(subset=['date', 'r_star'])
            df_rstar['date'] = pd.to_datetime(df_rstar['date'], errors='coerce')
            df_rstar['r_star'] = pd.to_numeric(df_rstar['r_star'], errors='coerce')
            df_rstar = df_rstar.dropna()
            
            # 數據對齊合併
            df_fred = df_fred.reset_index().rename(columns={'DATE': 'date'})
            df_final = pd.merge(df_fred, df_rstar, on='date', how='outer')
            df_final = df_final[['date', 'GDP_Growth', 'FEDFUNDS', 'r_star']].dropna(subset=['GDP_Growth'])
            
        except Exception as r_err:
            print(f"   ⚠️ [Macro Data] r-star 下載失敗 (可能被防爬蟲阻擋): {r_err}")
            print("   ⚠️ [Macro Data] 系統將自動降級，僅儲存名目 GDP 與聯邦基金利率數據...")
            df_fred = df_fred.reset_index().rename(columns={'DATE': 'date'})
            df_final = df_fred[['date', 'GDP_Growth', 'FEDFUNDS']].dropna(subset=['GDP_Growth'])
        
        # 3. 存成一目瞭然的 CSV
        if not os.path.exists("data"): os.makedirs("data")
        df_final.to_csv("data/gdp_fedfunds_rstar.csv", index=False)
        print("   ✅ [Macro Data] 儲存成功 data/gdp_fedfunds_rstar.csv")
        
    except Exception as e:
        print(f"   ❌ [Macro Data] 核心 FRED 數據下載失敗: {e}")

if __name__ == "__main__":
    update()
