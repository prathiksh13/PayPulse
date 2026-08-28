from __future__ import annotations

import time

import httpx

from ..config import settings


class RazorpayError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class RazorpayClient:
    """Thin, credential-guarded Razorpay API client (Test Mode)."""

    def __init__(self):
        self.base_url = settings.razorpay_api_base
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def _auth(self) -> tuple[str, str] | None:
        if not self.configured:
            return None
        return self.key_id, self.key_secret

    def _post(self, path: str, body: dict) -> dict:
        auth = self._auth()
        if auth is None:
            raise RazorpayError("RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured in backend/.env")
        try:
            resp = httpx.post(
                f"{self.base_url}{path}",
                json=body,
                auth=auth,
                timeout=20.0,
                headers={"X-Razorpay-Account": self.key_id},
            )
        except httpx.HTTPError as exc:
            raise RazorpayError(f"Razorpay API unreachable: {exc}") from exc
        if resp.status_code >= 400:
            detail = resp.text[:300]
            raise RazorpayError(f"Razorpay API error {resp.status_code}: {detail}")
        return resp.json()

    def _get(self, path: str) -> dict:
        auth = self._auth()
        if auth is None:
            raise RazorpayError("RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured in backend/.env")
        try:
            resp = httpx.get(
                f"{self.base_url}{path}",
                auth=auth,
                timeout=20.0,
                headers={"X-Razorpay-Account": self.key_id},
            )
        except httpx.HTTPError as exc:
            raise RazorpayError(f"Razorpay API unreachable: {exc}") from exc
        if resp.status_code >= 400:
            detail = resp.text[:300]
            raise RazorpayError(f"Razorpay API error {resp.status_code}: {detail}")
        return resp.json()

    def create_order(self, amount_inr: float, currency: str = "INR", receipt: str | None = None) -> dict:
        """Create a Razorpay Order (Test Mode) for the Checkout SDK."""
        body = {
            "amount": int(round(amount_inr * 100)),
            "currency": currency,
            "receipt": receipt or None,
            "notes": {"source": "pulseops-test-checkout"},
        }
        data = self._post("/orders", body)
        return {
            "order_id": data.get("id"),
            "amount": data.get("amount"),
            "currency": data.get("currency"),
            "receipt": data.get("receipt"),
            "raw": data,
        }

    def get_payment(self, payment_id: str) -> dict:
        """Fetch a single payment entity (used to sync a completed checkout to DB)."""
        data = self._get(f"/payments/{payment_id}")
        if not isinstance(data, dict) or not data.get("id"):
            raise RazorpayError(f"Razorpay returned an unexpected payment payload for {payment_id}")
        return data

    def refund_payment(self, payment_id: str, amount_inr: float | None = None) -> dict:
        body: dict = {}
        if amount_inr is not None:
            body["amount"] = int(round(amount_inr * 100))
        data = self._post(f"/payments/{payment_id}/refund", body)
        return {"provider_ref_id": data.get("id"), "raw": data}

    def create_retry_payment_link(self, *, amount_inr: float, description: str, email: str | None, contact: str | None) -> dict:
        body = {
            "amount": int(round(amount_inr * 100)),
            "currency": "INR",
            "description": description or "Retry payment",
            "accept_partial": False,
            "reminder_enable": False,
            "notes": {"retry": "auto", "source": "pulseops-recovery"},
        }
        if email:
            body["customer"] = {"email": email}
        if contact:
            body.setdefault("customer", {})["contact"] = contact
        data = self._post("/payment_links", body)
        return {"provider_ref_id": data.get("id"), "short_url": data.get("short_url"), "raw": data}

    def ping(self) -> dict:
        """Cheap connectivity + credential check (test mode)."""
        if not self.configured:
            return {"ok": False, "detail": "credentials_missing"}
        try:
            r = httpx.get(
                f"{self.base_url}/payments?count=1",
                auth=self._auth(),
                timeout=10.0,
            )
            return {"ok": r.status_code < 400, "detail": "ok" if r.status_code < 400 else f"http_{r.status_code}"}
        except httpx.HTTPError as exc:
            return {"ok": False, "detail": f"unreachable_{exc.__class__.__name__}"}


_connection_cache: dict = {"at": 0.0, "value": None}


def get_connection_status() -> dict:
    """Connection status with a short TTL so /settings does not hammer the API."""
    now = time.time()
    cached = _connection_cache.get("value")
    if cached is not None and (now - _connection_cache["at"]) < 60:
        return cached
    client = RazorpayClient()
    if not client.configured:
        result = {"status": "disconnected", "environment": "test", "api_status": "pending"}
    else:
        ping = client.ping()
        result = {
            "status": "connected" if ping.get("ok") else "disconnected",
            "environment": "test",
            "api_status": "ok" if ping.get("ok") else "error",
        }
    _connection_cache.update(at=now, value=result)
    return result