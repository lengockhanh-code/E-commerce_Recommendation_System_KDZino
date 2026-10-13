"""Verified Google OIDC identity. Never accept browser-supplied email as proof."""

import json
import logging
import secrets
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlencode

import certifi
import httpx
import jwt
from fastapi import HTTPException

from backend.src.config import settings

logger = logging.getLogger(__name__)

_keys = {}
_keys_expire = 0


def _get_ssl_context():
    try:
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _fetch_google_certs():
    global _keys, _keys_expire
    certs_url = "https://www.googleapis.com/oauth2/v3/certs"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) MerRec/1.0",
        "Accept": "application/json",
    }

    # 1. Try httpx first
    try:
        with httpx.Client(timeout=10, headers=headers) as client:
            resp = client.get(certs_url)
            if resp.status_code == 200:
                certs_data = resp.json()
                _keys = {key["kid"]: jwt.PyJWK.from_dict(key).key for key in certs_data.get("keys", [])}
                _keys_expire = time.monotonic() + 3600
                return
    except Exception as exc:
        logger.warning("Failed to fetch Google certs via httpx: %s", exc)

    # 2. Fallback to urllib with certifi SSL context
    try:
        req = urllib.request.Request(certs_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=_get_ssl_context()) as response:
            certs_data = json.loads(response.read().decode("utf-8"))
            _keys = {key["kid"]: jwt.PyJWK.from_dict(key).key for key in certs_data.get("keys", [])}
            _keys_expire = time.monotonic() + 3600
            return
    except Exception as exc:
        logger.error("Failed to fetch Google certs via urllib: %s", exc)
        raise HTTPException(503, "Google tạm thời không khả dụng. Vui lòng thử lại.") from None


def verify_google_token(token, nonce=None):
    global _keys, _keys_expire
    if not token or not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(401, "Thiếu thông tin xác thực Google")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise ValueError("algorithm")
        if time.monotonic() >= _keys_expire or header.get("kid") not in _keys:
            _fetch_google_certs()
        claims = jwt.decode(token, _keys[header["kid"]], algorithms=["RS256"],
                            audience=settings.GOOGLE_CLIENT_ID,
                            options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        if claims["iss"] not in ("https://accounts.google.com", "accounts.google.com"):
            raise ValueError(f"invalid issuer: {claims.get('iss')}")
        if str(claims.get("email_verified")).lower() not in ("true", "1") or not claims.get("email"):
            raise ValueError(f"unverified email: {claims.get('email_verified')}")
        if nonce is not None and claims.get("nonce") and not secrets.compare_digest(claims.get("nonce", ""), nonce):
            raise ValueError("nonce mismatch")
        return claims
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Google token verification failed: %s (type=%s)", exc, type(exc).__name__)
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
    data_dict = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    encoded_data = urllib.parse.urlencode(data_dict).encode("utf-8")

    endpoints = [
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/oauth2/v4/token",
    ]

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) MerRec/1.0",
        "Accept": "application/json",
    }

    last_err = None

    for token_url in endpoints:
        # 1. Try httpx first
        try:
            with httpx.Client(timeout=15, headers=headers) as client:
                resp = client.post(token_url, data=data_dict)
                if resp.status_code == 200:
                    payload = resp.json()
                    return verify_google_token(payload.get("id_token"), state)
                elif resp.status_code in (400, 401, 403):
                    logger.warning("Google token exchange returned status %s from %s: %s", resp.status_code, token_url, resp.text[:200])
                    raise HTTPException(401, "Google từ chối đăng nhập. Vui lòng thử lại.")
        except HTTPException:
            raise
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.warning("httpx connection failed to %s: %s", token_url, exc)
            last_err = exc

        # 2. Fallback to urllib with certifi SSL context
        try:
            req = urllib.request.Request(token_url, data=encoded_data, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=_get_ssl_context()) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return verify_google_token(payload.get("id_token"), state)
        except HTTPException:
            raise
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            logger.warning("Google token exchange HTTPError %s from %s: %s", err.code, token_url, err_body[:200])
            raise HTTPException(401, "Google từ chối đăng nhập. Vui lòng thử lại.") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("urllib connection failed to %s: %s", token_url, exc)
            last_err = exc

    logger.error("All Google token exchange attempts failed: %s", last_err)
    raise HTTPException(503, "Không thể kết nối Google. Vui lòng thử lại.") from None
