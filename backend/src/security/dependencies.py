"""FastAPI Authentication Dependencies"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.src.config import settings
from backend.src.database.connection import get_db
from backend.src.models.orm import User
from backend.src.security.jwt import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Retrieve current user from JWT token if valid."""
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn")
    user = db.query(User).filter(User.id == str(user_id), User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Tài khoản không khả dụng")
    return user


def require_current_user(
    user: Optional[User] = Depends(get_current_user)
) -> User:
    """Enforce authentication requirement on protected routes."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bạn cần đăng nhập để thực hiện thao tác này",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
