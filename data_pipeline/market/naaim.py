"""
data_pipeline/market/naaim.py
負責抓取 NAAIM 機構經理人持倉指數，並與 S&P 500 對照
"""
import pandas as pd
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import os

DATA_DIR = "data"
NAAIM_FILE = os.path.join(DATA_DIR, "naaim.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "NAAIM_History.xlsx")

def get_naaim_latest():
    """從 NAAIM 官網爬取最新的 Excel 檔案連結並下載"""
    url = "https://naaim.org/programs/naaim-exposure-index/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        import io
        import os
        import time
        import glob
        
        # 建立專屬的暫存下載資料夾
        download_dir = os.path.abspath(os.path.join("data", "temp_naaim"))
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        else:
            # 清空舊檔案
            for f in glob.glob(os.path.join(download_dir, "*")):
                try: os.remove(f)
                except: pass

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox") # 必須加上這行，否則在 GitHub Actions 的 Linux 環境會崩潰
        chrome_options.add_argument("--disable-dev-shm-usage") # 解決 CI/CD 環境記憶體限制問題
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # 設定預設下載路徑 (這是繞過 WAF 最重要的一步！)
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        print("      🤖 [Selenium] 啟動瀏覽器載入 NAAIM 頁面...")
        driver.get(url)
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        xls_link = None
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if ('.xls' in href or '.xlsx' in href) and 'naaim' in href:
                xls_link = a['href']
                break
                
        if xls_link:
            print(f"      📥 [Selenium] 找到 Excel 連結，正在透過瀏覽器真實下載...")
            driver.get(xls_link)
            
            # 等待下載完成 (最多等 10 秒)
            downloaded_file = None
            for _ in range(10):
                time.sleep(1)
                files = glob.glob(os.path.join(download_dir, "*.xls*"))
                # 排除 .crdownload 暫存檔
                files = [f for f in files if not f.endswith('.crdownload')]
                if files:
                    downloaded_file = files[0]
                    break
            
            driver.quit()
            
            if downloaded_file:
                # 讀取本地端真正下載下來的 Excel，這樣就不會觸發 403 了
                df = pd.read_excel(downloaded_file)
                
                # 讀完後清理
                try: os.remove(downloaded_file)
                except: pass
                
                return df
            else:
                print("      [Error] Selenium 下載 Excel 超時失敗")
                return pd.DataFrame()
        else:
            driver.quit()
    except Exception as e:
        print(f"      [Error] NAAIM 爬蟲失敗: {e}")
    return pd.DataFrame()

def update():
    print("   ↳ 👔 [NAAIM Exposure] 正在更新機構經理人情緒指標...")
    
    # 1. 讀取基礎數據
    if os.path.exists(NAAIM_FILE):
        base_df = pd.read_csv(NAAIM_FILE, parse_dates=['Date'])
    elif os.path.exists(HISTORY_FILE):
        try:
            base_df = pd.read_excel(HISTORY_FILE, engine='openpyxl')
            
            # 👇 2. 加上防呆：如果讀出來的 Excel 是全空的，直接給空表
            if base_df.empty:
                base_df = pd.DataFrame(columns=['Date', 'NAAIM'])
            else:
                # 智慧解析欄位
                date_col = next((c for c in base_df.columns if 'date' in str(c).lower()), base_df.columns[0])
                naaim_col = next((c for c in base_df.columns if 'naaim' in str(c).lower() or 'exposure' in str(c).lower()), base_df.columns[1])
                
                base_df = base_df.rename(columns={date_col: 'Date', naaim_col: 'NAAIM'})
                base_df['Date'] = pd.to_datetime(base_df['Date'], errors='coerce')
                base_df['NAAIM'] = pd.to_numeric(base_df['NAAIM'], errors='coerce')
                base_df = base_df.dropna(subset=['Date', 'NAAIM'])[['Date', 'NAAIM']]
                
        except Exception as e:
            print(f"      [Error] 讀取 Excel 失敗: {e}")
            base_df = pd.DataFrame(columns=['Date', 'NAAIM'])
    # 2. 抓取最新數據並合併
    new_df = get_naaim_latest()
    if not new_df.empty:
        try:
            date_col = next((c for c in new_df.columns if 'date' in str(c).lower()), new_df.columns[0])
            naaim_col = next((c for c in new_df.columns if 'naaim' in str(c).lower() or 'exposure' in str(c).lower()), new_df.columns[1])
            new_df = new_df.rename(columns={date_col: 'Date', naaim_col: 'NAAIM'})
            new_df['Date'] = pd.to_datetime(new_df['Date'], errors='coerce')
            new_df['NAAIM'] = pd.to_numeric(new_df['NAAIM'], errors='coerce')
            new_df = new_df.dropna(subset=['Date', 'NAAIM'])[['Date', 'NAAIM']]
            
            full_df = pd.concat([base_df, new_df]).drop_duplicates(subset=['Date'], keep='last').sort_values('Date')
        except:
            full_df = base_df
    else:
        full_df = base_df

    if full_df.empty:
        return

    # 3. 計算 MA20
    full_df['NAAIM_MA20'] = full_df['NAAIM'].rolling(window=20).mean()

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
            
            # 🔥 修正 2：合併前先刪除舊有的 SP500_Price
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
    full_df.to_csv(NAAIM_FILE, index=False)
    
    # 🔥 自動回寫更新到使用者的 Excel 歷史檔案
    # 確保只存需要的欄位，避免把 SP500_Price 存進去弄髒手動輸入的格式
    history_save_df = full_df[['Date', 'NAAIM']].copy()
    history_save_df['Date'] = history_save_df['Date'].dt.strftime('%Y-%m-%d')
    history_save_df.to_excel(HISTORY_FILE, index=False, engine='openpyxl')
    
    print(f"   ✅ [NAAIM Exposure] 儲存成功，最新日期: {full_df['Date'].iloc[-1].strftime('%Y-%m-%d')} (已自動同步至 Excel)")