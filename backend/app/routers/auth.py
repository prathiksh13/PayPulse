# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Merchant, Profile, UserRole
from ..services.supabase_auth import SupabaseAuthError, supabase_auth

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int
    user: dict


class ProfileResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    merchant_id: str | None
    is_active: bool
    merchant: dict | None = None


class CurrentUser:
    def __init__(self, user_id: str, email: str, role: str, merchant_id: str | None, name: str | None = None):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.merchant_id = merchant_id
        self.name = name

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_analyst(self) -> bool:
        return self.role == "analyst"


async def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid authorization header")

    token = authorization.split(" ")[1]

    try:
        user_info = supabase_auth.get_user_from_token(token)
        user_id = user_info["id"]
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    profile = supabase_auth.get_profile(user_id)
    if not profile:
        try:
            supabase_auth.create_or_update_profile(
                user_id=user_id,
                email=user_info["email"],
                name=user_info.get("user_metadata", {}).get("full_name"),
                role="analyst",
                merchant_id=settings.demo_merchant_id,
            )
            profile = supabase_auth.get_profile(user_id)
        except SupabaseAuthError:
            raise HTTPException(status_code=500, detail="Failed to initialize user profile")

    if not profile or not profile.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    merchant = None
    if profile.get("merchant_id"):
        merchant = supabase_auth.get_merchant(profile["merchant_id"])

    return CurrentUser(
        user_id=user_id,
        email=profile["email"],
        role=profile["role"],
        merchant_id=profile.get("merchant_id"),
        name=profile.get("name"),
    )


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def require_analyst_or_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Analyst or Admin role required")
    return current_user


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    try:
        result = supabase_auth.sign_in(body.email, body.password)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    # Attach profile + role so the authenticated user's permissions always come
    # from the backend/database, never from frontend-only state.
    user_id = result["user"]["id"]
    email = result["user"]["email"]
    profile = supabase_auth.get_profile(user_id)
    if not profile:
        try:
            supabase_auth.create_or_update_profile(
                user_id=user_id,
                email=email,
                name=result["user"].get("user_metadata", {}).get("full_name"),
                role="analyst",
                merchant_id=settings.demo_merchant_id,
            )
            profile = supabase_auth.get_profile(user_id)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=500, detail="Failed to load user profile")

    result["user"]["role"] = profile.get("role", "analyst") if profile else "analyst"
    result["user"]["merchant_id"] = profile.get("merchant_id") if profile else settings.demo_merchant_id
    result["user"]["name"] = profile.get("name") if profile else None
    return result


@router.post("/logout")
def logout(authorization: str | None = Header(None, alias="Authorization")):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid authorization header")

    token = authorization.split(" ")[1]
    supabase_auth.sign_out(token)
    return {"ok": True, "message": "Logged out successfully"}


@router.get("/me", response_model=ProfileResponse)
def get_current_user_profile(current_user: CurrentUser = Depends(get_current_user)):
    merchant = None
    if current_user.merchant_id:
        merchant = supabase_auth.get_merchant(current_user.merchant_id)

    return ProfileResponse(
        id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        merchant_id=current_user.merchant_id,
        is_active=True,
        merchant=merchant,
    )


@router.get("/demo-credentials")
def get_demo_credentials():
    """Return the actual configured demo credentials for presentation."""
    return {
        "admin": {
            "email": settings.demo_admin_email,
            "password": settings.demo_admin_password,
            "role": "admin",
        },
        "analyst": {
            "email": settings.demo_analyst_email,
            "password": settings.demo_analyst_password,
            "role": "analyst",
        },
    }


@router.post("/init-demo")
def init_demo_data(db: Session = Depends(get_db)):
    """Initialize demo merchant and demo users in Supabase."""
    if not settings.supabase_configured:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    try:
        supabase_auth.create_demo_merchant()

        supabase_auth.create_or_update_profile(
            user_id="admin-user-id-placeholder",
            email="admin@paypulse.demo",
            name="Admin User",
            role="admin",
            merchant_id=settings.demo_merchant_id,
        )

        supabase_auth.create_or_update_profile(
            user_id="analyst-user-id-placeholder",
            email="analyst@paypulse.demo",
            name="Analyst User",
            role="analyst",
            merchant_id=settings.demo_merchant_id,
        )

        return {"ok": True, "message": "Demo data initialized. Create users in Supabase Auth dashboard with the same emails."}
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))