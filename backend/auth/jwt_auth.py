"""
JWT-based authentication for the admin dashboard.
Uses python-jose for token creation/verification and passlib for password hashing.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from models.database import AdminUser, get_db

# ── Config (all from environment) ─────────────────────────────────────────────
SECRET_KEY      = os.getenv("JWT_SECRET_KEY", "change-this-in-production-pvg-secret-2024")
ALGORITHM       = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours

# ── Password hashing ───────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── HTTP Bearer extractor ──────────────────────────────────────────────────────
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against its hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT token.

    Args:
        data: Payload dict (typically {"sub": username})
        expires_delta: Token lifetime; defaults to ACCESS_TOKEN_EXPIRE_MINUTES

    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """
    Decode JWT and return username (sub claim).

    Returns:
        Username string or None if token is invalid/expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    """
    FastAPI dependency: verifies JWT and returns the current admin user.

    Raises:
        HTTPException 401 if token is missing, invalid, or expired
        HTTPException 403 if user is inactive
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    username = decode_token(credentials.credentials)
    if username is None:
        raise credentials_exception

    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return user


def authenticate_admin(db: Session, username: str, password: str) -> Optional[AdminUser]:
    """
    Verify username + password and return the AdminUser if valid.

    Returns:
        AdminUser on success, None on failure
    """
    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
