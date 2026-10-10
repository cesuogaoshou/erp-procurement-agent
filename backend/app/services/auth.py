import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


DEMO_ACCOUNTS = {
    "buyer": {"password": "buyer-pass", "user_id": "buyer-1", "role": "buyer"},
    "approver": {"password": "approver-pass", "user_id": "approver-1", "role": "approver"},
}


@dataclass(frozen=True)
class TokenClaims:
    username: str
    user_id: str
    role: str
    exp: int


class AuthError(ValueError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def authenticate_demo_user(username: str, password: str) -> TokenClaims:
    account = DEMO_ACCOUNTS.get(username)
    if account is None or not hmac.compare_digest(account["password"], password):
        raise AuthError("invalid_credentials")
    return TokenClaims(username=username, user_id=account["user_id"], role=account["role"], exp=0)


def issue_token(
    *,
    username: str,
    user_id: str,
    role: str,
    secret: str,
    now: datetime | None = None,
    ttl_seconds: int = 3600,
) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "username": username,
        "user_id": user_id,
        "role": role,
        "exp": int((issued_at + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign(payload_b64, secret)
    return f"{payload_b64}.{signature}"


def verify_token(token: str, *, secret: str, now: datetime | None = None) -> TokenClaims:
    parts = token.split(".")
    if len(parts) != 2:
        raise AuthError("invalid_token")
    payload_b64, signature = parts
    expected = _sign(payload_b64, secret)
    if not hmac.compare_digest(signature, expected):
        raise AuthError("invalid_token")
    try:
        payload = json.loads(_b64decode(payload_b64))
        claims = TokenClaims(
            username=str(payload["username"]),
            user_id=str(payload["user_id"]),
            role=str(payload["role"]),
            exp=int(payload["exp"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthError("invalid_token") from exc
    if claims.exp < int((now or datetime.now(UTC)).timestamp()):
        raise AuthError("token_expired")
    account = DEMO_ACCOUNTS.get(claims.username)
    if account is None or account["user_id"] != claims.user_id or account["role"] != claims.role:
        raise AuthError("invalid_token")
    return claims


def _sign(payload_b64: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
