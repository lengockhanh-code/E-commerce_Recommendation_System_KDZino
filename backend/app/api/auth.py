"""Authentication API Router: Local Login, Registration & Google OAuth"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.schemas import UserRegister, UserLogin, GoogleAuthRequest, TokenResponse, UserOut
from app.services.auth_service import (
    register_local_user,
    login_local_user,
    authenticate_google_user,
    create_access_token,
    get_current_user,
    require_current_user
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Đăng ký tài khoản bằng Email & Mật khẩu"""
    user = register_local_user(db, data)
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Đăng nhập bằng Email & Mật khẩu"""
    user = login_local_user(db, data.email, data.password)
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/google", response_model=TokenResponse)
def google_auth(data: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Đăng nhập / Đăng ký qua Google OAuth 2.0.
    Chấp nhận Google ID Token hoặc email/sub thông tin tài khoản Google.
    Mã cấu hình Google Client ID & Secret nằm trong settings/config.py.
    """
    user = authenticate_google_user(db, data)
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserOut)
def me(user=Depends(require_current_user)):
    """Lấy thông tin tài khoản đang đăng nhập"""
    return user
