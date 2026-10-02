"""Authentication Service: JWT Tokens, Password Hashing & Google OAuth"""

import datetime
from typing import Optional
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.model.database import get_db
from app.model.models import User, AuthAccount
from app.model.schemas import UserRegister, GoogleAuthRequest

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(user_id: str, expires_delta: Optional[datetime.timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.datetime.now(datetime.timezone.utc)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        return str(payload.get("sub"))
    except Exception:
        return None


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == str(user_id), User.is_active == True).first()


def require_current_user(
    user: Optional[User] = Depends(get_current_user)
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bạn cần đăng nhập để thực hiện thao tác này",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def register_local_user(db: Session, data: UserRegister) -> User:
    existing_user = db.query(User).filter(User.email == data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được sử dụng. Vui lòng đăng nhập hoặc dùng email khác."
        )

    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        is_active=True,
        is_verified=False
    )
    db.add(user)
    db.flush()

    auth_acc = AuthAccount(
        user_id=str(user.id),
        provider="local",
        provider_email=data.email.lower(),
        password_hash=hash_password(data.password)
    )
    db.add(auth_acc)
    db.commit()
    db.refresh(user)
    return user


def login_local_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower(), User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác"
        )
    
    auth_acc = db.query(AuthAccount).filter(
        AuthAccount.user_id == str(user.id),
        AuthAccount.provider == "local"
    ).first()

    if not auth_acc or not auth_acc.password_hash or not verify_password(password, auth_acc.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác"
        )

    return user


def authenticate_google_user(db: Session, data: GoogleAuthRequest) -> User:
    google_email = data.email or "google_user@gmail.com"
    google_email = google_email.lower()
    google_id = data.google_id or "google-sub-placeholder-12345"

    user = db.query(User).filter(User.email == google_email).first()
    if not user:
        user = User(
            email=google_email,
            full_name=data.full_name or google_email.split("@")[0],
            avatar_url=data.avatar_url or "/avatar-default.png",
            is_active=True,
            is_verified=True
        )
        db.add(user)
        db.flush()

    auth_acc = db.query(AuthAccount).filter(
        AuthAccount.user_id == str(user.id),
        AuthAccount.provider == "google"
    ).first()

    if not auth_acc:
        auth_acc = AuthAccount(
            user_id=str(user.id),
            provider="google",
            provider_account_id=google_id,
            provider_email=google_email
        )
        db.add(auth_acc)

    db.commit()
    db.refresh(user)
    return user
