import os
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from dotenv import load_dotenv # 👈 新增：用來讀取 .env 檔

# 載入環境變數 (確保抓得到 DISCORD_WEBHOOK)
load_dotenv()

# 設定路徑
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

FINRA_URL_TEMPLATE = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{}.txt"

# ==========================================
# 🦇 新增：Discord 推播函數 (暗池專屬文案)
# ==========================================
def send_to_discord(file_path):
    webhook_url = os.environ.get('DISCORD_WEBHOOK') 
    if not webhook_url:
        print("⚠️ 未設定 Discord Webhook，跳過傳送。")
        return
    if not os.path.exists(file_path): 
        print("⚠️ 找不到檔案，無法傳送至 Discord。")
        return
        
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            # 🌟 專屬文案修改：標明這是暗池雷達
            payload = {'content': f"🦇 **BamHI 廣域雷達：暗池異常資金掃描完畢**\n今日 Top 50 爆量標的與雙軌技術指標已出爐，請查收！"}
            response = requests.post(webhook_url, data=payload, files=files)
            
        if response.status_code in [200, 204]: 
            print("✅ Discord 戰報傳送成功！")
        else:
            print(f"❌ Discord 傳送失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print(f"❌ 傳送至 Discord 時發生錯誤: {e}")

# ==========================================
# 核心資料抓取與運算邏輯
# ==========================================
def get_valid_finra_dates(target_date, required_days=21):
    valid_dates = []
    current_date = target_date
    while len(valid_dates) < required_days:
        date_str = current_date.strftime("%Y%m%d")
        url = FINRA_URL_TEMPLATE.format(date_str)
        try:
            resp = requests.head(url, timeout=5)
            if resp.status_code == 200:
                valid_dates.append(current_date)
        except: pass
        current_date -= timedelta(days=1)
        if (target_date - current_date).days > 60: break
    return valid_dates

def fetch_finra_data(date_obj):
    date_str = date_obj.strftime("%Y%m%d")
    url = FINRA_URL_TEMPLATE.format(date_str)
    try:
        df = pd.read_csv(url, sep='|', storage_options={'User-Agent': 'Mozilla/5.0'})
        if 'TotalVolume' in df.columns:
            df = df[~df['Symbol'].str.contains(r'\W', na=False)]
            return df[['Symbol', 'TotalVolume', 'ShortVolume']]
    except: pass
    return pd.DataFrame()

def calculate_rsi(data, window=14):
    """計算 RSI 14"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_price_metrics(tickers):
    """使用 yfinance 抓取「趨勢」與「反彈」所需的雙軌技術指標"""
    print(f"📈 正在分析 {len(tickers)} 檔標的之技術型態...")
    data = []
    for t in tickers:
        try:
            ticker = yf.Ticker(t)
            hist = ticker.history(period="1y")
            if len(hist) < 200: continue # 排除上市不到一年的新股，確保指標準確
            
            latest_price = hist.iloc[-1]['Close']
            prev_close = hist.iloc[-2]['Close']
            
            # 計算均線與極值
            ma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            high_52w = hist['Close'].max()
            low_52w = hist['Close'].min()
            
            # 計算 RSI
            rsi_14 = calculate_rsi(hist['Close']).iloc[-1]
            
            data.append({
                'Ticker': t,
                'Price': round(latest_price, 2),
                'Chg%': round(((latest_price - prev_close) / prev_close) * 100, 2),
                # === 趨勢模板指標 (右側 VCP) ===
                'Above_MA200': 1 if latest_price > ma200 else 0,
                'Dist_52W_High%': round(((latest_price - high_52w) / high_52w) * 100, 2),
                # === 跌深反彈指標 (左側抄底) ===
                'Dist_MA200_%': round(((latest_price - ma200) / ma200) * 100, 2), # 看乖離率
                'Dist_52W_Low%': round(((latest_price - low_52w) / low_52w) * 100, 2), # 看是否剛脫離谷底
                'RSI_14': round(rsi_14, 2)
            })
        except: continue
    return pd.DataFrame(data)

def main():
    start_time = time.time()
    target_date = datetime.now()
    valid_dates = get_valid_finra_dates(target_date)
    
    if len(valid_dates) < 2: return
    
    print("🚀 啟動 FINRA 廣域雷達 (Top 50 爆量掃描)...")
    latest_date = valid_dates[0]
    history_dfs = [fetch_finra_data(d) for d in valid_dates[1:]]
    df_history = pd.concat(history_dfs)
    df_ma20 = df_history.groupby('Symbol')['TotalVolume'].mean().reset_index()
    df_ma20.rename(columns={'TotalVolume': 'MA20_Vol'}, inplace=True)
    
    df_latest = fetch_finra_data(latest_date)
    df_latest.rename(columns={'TotalVolume': 'Today_Vol', 'ShortVolume': 'Short_Vol'}, inplace=True)
    
    df_merged = pd.merge(df_latest, df_ma20[df_ma20['MA20_Vol'] >= 200000], on='Symbol', how='inner')
    df_merged['Surx'] = (df_merged['Today_Vol'] / df_merged['MA20_Vol']).round(2)
    df_merged['Short%'] = ((df_merged['Short_Vol'] / df_merged['Today_Vol']) * 100).round(2)
    
    df_top50 = df_merged.sort_values(by='Surx', ascending=False).head(50)
    
    print("🎯 正在套用雙軌策略濾網...")
    df_prices = get_price_metrics(df_top50['Symbol'].tolist())
    df_final = pd.merge(df_top50, df_prices, left_on='Symbol', right_on='Ticker')
    
    # 整理最終 CSV 欄位，分為 基礎資料 | 趨勢指標 | 反彈指標
    final_cols = [
        'Ticker', 'Price', 'Chg%', 'Surx', 'Short%', 
        'Above_MA200', 'Dist_52W_High%', 
        'Dist_MA200_%', 'Dist_52W_Low%', 'RSI_14'
    ]
    df_final = df_final[final_cols]
    
    output_path = os.path.join(DATA_DIR, 'darkpool_results.csv')
    df_final.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"🎉 任務完成！CSV 已儲存至: {output_path}")
    print(f"⏱️ 總耗時: {time.time() - start_time:.2f} 秒")
    
    # 👈 新增：腳本跑到最後，自動把剛存好的 CSV 送去 Discord
    send_to_discord(output_path)

if __name__ == "__main__":
    main()