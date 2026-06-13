"""Supabase JWT 驗證 (§1.3)。

支援兩種簽章模式：
  1. 新版非對稱金鑰 (ES256 / RS256)：從專案 JWKS 公鑰端點驗證（推薦）。
  2. 舊版對稱金鑰 (HS256)：用 SUPABASE_JWT_SECRET 共享密鑰驗證（fallback）。

依 token header 的 alg 自動選擇。將 get_current_user 作為相依注入到需登入的路由。
"""
import os
import time

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

# 後端用：你的 Supabase 專案網址，例 https://abcdefgh.supabase.co
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
# 舊版 HS256 共享密鑰 (若專案仍用 legacy JWT secret 才需要)
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
# Supabase 簽發的 token aud 預設為 "authenticated"
JWT_AUDIENCE = "authenticated"

# ⚠️ 僅供本地開發預覽：設 AUTH_DISABLED=true 可略過 JWT 驗證。
# 生產環境 (Render) 千萬不要設定此變數。
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "").lower() == "true"

_bearer = HTTPBearer(auto_error=not AUTH_DISABLED)

# ── JWKS 公鑰快取 ──
_JWKS_CACHE: dict = {"ts": 0, "keys": {}}
_JWKS_TTL = 3600


def _jwks_url() -> str:
    return f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"


def _get_jwks(force: bool = False) -> dict:
    """抓取並快取 JWKS（kid → JWK dict）。"""
    if not force and _JWKS_CACHE["keys"] and time.time() - _JWKS_CACHE["ts"] < _JWKS_TTL:
        return _JWKS_CACHE["keys"]
    if not SUPABASE_URL:
        return {}
    try:
        resp = requests.get(_jwks_url(), timeout=10)
        resp.raise_for_status()
        keys = {k["kid"]: k for k in resp.json().get("keys", []) if "kid" in k}
        _JWKS_CACHE.update(ts=time.time(), keys=keys)
        return keys
    except Exception as e:
        print(f"[auth] JWKS 取得失敗: {e}")
        return _JWKS_CACHE["keys"]


def _unauthorized(detail: str):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "")

    if alg == "HS256":
        if not SUPABASE_JWT_SECRET:
            raise _unauthorized("後端未設定 SUPABASE_JWT_SECRET（HS256 模式）")
        return jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience=JWT_AUDIENCE)

    # 非對稱 (ES256 / RS256)：用 JWKS 公鑰
    kid = header.get("kid")
    keys = _get_jwks()
    jwk = keys.get(kid)
    if jwk is None:  # kid 可能輪替過，強制刷新一次
        jwk = _get_jwks(force=True).get(kid)
    if jwk is None:
        raise _unauthorized("找不到對應的簽章公鑰 (kid)，請確認 SUPABASE_URL 設定正確")
    return jwt.decode(token, jwk, algorithms=[alg], audience=JWT_AUDIENCE)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """驗證 JWT 並回傳 payload（含 sub=user_id、email）。失敗則 401。"""
    if AUTH_DISABLED:
        return {"sub": "dev-local", "email": "dev@local"}

    try:
        payload = _verify(credentials.credentials)
    except JWTError as exc:
        raise _unauthorized(f"無效或過期的憑證: {exc}") from exc

    if not payload.get("sub"):
        raise _unauthorized("憑證缺少使用者識別")
    return payload
