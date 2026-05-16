import uvicorn
from fastapi import FastAPI, HTTPException
import pandas as pd
import json

from data_engine.market.sector_engine import calculate_sector_metrics, scan_vcp_candidates
from sector_config import TRACKED_SECTORS

app = FastAPI(title="BamHI Quant Sector API")

@app.get("/")
def root():
    return {"message": "BamHI Quant Sector API is running!"}

@app.get("/api/sector/{sector_name}")
def get_sector_metrics(sector_name: str, period: str = "1y"):
    """
    計算板塊指標與 RRG 數據 (等同原本的 calculate_sector_metrics)
    """
    tickers = TRACKED_SECTORS.get(sector_name, [])
    if not tickers:
        raise HTTPException(status_code=404, detail="Sector not found")

    try:
        # df_sector 是板塊綜合指標, df_c 是個別成分股收盤價
        df_sector, df_c = calculate_sector_metrics(tickers, period=period)
        
        if df_sector is None or df_sector.empty:
            raise HTTPException(status_code=400, detail="Failed to calculate sector metrics")

        # FastAPI 無法直接回傳 Pandas DataFrame，需轉成 dict 或 JSON
        # reset_index 以保留日期資訊
        df_sector = df_sector.reset_index()
        # 日期轉字串避免 JSON 序列化錯誤
        if 'Date' in df_sector.columns:
            df_sector['Date'] = df_sector['Date'].dt.strftime('%Y-%m-%d')
            
        return {"data": df_sector.to_dict(orient="records")}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vcp/{sector_name}")
def get_vcp_candidates(sector_name: str, period: str = "1y"):
    """
    執行 VCP 掃描 (等同原本的 scan_vcp_candidates)
    """
    tickers = TRACKED_SECTORS.get(sector_name, [])
    if not tickers:
        raise HTTPException(status_code=404, detail="Sector not found")

    try:
        df_vcp = scan_vcp_candidates(tickers, period=period)
        if df_vcp.empty:
            return {"data": []}
            
        # 處理可能的 NaN 值 (JSON 不支援 NaN)
        df_vcp = df_vcp.fillna(0)
        return {"data": df_vcp.to_dict(orient="records")}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
