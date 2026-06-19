"""
data_pipeline/market/sentiment.py
負責抓取 AAII 散戶情緒與 S&P 500 對照數據 (包含超強 Excel 智慧解析)
"""
import pandas as pd
import requests
import yfinance as yf
import os
import io
# 設定資料路徑
DATA_DIR = "data"
SENTIMENT_FILE = os.path.join(DATA_DIR, "sentiment.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "AAII_History.xlsx") 

def get_aaii_latest():
    """從 AAII 官網抓取最新一週數據 (使用 undetected-chromedriver 繞過 Incapsula)"""
    url = "https://www.aaii.com/sentimentsurvey/sent_results"
    
    try:
        import undetected_chromedriver as uc
        from webdriver_manager.chrome import ChromeDriverManager
        import time

        print("      🤖 [Selenium] 啟動瀏覽器載入 AAII 頁面並嘗試繞過防火牆...")

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1,1")
        options.add_argument("--window-position=10000,10000")

        driver_path = ChromeDriverManager().install()
        driver = uc.Chrome(driver_executable_path=driver_path, options=options)
        driver.get(url)
        
        # 動態等待，直到網頁出現表格為止 (最多 25 秒)
        page_source = ""
        for _ in range(25):
            time.sleep(1)
            page_source = driver.page_source
            if "<table" in page_source.lower() or "reported date" in page_source.lower():
                break
                
        driver.quit()
        
        if "<table" not in page_source.lower() and "reported date" not in page_source.lower():
            print("      [Error] AAII 爬蟲失敗: 無法通過防火牆，請稍後重試。")
            return pd.DataFrame()
            
        tables = pd.read_html(io.StringIO(page_source), flavor='html5lib')
        df = tables[0].iloc[:, [0, 1, 2, 3]]
        df.columns = ['Date', 'Bullish', 'Neutral', 'Bearish']
        
        # 智慧補齊年份：AAII 網頁上的日期格式為 "May 6"（無年份），len("May 6")=5, len("Apr 29")=6
        current_year = pd.Timestamp.now().year
        
        def parse_aaii_date(d):
            d_str = str(d).strip()
            # 過濾標題列
            if d_str in ('Reported Date', 'nan', 'None', ''):
                return pd.NaT
            try:
                # 🔥 關鍵修正：先補年份，再解析（避免 pandas 對 "May 6" 丟出 Exception）
                if len(d_str) <= 6:  # "May 6"=5, "Apr 29"=6 → 這些沒有年份
                    d_str = f"{d_str} {current_year}"
                
                parsed = pd.to_datetime(d_str)
                
                # 若補完年份後是未來日期，代表是去年的資料
                if parsed > pd.Timestamp.now():
                    parsed = parsed.replace(year=current_year - 1)
                return parsed
            except:
                return pd.NaT
                
        df['Date'] = df['Date'].apply(parse_aaii_date)
        df = df.dropna(subset=['Date'])
        
        # 無條件清洗成數值（新版 pandas 可能是 string dtype，不能只靠 dtype==object 判斷）
        for col in ['Bullish', 'Neutral', 'Bearish']:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace('%', '', regex=False).str.strip(),
                errors='coerce',
            )
        df = df.dropna(subset=['Bullish', 'Bearish'])

        df['Spread'] = df['Bullish'] - df['Bearish']
        return df
        
    except Exception as e:
        print(f"      [Error] AAII 爬蟲失敗: {e}")
        return pd.DataFrame()


def update():
    """主更新函數：整合歷史檔 + 網路爬蟲 + S&P 500"""
    print("   ↳ 🐂🐻 [AAII Sentiment] 正在更新散戶情緒指標...")
    
    if os.path.exists(SENTIMENT_FILE):
        base_df = pd.read_csv(SENTIMENT_FILE, parse_dates=['Date'])
    elif os.path.exists(HISTORY_FILE):
        # 💡 [智慧解析] 容忍各種 Excel 格式
        try:
            # 讀取你的 Excel 檔
            base_df = pd.read_excel(HISTORY_FILE, engine='openpyxl')
            
            # 處理 Date 欄位名稱 (如果官方表頭叫 Reported Date，自動改名)
            if 'Reported Date' in base_df.columns:
                base_df = base_df.rename(columns={'Reported Date': 'Date'})
                
            base_df['Date'] = pd.to_datetime(base_df['Date'], errors='coerce')
            base_df = base_df.dropna(subset=['Date']) # 刪除沒有日期的無效行
            
            # 🔥 核心魔法：自動把 0.75 這種小數轉換成 75.0
            for col in ['Bullish', 'Neutral', 'Bearish']:
                if col in base_df.columns:
                    # 強制轉為數字，忽略無法轉換的文字
                    base_df[col] = pd.to_numeric(base_df[col], errors='coerce')
                    # 如果這欄的最大值小於或等於 1.5，代表它是百分比小數 (例如 0.75)
                    if base_df[col].max() <= 1.5:
                        base_df[col] = base_df[col] * 100
                        
            if 'Spread' not in base_df.columns and 'Bullish' in base_df.columns:
                base_df['Spread'] = base_df['Bullish'] - base_df['Bearish']
                
            # 只取我們要的欄位
            base_df = base_df[['Date', 'Bullish', 'Neutral', 'Bearish', 'Spread']]
            
        except Exception as e:
            print(f"      [Error] 讀取 Excel 失敗: {e}")
            base_df = pd.DataFrame(columns=['Date', 'Bullish', 'Neutral', 'Bearish', 'Spread'])
    else:
        print("      ⚠️ 警告：找不到 sentiment.csv 或 AAII_History.xlsx，將初始化空表")
        base_df = pd.DataFrame(columns=['Date', 'Bullish', 'Neutral', 'Bearish', 'Spread'])

    # 2. 抓取最新數據並合併
    new_df = get_aaii_latest()
    if not new_df.empty:
        cols = ['Date', 'Bullish', 'Neutral', 'Bearish', 'Spread']
        base_df = base_df[cols] if not base_df.empty else base_df
        new_df = new_df[cols]
        full_df = pd.concat([base_df, new_df]).drop_duplicates(subset=['Date'], keep='last').sort_values('Date')
    else:
        full_df = base_df

    if full_df.empty:
        return

    # 3. 重算 20 週均線
    full_df['Spread_MA20'] = full_df['Spread'].rolling(window=20).mean()

    # 4. 補上 S&P 500 收盤價
# 4. 補上 S&P 500 收盤價
    start_date = full_df['Date'].min()
    try:
        sp500 = yf.download("^GSPC", start=start_date, progress=False, auto_adjust=False)['Close']
        if not sp500.empty:
            if isinstance(sp500, pd.DataFrame):
                sp500 = sp500.iloc[:, 0]
            sp500 = sp500.reset_index()
            sp500.columns = ['Date', 'SP500_Price']
            
            # 🔥 修正 2：合併前先刪除舊有的 SP500_Price，避免欄位名稱衝突 (_x, _y)
            if 'SP500_Price' in full_df.columns:
                full_df = full_df.drop(columns=['SP500_Price'])

            full_df['Date'] = pd.to_datetime(full_df['Date']).astype('datetime64[us]')
            sp500['Date'] = pd.to_datetime(sp500['Date']).astype('datetime64[us]')

            full_df = pd.merge_asof(full_df.sort_values('Date'),
                                    sp500.sort_values('Date'),
                                    on='Date',
                                    direction='backward')
    except Exception as e:
        print(f"      [Error] S&P 500 下載失敗: {e}")
    # 5. 存檔
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # 存成系統要用的 CSV
    full_df.to_csv(SENTIMENT_FILE, index=False)
    
    # 🔥 自動回寫更新到使用者的 Excel 歷史檔案
    history_save_df = full_df[['Date', 'Bullish', 'Neutral', 'Bearish', 'Spread']].copy()
    history_save_df['Date'] = history_save_df['Date'].dt.strftime('%Y-%m-%d')
    # 這裡將數值轉換成小數點 (0.55 = 55%) 以符合手動輸入的習慣
    for col in ['Bullish', 'Neutral', 'Bearish']:
        history_save_df[col] = history_save_df[col] / 100.0
        
    history_save_df.to_excel(HISTORY_FILE, index=False, engine='openpyxl')
    
    print(f"   ✅ [AAII Sentiment] 儲存成功，最新日期: {full_df['Date'].iloc[-1].strftime('%Y-%m-%d')} (已自動同步至 Excel)")