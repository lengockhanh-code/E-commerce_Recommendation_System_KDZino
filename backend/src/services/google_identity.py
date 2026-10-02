"""Verified Google OIDC identity. Never accept browser-supplied email as proof."""

import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException

from backend.src.config import settings

_keys = {}
_keys_expire = 0


def verify_google_token(token, nonce=None):
    global _keys, _keys_expire
    if not token or not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(401, "Thiếu thông tin xác thực Google")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise ValueError("algorithm")
        if time.monotonic() >= _keys_expire or header.get("kid") not in _keys:
            with httpx.Client(timeout=5) as client:
                response = client.get("https://www.googleapis.com/oauth2/v3/certs")
                response.raise_for_status()
                _keys = {key["kid"]: jwt.PyJWK.from_dict(key).key for key in response.json()["keys"]}
                _keys_expire = time.monotonic() + 3600
        claims = jwt.decode(token, _keys[header["kid"]], algorithms=["RS256"],
                            audience=settings.GOOGLE_CLIENT_ID,
                            options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        if claims["iss"] not in ("https://accounts.google.com", "accounts.google.com"):
            raise ValueError("issuer")
        if claims.get("email_verified") is not True or not claims.get("email"):
            raise ValueError("unverified email")
        if nonce is not None and not secrets.compare_digest(claims.get("nonce", ""), nonce):
            raise ValueError("nonce")
        return claims
    except httpx.HTTPError:
        raise HTTPException(503, "Google tạm thời không khả dụng. Vui lòng thử lại.") from None
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(401, "Thông tin xác thực Google không hợp lệ") from None


def authorization_url(state):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Đăng nhập Google chưa được cấu hình")
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code", "scope": "openid email profile",
        "state": state, "nonce": state, "prompt": "select_account",
    })


def exchange_code(code, state):
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
            if response.status_code != 200:
                raise HTTPException(401, "Google từ chối đăng nhập. Vui lòng thử lại.")
            return verify_google_token(response.json().get("id_token"), state)
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Không thể kết nối Google. Vui lòng thử lại.") from None
