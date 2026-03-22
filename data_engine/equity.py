"""
data_engine/equity.py
負責處理單一個股 (Tearsheet) 的即時資料抓取、指標計算與繪圖
架構：YFinance (歷史股價) + Financial Modeling Prep (基本面與財報 - 最新 Stable API)
"""
"""
data_engine/equity.py
負責處理單一個股 (Tearsheet) 的即時資料抓取、指標計算與繪圖
架構：YFinance (股價) + FMP (美股財報) + TWSE 官方 API (台股財報 - 絕對防封鎖)
"""
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import requests
import streamlit as st

# 🔑 你的專屬 FMP API 金鑰
FMP_API_KEY = "29epqrFbGsBfasHJHyU7fnFT8CcUdeaF"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_profile(ticker: str, period: str = "2y", interval: str = "1d"):
    """
    BamHI 終極大腦：硬派白嫖流，台股財報全面改用 TWSE 官方端點！
    """
    ticker_upper = ticker.upper()
    is_taiwan_stock = ticker_upper.endswith(".TW") or ticker_upper.endswith(".TWO")

    # ==========================================
    # 引擎 1：YFinance (統一負責 K 線與技術分析 - 雲端安全)
    # ==========================================
    stock = yf.Ticker(ticker_upper)
    try:
        hist = stock.history(period=period, interval=interval)
    except Exception:
        hist = pd.DataFrame()
        
    if hist.empty: return None 

    ma_windows = [5, 10, 20, 60, 120, 240]
    for ma in ma_windows:
        hist[f'MA_{ma}'] = hist['Close'].rolling(window=ma).mean()

    hist['Max_20'] = hist['High'].shift(1).rolling(window=20).max()
    hist['Min_20'] = hist['Low'].shift(1).rolling(window=20).min()
    hist['Signal_Up'] = (hist['Close'] > hist['Max_20']) & (hist['Close'].shift(1) <= hist['Max_20'].shift(1))
    hist['Signal_Down'] = (hist['Close'] < hist['Min_20']) & (hist['Close'].shift(1) >= hist['Min_20'].shift(1))

    # ==========================================
    # 引擎 2：智能分流財務萃取
    # ==========================================
    info = {}
    income_stmt = pd.DataFrame()
    finance_source = None

    if is_taiwan_stock:
        # 🟢 【台股模式 - 終極乾淨完全體】
        symbol = ticker_upper.split('.')[0]
        is_otc = ticker_upper.endswith(".TWO")
        info['sector'] = '台灣市場 (TWSE)'
        
        # 💡 拿最新收盤價算指標
        current_price = float(hist['Close'].iloc[-1]) if not hist.empty else 0
        info['currentPrice'] = current_price

        # ==========================================
        # A. 質性簡介 (FMP 拿深度簡介與員工數)
        # ==========================================
        try:
            profile_url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker_upper}&apikey={FMP_API_KEY}"
            p_resp = requests.get(profile_url, timeout=10).json()
            if p_resp:
                p = p_resp[0] if isinstance(p_resp, list) else p_resp
                info['shortName'] = p.get('companyName', ticker_upper)
                info['industry'] = p.get('industry', 'N/A')
                info['longBusinessSummary'] = p.get('description', '暫無公司業務介紹。')
                info['website'] = p.get('website', 'N/A')
                info['fullTimeEmployees'] = p.get('fullTimeEmployees', 'N/A')
        except Exception as e:
            print(f"FMP 基本資料抓取失敗: {e}")

        # 共用標頭
        import json
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Accept": "application/json"
        }

        # ==========================================
        # B. 算「市值」(TWSE t187ap03) - 絕對不蓋掉簡介！
        # ==========================================
        try:
            twse_prof_url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_O" if is_otc else "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
            p_resp = requests.get(twse_prof_url, headers=headers, timeout=15)
            if p_resp.status_code == 200:
                p_data = json.loads(p_resp.text)
                comp = next((item for item in p_data if str(item.get('公司代號', '')).strip() == symbol), None)
                if comp:
                    capital_str = str(comp.get('實收資本額', '0')).replace(',', '').strip()
                    try:
                        shares = float(capital_str) / 10 
                        if current_price > 0:
                            info['marketCap'] = shares * current_price
                    except: pass
        except Exception as e:
            print(f"TWSE 資本額抓取失敗: {e}")

        # ==========================================
        # C. 算「P/E」與財報 (TWSE t187ap06)
        # ==========================================
        ni = 0 # 宣告給下面的 ROE 使用
        try:
            twse_fin_url = "https://openapi.twse.com.tw/v1/opendata/t187ap06_O_ci" if is_otc else "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci"
            resp = requests.get(twse_fin_url, headers=headers, timeout=20)
            if resp.status_code == 200:
                twse_f_resp = json.loads(resp.text)
                fin_data = next((item for item in twse_f_resp if str(item.get('公司代號', '')).strip() == symbol), None)
                if fin_data:
                    clean_data = {str(k).replace(' ', '').replace('　', '').replace('（', '(').replace('）', ')'): v for k, v in fin_data.items()}
                    def safe_float(val_str):
                        try: return float(str(val_str).replace(',', '').strip())
                        except: return 0.0

                    rev = safe_float(clean_data.get('營業收入', 0))
                    gp = safe_float(clean_data.get('營業毛利(毛損)', 0))
                    ni = safe_float(clean_data.get('本期淨利(淨損)', 0))
                    eps = safe_float(clean_data.get('基本每股盈餘(元)', 0))

                    if eps > 0 and current_price > 0:
                        info['trailingPE'] = current_price / (eps * 4)

                    year = clean_data.get('年度', '最新')
                    quarter = clean_data.get('季別', '季')
                    col_name = f"民國{year}年 Q{quarter}"

                    tw_fin = pd.DataFrame(index=[
                        '營收 (Revenue)', '營收年增率 (YoY)', '毛利率 (Gross Margin)', '淨利率 (Net Margin)',
                        '單季 EPS', '營運現金流 (Operating CF)', '自由現金流 (Free CF)'
                    ], columns=[col_name])

                    tw_fin.loc['營收 (Revenue)', col_name] = rev
                    tw_fin.loc['毛利率 (Gross Margin)', col_name] = gp / rev if rev else 0
                    tw_fin.loc['淨利率 (Net Margin)', col_name] = ni / rev if rev else 0
                    tw_fin.loc['單季 EPS', col_name] = eps
                    income_stmt = tw_fin
        except Exception as e:
            print(f"TWSE 損益表抓取失敗: {e}")

        # ==========================================
        # D. 算「P/B」與「ROE」(TWSE t187ap07)
        # ==========================================
        try:
            twse_bs_url = "https://openapi.twse.com.tw/v1/opendata/t187ap07_O_ci" if is_otc else "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci"
            bs_resp = requests.get(twse_bs_url, headers=headers, timeout=15)
            if bs_resp.status_code == 200:
                bs_data = json.loads(bs_resp.text)
                comp_bs = next((item for item in bs_data if str(item.get('公司代號', '')).strip() == symbol), None)
                if comp_bs:
                    c_bs = {str(k).replace(' ', '').replace('　', '').replace('（', '(').replace('）', ')'): v for k, v in comp_bs.items()}
                    bps = float(str(c_bs.get('每股參考淨值', '0')).replace(',', '').strip() or 0)
                    
                    # 💡 ROE 容錯機制：政府的「權益」名稱五花八門
                    equity_str = c_bs.get('權益總計', c_bs.get('權益總額', c_bs.get('歸屬於母公司業主之權益', '0')))
                    equity = float(str(equity_str).replace(',', '').strip() or 0)
                    
                    if bps > 0 and current_price > 0:
                        info['priceToBook'] = current_price / bps
                    if equity > 0 and ni != 0:
                        info['returnOnEquity'] = ni / equity
        except Exception as e:
            print(f"TWSE 資產負債表抓取失敗: {e}")

        # ==========================================
        # E. FMP 備援機制
        # ==========================================
        if income_stmt.empty:
            print(f"⚠️ TWSE 無財務數據，啟動 FMP 備援...")
            try:
                is_url = f"https://financialmodelingprep.com/stable/income-statement?symbol={ticker_upper}&period=quarter&limit=5&apikey={FMP_API_KEY}"
                cf_url = f"https://financialmodelingprep.com/stable/cash-flow-statement?symbol={ticker_upper}&period=quarter&limit=4&apikey={FMP_API_KEY}"
                is_resp = requests.get(is_url, timeout=10).json()
                cf_resp = requests.get(cf_url, timeout=10).json()

                if is_resp and cf_resp:
                    df_is = pd.DataFrame(is_resp if isinstance(is_resp, list) else [is_resp])
                    df_cf = pd.DataFrame(cf_resp if isinstance(cf_resp, list) else [cf_resp])
                    
                    if not df_is.empty and not df_cf.empty:
                        df_is.set_index('date', inplace=True)
                        df_cf.set_index('date', inplace=True)
                        if len(df_is) >= 5: df_is['revenue_YoY'] = df_is['revenue'].pct_change(periods=-4)
                        else: df_is['revenue_YoY'] = None
                            
                        df_combined = pd.concat([df_is.head(4), df_cf.head(4)], axis=1).T
                        mapping = {'revenue': '營收 (Revenue)', 'revenue_YoY': '營收年增率 (YoY)', 'grossProfitRatio': '毛利率 (Gross Margin)', 'netIncomeRatio': '淨利率 (Net Margin)', 'eps': '單季 EPS', 'operatingCashFlow': '營運現金流 (Operating CF)', 'freeCashFlow': '自由現金流 (Free CF)'}
                        available_cols = [c for c in mapping.keys() if c in df_combined.index]
                        df_mapped = df_combined.loc[available_cols].rename(index=mapping)
                        
                        for row in ['營收 (Revenue)', '營運現金流 (Operating CF)', '自由現金流 (Free CF)']:
                            if row in df_mapped.index:
                                df_mapped.loc[row] = df_mapped.loc[row].apply(lambda x: float(x) / 1000 if pd.notna(x) else None)
                        income_stmt = df_mapped
            except Exception as e: print(f"FMP 備援失敗: {e}")
    else:
        # 🔵 【美股模式 - 保持 FMP 完美萃取 4 季與 8 大指標】
        try:
            profile_url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker_upper}&apikey={FMP_API_KEY}"
            p_resp = requests.get(profile_url, timeout=10).json()
            if p_resp:
                p = p_resp[0] if isinstance(p_resp, list) else p_resp
                info['shortName'] = p.get('companyName', ticker_upper)
                info['longBusinessSummary'] = p.get('description', '暫無公司業務介紹。')
                info['website'] = p.get('website', 'N/A')
                info['marketCap'] = p.get('mktCap', 0)

            metrics_url = f"https://financialmodelingprep.com/stable/key-metrics-ttm?symbol={ticker_upper}&apikey={FMP_API_KEY}"
            m_resp = requests.get(metrics_url, timeout=10).json()
            if m_resp:
                m = m_resp[0] if isinstance(m_resp, list) else m_resp
                info['trailingPE'] = m.get('peRatioTTM', 'N/A')

            is_url = f"https://financialmodelingprep.com/stable/income-statement?symbol={ticker_upper}&period=quarter&limit=5&apikey={FMP_API_KEY}"
            cf_url = f"https://financialmodelingprep.com/stable/cash-flow-statement?symbol={ticker_upper}&period=quarter&limit=4&apikey={FMP_API_KEY}"
            is_resp = requests.get(is_url, timeout=10).json()
            cf_resp = requests.get(cf_url, timeout=10).json()

            if is_resp and cf_resp:
                df_is = pd.DataFrame(is_resp if isinstance(is_resp, list) else [is_resp])
                df_cf = pd.DataFrame(cf_resp if isinstance(cf_resp, list) else [cf_resp])
                
                if not df_is.empty and not df_cf.empty:
                    df_is.set_index('date', inplace=True)
                    df_cf.set_index('date', inplace=True)
                    if len(df_is) >= 5:
                        df_is['revenue_YoY'] = df_is['revenue'].pct_change(periods=-4)
                    else:
                        df_is['revenue_YoY'] = None
                        
                    df_combined = pd.concat([df_is.head(4), df_cf.head(4)], axis=1).T
                    mapping = {
                        'revenue': '營收 (Revenue)', 'revenue_YoY': '營收年增率 (YoY)',
                        'grossProfitRatio': '毛利率 (Gross Margin)', 'netIncomeRatio': '淨利率 (Net Margin)',
                        'eps': '單季 EPS', 'operatingCashFlow': '營運現金流 (Operating CF)',
                        'freeCashFlow': '自由現金流 (Free CF)'
                    }
                    available_cols = [c for c in mapping.keys() if c in df_combined.index]
                    income_stmt = df_combined.loc[available_cols].rename(index=mapping)
                    finance_source = "FMP (Financial Modeling Prep)"

        except Exception as e:
            print(f"FMP API 抓取失敗: {e}")

    # 防呆補上收盤價
    if 'currentPrice' not in info and not hist.empty:
        info['currentPrice'] = float(hist['Close'].iloc[-1])
        info['previousClose'] = float(hist['Close'].iloc[-2]) if len(hist) > 1 else float(hist['Close'].iloc[-1])
    
    return {"info": info, "history": hist, "income_stmt": income_stmt, "finance_source": finance_source}

# (下方 plot_candlestick 函數保持不變...)
# ==========================================
# 繪圖引擎 (完全保留我們做好的高質感 K 線與中文設定)
# ==========================================
def plot_candlestick(hist: pd.DataFrame, ticker: str, interval: str = "1d"):
    if hist.empty:
        return None
        
    fig = go.Figure()

    hover_text = hist.apply(
        lambda row: f"<b>日期: {row.name.strftime('%Y-%m-%d %H:%M') if pd.notna(row.name) else ''}</b><br><br>"
                    f"開盤價: $ {row['Open']:.2f}<br>"
                    f"最高價: $ {row['High']:.2f}<br>"
                    f"最低價: $ {row['Low']:.2f}<br>"
                    f"收盤價: $ {row['Close']:.2f}",
        axis=1
    )

    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'], high=hist['High'],
        low=hist['Low'], close=hist['Close'],
        name="K線",
        hovertext=hover_text,  
        hoverinfo="text"       
    ))

    ma_colors = { 5: '#f59e0b', 10: '#3b82f6', 20: '#ec4899', 60: '#10b981', 120: '#8b5cf6', 240: '#ef4444' }
    
    for ma, color in ma_colors.items():
        if f'MA_{ma}' in hist.columns:
            plot_df = hist.dropna(subset=[f'MA_{ma}'])
            fig.add_trace(go.Scatter(
                x=plot_df.index, y=plot_df[f'MA_{ma}'],
                mode='lines', name=f'{ma}MA',
                line=dict(color=color, width=1.2),
                hoverinfo='skip' 
            ))

    up_signals = hist[hist['Signal_Up']]
    down_signals = hist[hist['Signal_Down']]

    if not up_signals.empty:
        fig.add_trace(go.Scatter(
            x=up_signals.index, y=up_signals['Low'] * 0.96,
            mode='markers', name='突破20期高',
            marker=dict(symbol='triangle-up', size=14, color='#34d399', line=dict(width=1, color='black'))
        ))

    if not down_signals.empty:
        fig.add_trace(go.Scatter(
            x=down_signals.index, y=down_signals['High'] * 1.04,
            mode='markers', name='跌破20期低',
            marker=dict(symbol='triangle-down', size=14, color='#ef4444', line=dict(width=1, color='black'))
        ))

    breaks = [dict(bounds=["sat", "mon"])] 
    if interval == "1h":
        breaks.append(dict(bounds=[16, 9.5], pattern="hour"))

    fig.update_xaxes(rangebreaks=breaks)
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0), xaxis_rangeslider_visible=False,
        height=600, title=f"{ticker} 價格走勢與訊號",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig