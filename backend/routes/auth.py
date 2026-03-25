"""
Admin authentication routes — login, token refresh, and user management.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.jwt_auth import (
    authenticate_admin,
    create_access_token,
    get_current_admin,
    hash_password,
)
from models.database import AdminUser, get_db
from schemas.schemas import AdminUserCreate, AdminUserResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Admin registration secret — prevents arbitrary account creation
ADMIN_REGISTRATION_SECRET = os.getenv("ADMIN_REGISTRATION_SECRET", "pvg-admin-secret-2024")


@router.post("/login", response_model=TokenResponse, summary="Admin login")
def login(login_req: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate admin with username + password.
    Returns a JWT Bearer token valid for the configured duration.
    """
    user = authenticate_admin(db, login_req.username, login_req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, username=user.username)


@router.post(
    "/register",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new admin (requires registration secret)",
)
def register_admin(
    user_in: AdminUserCreate,
    registration_secret: str,
    db: Session = Depends(get_db),
):
    """
    Register a new admin account.
    Requires the ADMIN_REGISTRATION_SECRET header to prevent unauthorized access.

    Used only for initial setup — subsequent admins should be created by existing admins.
    """
    if registration_secret != ADMIN_REGISTRATION_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid registration secret",
        )

    # Check for existing username/email
    if db.query(AdminUser).filter(AdminUser.username == user_in.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    if db.query(AdminUser).filter(AdminUser.email == user_in.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    admin = AdminUser(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@router.get("/me", response_model=AdminUserResponse, summary="Get current admin profile")
def get_me(current_admin: AdminUser = Depends(get_current_admin)):
    """Returns the currently authenticated admin's profile."""
    return current_admin


@router.post(
    "/create-admin",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create admin user (logged-in admin only)",
)
def create_admin_by_admin(
    user_in: AdminUserCreate,
    db: Session = Depends(get_db),
    _current_admin: AdminUser = Depends(get_current_admin),
):
    """Authenticated admins can create additional admin accounts."""
    if db.query(AdminUser).filter(AdminUser.username == user_in.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    admin = AdminUser(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
