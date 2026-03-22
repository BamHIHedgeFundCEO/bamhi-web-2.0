"""
data_engine/equity.py
負責處理單一個股 (Tearsheet) 的即時資料抓取、指標計算與繪圖
架構：YFinance (歷史股價) + Financial Modeling Prep (基本面與財報 - 最新 Stable API)
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
    雙引擎抓取：YF 負責股價與均線，FMP 負責基本面與財報
    """
    # ==========================================
    # 引擎 1：YFinance (專職負責 K 線與技術分析)
    # ==========================================
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period, interval=interval)
    except Exception:
        hist = pd.DataFrame()
        
    if hist.empty:
        return None 

    # 🎯 技術指標計算 (MA 與 海龜突破訊號)
    ma_windows = [5, 10, 20, 60, 120, 240]
    for ma in ma_windows:
        hist[f'MA_{ma}'] = hist['Close'].rolling(window=ma).mean()

    hist['Max_20'] = hist['High'].shift(1).rolling(window=20).max()
    hist['Min_20'] = hist['Low'].shift(1).rolling(window=20).min()
    hist['Signal_Up'] = (hist['Close'] > hist['Max_20']) & (hist['Close'].shift(1) <= hist['Max_20'].shift(1))
    hist['Signal_Down'] = (hist['Close'] < hist['Min_20']) & (hist['Close'].shift(1) >= hist['Min_20'].shift(1))

    # ==========================================
    # 引擎 2：FMP API (你找出的最新 Stable 秘密通道)
    # ==========================================
    info = {}
    income_stmt = pd.DataFrame()
    
    # 防止 API 請求失敗的保護機制
    try:
        # A. 抓取公司基本資料 (使用你親自測試成功的 Stable Endpoint)
        profile_url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={FMP_API_KEY}"
        profile_resp = requests.get(profile_url).json()
        
        # 新版 stable API 回傳的可能是一個 list，也可能直接是一個字典，我們做個兼容防呆
        if profile_resp:
            p = profile_resp[0] if isinstance(profile_resp, list) else profile_resp
            
            info['shortName'] = p.get('companyName', ticker)
            info['currentPrice'] = p.get('price', 0)
            info['previousClose'] = p.get('price', 0) - p.get('changes', 0)
            info['marketCap'] = p.get('mktCap', 0)
            info['sector'] = p.get('sector', 'N/A')
            info['industry'] = p.get('industry', 'N/A')
            info['fullTimeEmployees'] = p.get('fullTimeEmployees', 'N/A')
            info['longBusinessSummary'] = p.get('description', '暫無公司業務介紹。')

        # B. 抓取關鍵財務指標 (Key Metrics TTM)
        metrics_url = f"https://financialmodelingprep.com/stable/key-metrics-ttm?symbol={ticker}&apikey={FMP_API_KEY}"
        metrics_resp = requests.get(metrics_url).json()
        
        if metrics_resp:
            m = metrics_resp[0] if isinstance(metrics_resp, list) else metrics_resp
            info['trailingPE'] = m.get('peRatioTTM', 'N/A')
            info['priceToBook'] = m.get('pbRatioTTM', 'N/A')
            info['returnOnEquity'] = m.get('roeTTM', 0)
            info['debtToEquity'] = m.get('debtToEquityTTM', 0) * 100 

        # C. 抓取年度損益表 (Income Statement)
        is_url = f"https://financialmodelingprep.com/stable/income-statement?symbol={ticker}&limit=4&apikey={FMP_API_KEY}"
        is_resp = requests.get(is_url).json()
        
        if is_resp:
            # 確保它是 list 型態才能轉成 DataFrame
            is_data = is_resp if isinstance(is_resp, list) else [is_resp]
            df_is = pd.DataFrame(is_data)
            
            if 'date' in df_is.columns:
                df_is.set_index('date', inplace=True)
                df_is = df_is.T 
                
                mapping = {
                    'revenue': 'Total Revenue',
                    'grossProfit': 'Gross Profit',
                    'operatingIncome': 'Operating Income',
                    'netIncome': 'Net Income'
                }
                df_is.rename(index=mapping, inplace=True)
                income_stmt = df_is
                
                try:
                    latest_col = income_stmt.columns[0]
                    rev = income_stmt.loc['Total Revenue', latest_col]
                    info['grossMargins'] = income_stmt.loc['Gross Profit', latest_col] / rev if rev else 0
                    info['profitMargins'] = income_stmt.loc['Net Income', latest_col] / rev if rev else 0
                except Exception:
                    pass

    except Exception as e:
        print(f"⚠️ FMP API 抓取失敗: {e}")

    # 如果 FMP 偶爾出錯，用 YFinance 歷史價格當最後防線
    if 'currentPrice' not in info and not hist.empty:
        info['currentPrice'] = float(hist['Close'].iloc[-1])
        info['previousClose'] = float(hist['Close'].iloc[-2]) if len(hist) > 1 else float(hist['Close'].iloc[-1])
    
    return {
        "info": info,
        "history": hist,
        "income_stmt": income_stmt
    }

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