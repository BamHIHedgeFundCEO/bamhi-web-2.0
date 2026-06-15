"""BamHI Quant API — FastAPI 入口 (§1.2)。

部署：Render Web Service
    uvicorn backend.main:app --host 0.0.0.0 --port 10000

各功能 router 在模組遷移時逐一掛上 (app.include_router(...))，
資料運算重用既有 data_engine / data_pipeline。
"""
import os

from dotenv import load_dotenv

# 先載入 backend/.env，再 import 會讀取環境變數的模組 (auth.py 在 import 時讀 secret)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.auth import get_current_user  # noqa: E402
from backend.routers import dark_pool, equity, macro, models, notes, screener, sector_rotation, sector_strength, world_sectors  # noqa: E402

app = FastAPI(title="BamHI Quant API", version="2.0.0")

# ── CORS (§1.2)：開發 localhost:5173 + 生產 Vercel domain ──
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_vercel_origin = os.getenv("FRONTEND_ORIGIN")  # 例：https://bamhi-quant.vercel.app
if _vercel_origin:
    ALLOWED_ORIGINS.append(_vercel_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Render 健康檢查 / 前端探活。"""
    return {"status": "ok", "service": "bamhi-quant-api"}


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    """驗證 JWT 串接是否正常的範例受保護端點。"""
    return {"user_id": user.get("sub"), "email": user.get("email")}


# ── 功能 router ──
app.include_router(dark_pool.router)
app.include_router(macro.router)
app.include_router(sector_strength.router)
app.include_router(world_sectors.router)
app.include_router(models.router)
app.include_router(sector_rotation.router)
app.include_router(equity.router)
app.include_router(notes.router)
app.include_router(screener.router)
