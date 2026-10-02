"""Authentication Service: User Registration, Login & Google OAuth Flow"""

import urllib.parse
from typing import Optional
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.src.config import settings
from backend.src.models.orm import User, AuthAccount, generate_uuid
from backend.src.models.schemas import UserRegister, GoogleAuthRequest
from backend.src.security.hashing import hash_password, verify_password
from backend.src.security.jwt import create_access_token


def register_local_user(db: Session, data: UserRegister) -> User:
    existing_user = db.query(User).filter(User.email == data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được sử dụng. Vui lòng đăng nhập hoặc dùng email khác."
        )

    user_id = generate_uuid()
    user = User(
        id=user_id,
        email=data.email.lower(),
        full_name=data.full_name,
        is_active=True,
        is_verified=False
    )
    db.add(user)

    auth_acc = AuthAccount(
        id=generate_uuid(),
        user_id=user_id,
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


def change_user_password(db: Session, user: User, old_pwd: Optional[str], new_pwd: str) -> dict:
    auth_acc = db.query(AuthAccount).filter(
        AuthAccount.user_id == str(user.id),
        AuthAccount.provider == "local"
    ).first()

    if not auth_acc:
        # User registered via Google -> Create a local auth account so they can also use email + password
        auth_acc = AuthAccount(
            id=generate_uuid(),
            user_id=str(user.id),
            provider="local",
            provider_email=user.email,
            password_hash=hash_password(new_pwd)
        )
        db.add(auth_acc)
        db.commit()
        return {"status": "success", "message": "Đã tạo mật khẩu riêng thành công cho tài khoản Google của bạn!"}

    if auth_acc.password_hash:
        if not old_pwd or not verify_password(old_pwd, auth_acc.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không chính xác"
            )

    auth_acc.password_hash = hash_password(new_pwd)
    db.commit()
    return {"status": "success", "message": "Đổi mật khẩu thành công!"}


def authenticate_google_user(db: Session, data: GoogleAuthRequest) -> tuple[User, bool]:
    from backend.src.services.google_identity import verify_google_token
    return authenticate_verified_google_user(db, verify_google_token(data.id_token))


def authenticate_verified_google_user(db, claims):
    google_id = claims["sub"]
    email = claims["email"].lower()
    account = db.query(AuthAccount).filter(
        AuthAccount.provider == "google", AuthAccount.provider_account_id == google_id
    ).first()
    if account:
        user = db.get(User, account.user_id)
        if not user or not user.is_active:
            raise HTTPException(403, "Tài khoản không khả dụng")
        return user, False
    user = db.query(User).filter(User.email == email).first()
    is_new = user is None
    if user is not None:
        # Linking an existing local account requires a separately authenticated flow.
        raise HTTPException(409, "Email đã có tài khoản. Vui lòng đăng nhập bằng mật khẩu.")
    user = User(id=generate_uuid(), email=email, full_name=claims.get("name"),
                avatar_url=claims.get("picture"), is_active=True, is_verified=True)
    db.add(user)
    db.flush()
    db.add(AuthAccount(id=generate_uuid(), user_id=str(user.id), provider="google",
                       provider_account_id=google_id, provider_email=email))
    db.commit()
    db.refresh(user)
    return user, is_new


def handle_google_callback(db, code, state):
    from backend.src.services.google_identity import exchange_code
    user, is_new = authenticate_verified_google_user(db, exchange_code(code, state))
    return {"access_token": create_access_token(str(user.id)), "is_new": is_new}
