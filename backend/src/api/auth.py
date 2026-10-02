"""Authentication Endpoints: Local Register/Login, Google OAuth Login & Callback"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.src.database.connection import get_db
from backend.src.models.orm import User
from backend.src.models.schemas import UserRegister, UserLogin, GoogleAuthRequest, TokenResponse, UserProfile
from backend.src.security.jwt import create_access_token
from backend.src.security.dependencies import require_current_user
from backend.src.services.auth_service import (
    register_local_user, login_local_user, authenticate_google_user,
    handle_google_callback
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Đăng ký tài khoản mới bằng Email & Mật khẩu"""
    user = register_local_user(db, data)
    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        provider="local"
    )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Đăng nhập bằng Email & Mật khẩu"""
    user = login_local_user(db, data.email, data.password)
    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        provider="local"
    )


@router.post("/google", response_model=TokenResponse)
def google_auth(data: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Đăng nhập / Đăng ký trực tiếp với Google User Info (JSON payload)"""
    user, is_new = authenticate_google_user(db, data)
    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        provider="google"
    )


@router.get("/google/login")
def google_login_redirect():
    import secrets
    from backend.src.config import settings
    from backend.src.services.google_identity import authorization_url
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(authorization_url(state))
    response.set_cookie("merrec_google_state", state, max_age=600, httponly=True,
                        secure=settings.FRONTEND_URL.startswith("https://"), samesite="lax")
    return response


@router.get("/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    import secrets
    from urllib.parse import urlencode
    from backend.src.config import settings
    expected = request.cookies.get("merrec_google_state", "")
    if not code or not state or not expected or not secrets.compare_digest(state, expected):
        raise HTTPException(400, "Phiên đăng nhập Google không hợp lệ. Vui lòng thử lại.")
    result = handle_google_callback(db, code, state)
    # Fragment keeps the bearer token out of HTTP URLs, referrers and access logs.
    response = RedirectResponse(settings.FRONTEND_URL.rstrip("/") + "/login#" + urlencode({
        "token": result["access_token"],
    }))
    response.delete_cookie("merrec_google_state")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


from backend.src.models.orm import AuthAccount

@router.get("/me", response_model=UserProfile)
def get_me(user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    """Lấy thông tin tài khoản đang đăng nhập"""
    google_acc = db.query(AuthAccount).filter(
        AuthAccount.user_id == str(user.id),
        AuthAccount.provider == "google"
    ).first()
    
    local_acc = db.query(AuthAccount).filter(
        AuthAccount.user_id == str(user.id),
        AuthAccount.provider == "local"
    ).first()

    provider = "google" if (google_acc and not (local_acc and local_acc.password_hash)) else "local"

    profile = UserProfile.model_validate(user)
    profile.provider = provider
    return profile
