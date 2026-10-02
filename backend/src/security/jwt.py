"""JWT Token Generation & Decoding"""

import datetime
from typing import Optional
import jwt
from backend.src.config import settings


def create_access_token(user_id: str, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Create JWT access token signed with secret key."""
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
    """Decode JWT token and return subject user_id."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        return str(payload.get("sub"))
    except Exception:
        return None
