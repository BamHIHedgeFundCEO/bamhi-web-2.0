"""
data_engine/equity.py
負責處理單一個股 (Tearsheet) 的即時資料抓取、指標計算與繪圖
"""
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

def fetch_stock_profile(ticker: str, period: str = "2y", interval: str = "1d"):
    """
    抓取個股資料，並計算均線與突破訊號
    """
    stock = yf.Ticker(ticker)
    
    # 1. 抓取歷史價格 (加入動態期間與 K線級別)
    try:
        hist = stock.history(period=period, interval=interval)
    except Exception:
        hist = pd.DataFrame()
        
    if hist.empty:
        return None 

    # 🎯 核心量化計算區塊
    # A. 計算 6 條常用均線 (MA)
    ma_windows = [5, 10, 20, 60, 120, 240]
    for ma in ma_windows:
        hist[f'MA_{ma}'] = hist['Close'].rolling(window=ma).mean()

    # B. 計算前 20 期的最高價與最低價 (不包含當天，所以要 shift(1))
    hist['Max_20'] = hist['High'].shift(1).rolling(window=20).max()
    hist['Min_20'] = hist['Low'].shift(1).rolling(window=20).min()

    # C. 產生三角形訊號 (為了畫面乾淨，我們設定「第一天剛突破」時才畫三角形)
    # 向上突破：今天收盤大於前20期高點，且昨天還沒大於
    hist['Signal_Up'] = (hist['Close'] > hist['Max_20']) & (hist['Close'].shift(1) <= hist['Max_20'].shift(1))
    # 向下跌破：今天收盤小於前20期低點，且昨天還沒小於
    hist['Signal_Down'] = (hist['Close'] < hist['Min_20']) & (hist['Close'].shift(1) >= hist['Min_20'].shift(1))

    # 2. 抓取基本面 (防呆機制)
    try:
        info = stock.info
    except Exception:
        info = {} 

    if 'currentPrice' not in info and 'regularMarketPrice' not in info:
        if len(hist) >= 2:
            info['currentPrice'] = float(hist['Close'].iloc[-1])
            info['previousClose'] = float(hist['Close'].iloc[-2])
    
    # 3. 抓取財務報表
    try:
        income_stmt = stock.income_stmt
    except Exception:
        income_stmt = pd.DataFrame()
    
    return {
        "info": info,
        "history": hist,
        "income_stmt": income_stmt
    }

def plot_candlestick(hist: pd.DataFrame, ticker: str, interval: str = "1d"):
    """
    繪製帶有均線與訊號的 K 線圖
    """
    if hist.empty:
        return None
        
    fig = go.Figure()

    # 👇 解決方案：用 Pandas 事先幫每一根 K 線組裝好全中文的提示文字
    hover_text = hist.apply(
        lambda row: f"<b>日期: {row.name.strftime('%Y-%m-%d %H:%M') if pd.notna(row.name) else ''}</b><br><br>"
                    f"開盤價: $ {row['Open']:.2f}<br>"
                    f"最高價: $ {row['High']:.2f}<br>"
                    f"最低價: $ {row['Low']:.2f}<br>"
                    f"收盤價: $ {row['Close']:.2f}",
        axis=1
    )

    # 1. 畫 K 線主圖
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'], high=hist['High'],
        low=hist['Low'], close=hist['Close'],
        name="K線",
        hovertext=hover_text,  # 改用所有版本都支援的 hovertext
        hoverinfo="text"       # 告訴 Plotly 只顯示我們自訂好的中文字
    ))

    # 2. 畫出 6 條均線 (配色使用高質感的霓虹色系)
    ma_colors = {
        5: '#f59e0b',    # 黃色
        10: '#3b82f6',   # 藍色
        20: '#ec4899',   # 粉紅
        60: '#10b981',   # 綠色
        120: '#8b5cf6',  # 紫色
        240: '#ef4444'   # 紅色
    }
    
    for ma, color in ma_colors.items():
        if f'MA_{ma}' in hist.columns:
            # 隱藏那些還沒算出來的 NaN 值
            plot_df = hist.dropna(subset=[f'MA_{ma}'])
            fig.add_trace(go.Scatter(
                x=plot_df.index, y=plot_df[f'MA_{ma}'],
                mode='lines', name=f'{ma}MA',
                line=dict(color=color, width=1.2),
                hoverinfo='skip' # 滑鼠移過去不顯示，保持畫面乾淨
            ))

    # 3. 標記突破/跌破的三角形訊號
    up_signals = hist[hist['Signal_Up']]
    down_signals = hist[hist['Signal_Down']]

    if not up_signals.empty:
        fig.add_trace(go.Scatter(
            x=up_signals.index, 
            y=up_signals['Low'] * 0.96, # 畫在最低價下方一點點
            mode='markers', name='突破20期高',
            marker=dict(symbol='triangle-up', size=14, color='#34d399', line=dict(width=1, color='black'))
        ))

    if not down_signals.empty:
        fig.add_trace(go.Scatter(
            x=down_signals.index, 
            y=down_signals['High'] * 1.04, # 畫在最高價上方一點點
            mode='markers', name='跌破20期低',
            marker=dict(symbol='triangle-down', size=14, color='#ef4444', line=dict(width=1, color='black'))
        ))

    # 4. 根據時間級別，自動隱藏非交易時間
    breaks = [dict(bounds=["sat", "mon"])] # 永遠隱藏六日
    if interval == "1h":
        # 美股時間：16:00 收盤 ~ 隔天 09:30 開盤 (這段時間隱藏)
        breaks.append(dict(bounds=[16, 9.5], pattern="hour"))

    fig.update_xaxes(rangebreaks=breaks)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis_rangeslider_visible=False,
        height=600, # 把圖表拉高一點，容納均線
        title=f"{ticker} 價格走勢與訊號",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig