"""交易筆記 API (對應 Streamlit notes 套件 + render_dynamic_chart 下方筆記區)。

重用專案根目錄的 notes 套件（純 Python 回傳 Markdown 字串，無 streamlit 依賴）。
"""
import os
import sys

from fastapi import APIRouter, Depends, Query

from backend.auth import get_current_user

# 確保能 import 到根目錄的 notes 套件
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import notes as notes_pkg  # noqa: E402

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("")
def get_note(
    category: str = Query(..., description="rates / market / equity ..."),
    module: str = Query(..., description="treasury / breadth / naaim / strength / world_sectors ..."),
    ticker: str = Query("", description="部分筆記會依代碼客製"),
    _user: dict = Depends(get_current_user),
):
    """回傳該指標的 Markdown 交易筆記；若無對應檔案，has_note=False。"""
    content = notes_pkg.fetch_note(category, module, ticker)
    has_note = not content.lstrip().startswith("⚠️")
    return {"category": category, "module": module, "has_note": has_note, "markdown": content}
