try:
  import pandas as pd
  import yfinance as yf
  from data_engine.market.sector_engine import calculate_sector_metrics, scan_vcp_candidates
  print('Testing...')
  metrics, vols = calculate_sector_metrics(['RKLB', 'PL', 'LUNR'])
  print('Success')
except Exception as e:
  import traceback
  traceback.print_exc()
