# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from supabase import create_client, Client
from jose import jwt, JWTError

from ..config import settings


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_db_role(role: str) -> str:
    """Map an app-side role ('admin'/'analyst') to the stored PostgreSQL enum
    label ('ADMIN'/'ANALYST'). The roles table was created with an enum whose
    values are uppercase, so raw writes must use those labels."""
    return (role or "analyst").upper()


def _from_db_role(role: Optional[str]) -> Optional[str]:
    """Normalize a stored enum label ('ADMIN'/'ANALYST') to the lowercase role
    the rest of the app compares against ('admin'/'analyst')."""
    if not role:
        return role
    return str(role).lower()


class SupabaseAuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class SupabaseAuthService:
    def __init__(self):
        self._client: Optional[Client] = None
        self._service_client: Optional[Client] = None

    @property
    def client(self) -> Client:
        if self._client is None:
            if not settings.supabase_configured:
                raise SupabaseAuthError("Supabase not configured", 503)
            self._client = create_client(settings.supabase_url, settings.supabase_anon_key)
        return self._client

    @property
    def service_client(self) -> Client:
        if self._service_client is None:
            if not settings.supabase_service_role_key:
                raise SupabaseAuthError("Supabase service role key not configured", 503)
            self._service_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        return self._service_client

    def verify_token(self, token: str) -> dict:
        """Verify a Supabase JWT token and return the payload."""
        try:
            payload = jwt.decode(
                token,
                settings.supabase_anon_key,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_signature": True}
            )
            return payload
        except JWTError as exc:
            raise SupabaseAuthError(f"Invalid token: {exc}", 401)

    def get_user_from_token(self, token: str) -> dict:
        """Get user info from Supabase using the token."""
        try:
            self.client.auth.set_session(token, "")
            user = self.client.auth.get_user()
            if user and user.user:
                return {
                    "id": user.user.id,
                    "email": user.user.email,
                    "user_metadata": user.user.user_metadata or {},
                    "app_metadata": user.user.app_metadata or {},
                }
            raise SupabaseAuthError("User not found", 401)
        except SupabaseAuthError:
            raise
        except Exception as exc:
            raise SupabaseAuthError(f"Failed to get user: {exc}", 401)

    def sign_in(self, email: str, password: str) -> dict:
        """Sign in with email and password."""
        try:
            response = self.client.auth.sign_in_with_password({"email": email, "password": password})
            if response.session:
                return {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at,
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "user_metadata": response.user.user_metadata or {},
                        "app_metadata": response.user.app_metadata or {},
                    }
                }
            raise SupabaseAuthError("Sign in failed", 401)
        except Exception as exc:
            raise SupabaseAuthError(f"Sign in failed: {exc}", 401)

    def sign_out(self, access_token: str) -> bool:
        """Sign out the user."""
        try:
            self.client.auth.set_session(access_token, "")
            self.client.auth.sign_out()
            return True
        except Exception:
            return False

    def get_profile(self, user_id: str) -> Optional[dict]:
        """Get user profile from database, role normalized to lowercase."""
        try:
            response = self.service_client.table("profiles").select("*").eq("id", user_id).single().execute()
            data = dict(response.data)
            if "role" in data:
                data["role"] = _from_db_role(data["role"])
            return data
        except Exception:
            return None

    def create_or_update_profile(self, user_id: str, email: str, name: Optional[str] = None,
                                  role: str = "analyst", merchant_id: Optional[str] = None) -> dict:
        """Create or update user profile. Idempotent AND preserves created_at.

        Existing rows are updated (role/email/merchant corrected), never
        duplicated -- the profiles primary key is the auth user id. Because
        created_at has no DB default, it is supplied explicitly on insert only."""
        try:
            now = _utcnow_iso()
            existing = self.get_profile(user_id)
            profile_data = {
                "id": user_id,
                "email": email,
                "name": name,
                "role": _to_db_role(role),
                "merchant_id": merchant_id or settings.demo_merchant_id,
                "is_active": True,
                "created_at": existing.get("created_at") if existing else now,
                "updated_at": now,
            }
            response = self.service_client.table("profiles").upsert(profile_data).execute()
            return response.data[0] if response.data else profile_data
        except Exception as exc:
            raise SupabaseAuthError(f"Failed to create/update profile: {exc}", 500)

    def get_merchant(self, merchant_id: str) -> Optional[dict]:
        """Get merchant by ID."""
        try:
            response = self.service_client.table("merchants").select("*").eq("id", merchant_id).single().execute()
            return response.data
        except Exception:
            return None

    def create_demo_merchant(self) -> dict:
        """Create/update the demo merchant. Idempotent upsert keyed on the PK."""
        try:
            now = _utcnow_iso()
            existing = self.get_merchant(settings.demo_merchant_id)
            merchant_data = {
                "id": settings.demo_merchant_id,
                "name": settings.demo_merchant_name,
                "environment": settings.demo_merchant_environment,
                "is_demo": True,
                "created_at": existing.get("created_at") if existing else now,
                "updated_at": now,
            }
            response = self.service_client.table("merchants").upsert(merchant_data).execute()
            return (response.data or [merchant_data])[0]
        except Exception as exc:
            raise SupabaseAuthError(f"Failed to create demo merchant: {exc}", 500)

    # ------------------------------------------------------------------
    # Admin API (service-role) helpers used by the automatic startup seed.
    # ------------------------------------------------------------------
    def find_user_by_email(self, email: str) -> Optional[dict]:
        """Find a Supabase Auth user by email. Returns None if not found."""
        try:
            users = self.service_client.auth.admin.list_users()
            for u in users:
                if u.email and u.email.lower() == email.lower():
                    return {
                        "id": u.id,
                        "email": u.email,
                        "email_confirmed_at": getattr(u, "email_confirmed_at", None),
                        "user_metadata": u.user_metadata or {},
                    }
            return None
        except Exception as exc:
            raise SupabaseAuthError(f"Failed to look up user: {exc}", 500)

    def add_demo_user(self, email: str, password: str, name: str) -> dict:
        """Ensure a Supabase Auth user exists for the demo account.

        Creates it via the Admin API (server-side, service-role) with
        email confirmation already handled so it can sign in immediately. If the
        user already exists it is returned untouched (never duplicated).
        """
        existing = self.find_user_by_email(email)
        if existing:
            return existing
        try:
            response = self.service_client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": name, "is_demo": True},
            })
            user = response.user
            return {
                "id": user.id,
                "email": user.email,
                "email_confirmed_at": getattr(user, "email_confirmed_at", None),
                "user_metadata": user.user_metadata or {},
            }
        except Exception as exc:
            raise SupabaseAuthError(f"Failed to create demo user: {exc}", 500)

    def sync_profile(self, email: str, role: str, name: str, merchant_id: Optional[str] = None) -> Optional[dict]:
        """Ensure a public.profiles row exists that matches the auth user.

        Looks the auth user up by email (live), then upserts its profile with the
        correct role/merchant on the profiles primary key (auth user id). If no auth
        user is found the whole demo account is (re)created first. Idempotent.
        """
        merchant_id = merchant_id or settings.demo_merchant_id
        user = self.find_user_by_email(email)
        if not user:
            user = self.add_demo_user(email, self._password_for_email(email), name)
        return self.create_or_update_profile(
            user_id=user["id"],
            email=user["email"],
            name=name,
            role=role,
            merchant_id=merchant_id,
        )

    def _password_for_email(self, email: str) -> str:
        if email.lower() == settings.demo_admin_email.lower():
            return settings.demo_admin_password
        if email.lower() == settings.demo_analyst_email.lower():
            return settings.demo_analyst_password
        return settings.demo_analyst_password

    def seed_demo_data(self) -> dict:
        """Idempotent demo-data initialization, run on every backend startup.

        Ensures the demo merchant, both demo Auth users, and their profiles all
        exist with the correct roles. Designed to be safe to run repeatedly.
        Confirms email for both users so login works immediately. Never logs
        passwords or service-role keys.
        """
        from ..utils.plog import plog

        plog("Demo initialization started")
        if not settings.supabase_service_configured:
            plog("Demo initialization skipped: Supabase service-role not configured")
            return {"ok": False, "reason": "supabase_not_configured"}

        self.create_demo_merchant()
        plog(f"Demo merchant verified ({settings.demo_merchant_id})")

        self.add_demo_user(settings.demo_admin_email, settings.demo_admin_password, "Admin User")
        plog(f"Admin demo account verified ({settings.demo_admin_email})")

        self.add_demo_user(settings.demo_analyst_email, settings.demo_analyst_password, "Analyst User")
        plog(f"Analyst demo account verified ({settings.demo_analyst_email})")

        self.sync_profile(settings.demo_admin_email, "admin", "Admin User")
        self.sync_profile(settings.demo_analyst_email, "analyst", "Analyst User")
        plog("Demo profiles verified")

        plog("Demo initialization complete")
        return {"ok": True}


supabase_auth = SupabaseAuthService()