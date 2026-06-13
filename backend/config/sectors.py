"""板塊追蹤清單與龍頭股設定。

重用專案根目錄的 sector_config.py（純資料、無 streamlit 依賴），
避免前後端與 pipeline 各自維護一份造成漂移。
"""
import os
import sys

# 確保能 import 到專案根目錄的 sector_config
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sector_config import SECTOR_LEADERS, TRACKED_SECTORS  # noqa: E402,F401
