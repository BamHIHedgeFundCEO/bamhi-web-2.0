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
from datetime import datetime, timedelta
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
        # 🟢 【台股模式 - 雲端專業量化版：FMP (英文簡介) + FinMind (台股財報)】
        symbol = ticker_upper.split('.')[0]
        info['sector'] = '台灣市場 (TWSE)'
        
        # 💡 從歷史 K 線拿最新收盤價，這是計算估值指標的核心！
        current_price = float(hist['Close'].iloc[-1]) if not hist.empty else 0
        info['currentPrice'] = current_price

        # ==========================================
        # A. 質性簡介 (FMP 拿深度英文介紹，雲端安全)
        # ==========================================
        try:
            profile_url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker_upper}&apikey={FMP_API_KEY}"
            p_resp = requests.get(profile_url, timeout=10).json()
            if p_resp:
                p = p_resp[0] if isinstance(p_resp, list) else p_resp
                info['shortName'] = p.get('companyName', ticker_upper)
                info['industry'] = p.get('industry', 'N/A')
                info['longBusinessSummary'] = p.get('description', '暫無公司業務介紹。')
                info['fullTimeEmployees'] = p.get('fullTimeEmployees', 'N/A')
        except Exception as e:
            print(f"FMP 基本資料抓取失敗: {e}")

        # ==========================================
        # B. 財務數據 (FinMind API - 專為量化交易設計，不怕雲端封鎖)
        # ==========================================

        # 設定抓取近一年的資料，確保能精準抓到最新一季
        start_date = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
        fm_url = "https://api.finmindtrade.com/api/v4/data"

        try:
            print(f"🚀 啟動 FinMind 專業量化引擎抓取 {symbol} 財報...")
            
            # 1. 抓取綜合損益表
            is_params = {"dataset": "TaiwanStockFinancialStatements", "data_id": symbol, "start_date": start_date}
            is_resp = requests.get(fm_url, params=is_params, timeout=15).json()
            
            # 2. 抓取資產負債表 (算 PB, ROE, 市值用)
            bs_params = {"dataset": "TaiwanStockBalanceSheet", "data_id": symbol, "start_date": start_date}
            bs_resp = requests.get(fm_url, params=bs_params, timeout=15).json()

            # --- 處理損益表 ---
            if is_resp.get("msg") == "success" and len(is_resp.get("data", [])) > 0:
                df_is = pd.DataFrame(is_resp["data"])
                
                # 找出最新一季的日期，並把資料轉成字典方便讀取
                latest_date_is = df_is['date'].max()
                df_is_latest = df_is[df_is['date'] == latest_date_is]
                is_dict = dict(zip(df_is_latest['type'], df_is_latest['value']))

                rev = is_dict.get('OperatingRevenue', 0)
                gp = is_dict.get('GrossProfit', 0)
                ni = is_dict.get('NetIncome', 0)
                eps = is_dict.get('EPS', 0)

                # 算本益比 P/E
                if eps > 0 and current_price > 0:
                    info['trailingPE'] = current_price / (eps * 4)

                # 建立 UI 專用的 DataFrame
                col_name = f"{latest_date_is} (FinMind)"
                tw_fin = pd.DataFrame(index=[
                    '營收 (Revenue)', '營收年增率 (YoY)', '毛利率 (Gross Margin)', '淨利率 (Net Margin)',
                    '單季 EPS', '營運現金流 (Operating CF)', '自由現金流 (Free CF)'
                ], columns=[col_name])

                tw_fin.loc['營收 (Revenue)', col_name] = rev
                tw_fin.loc['營收年增率 (YoY)', col_name] = None 
                tw_fin.loc['毛利率 (Gross Margin)', col_name] = gp / rev if rev else 0
                tw_fin.loc['淨利率 (Net Margin)', col_name] = ni / rev if rev else 0
                tw_fin.loc['單季 EPS', col_name] = eps
                income_stmt = tw_fin

                # --- 處理資產負債表 ---
                if bs_resp.get("msg") == "success" and len(bs_resp.get("data", [])) > 0:
                    df_bs = pd.DataFrame(bs_resp["data"])
                    latest_date_bs = df_bs['date'].max()
                    df_bs_latest = df_bs[df_bs['date'] == latest_date_bs]
                    bs_dict = dict(zip(df_bs_latest['type'], df_bs_latest['value']))

                    equity = bs_dict.get('TotalEquity', 0)
                    bps = bs_dict.get('BookValuePerShare', 0)
                    ordinary_shares = bs_dict.get('OrdinaryShares', 0) # 普通股股本

                    # 算 P/B
                    if bps > 0 and current_price > 0:
                        info['priceToBook'] = current_price / bps

                    # 算 ROE (單季淨利 / 總權益)
                    if equity > 0 and ni != 0:
                        info['returnOnEquity'] = ni / equity

                    # 算市值：普通股本(金額) / 10 = 股數。市值 = 股數 * 股價
                    if ordinary_shares > 0 and current_price > 0:
                        info['marketCap'] = (ordinary_shares / 10) * current_price

        except Exception as e:
            print(f"FinMind 量化引擎抓取失敗: {e}")
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