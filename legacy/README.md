# legacy/ — 舊版 Streamlit 遺留

2026-07-04 自根目錄移入。經全量引用盤點確認：`backend/`、`data_pipeline/`、`update_data.py`、render.yaml、GitHub Actions 均**不引用**此目錄任何內容。

| 內容 | 原位置 | 說明 |
|------|--------|------|
| `app.py` | 根目錄 | 舊 Streamlit 入口 |
| `api.py` | 根目錄 | 舊 API 層 |
| `config.py`、`config/` | 根目錄 | 舊設定（活代碼用的是根目錄 `sector_config.py` 與 `backend/config/`） |
| `views/`、`components/` | 根目錄 | 舊 Streamlit 頁面與元件 |
| `data_engine/` | 根目錄 | 舊資料讀取層（含 `@st.cache_data`）；新邏輯已重寫進 `backend/services/` |
| `bamhi/` | 根目錄 | Landing page 設計交接稿（frontend 已重建完成） |
| `assets/` | 根目錄 | 舊 Streamlit CSS |

**規則**：新功能不要 import 這裡的任何東西。只作歷史對照。確認一段時間沒人想念之後，整個目錄可刪。
