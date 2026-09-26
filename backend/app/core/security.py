"""Login admin: hash password (scrypt) e token di sessione firmati (HMAC)."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .db import connect

DEFAULT_USER = "admin"
DEFAULT_PASSWORD = "Admin12345"   # documentata nel README, da cambiare al primo accesso
MIN_PASSWORD_LEN = 10


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest.hex(), digest_hex)


def ensure_default_user() -> None:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM users").fetchone():
            conn.execute(
                "INSERT INTO users(username, password_hash, is_default) VALUES (?,?,1)",
                (DEFAULT_USER, hash_password(DEFAULT_PASSWORD)),
            )


_key_cache: bytes | None = None


def _secret() -> bytes:
    """SECRET_KEY dal .env; se è ancora quella d'esempio ne genera una casuale e la salva accanto al DB."""
    global _key_cache
    if _key_cache is None:
        s = get_settings()
        if s.secret_key and s.secret_key != "cambia-questa-chiave":
            _key_cache = s.secret_key.encode()
        else:
            path = Path(s.db_path).parent / "secret.key"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(secrets.token_hex(32))
                path.chmod(0o600)
            _key_cache = path.read_text().strip().encode()
    return _key_cache


def _sign(data: bytes) -> str:
    key = _secret()
    return base64.urlsafe_b64encode(hmac.new(key, data, hashlib.sha256).digest()).decode().rstrip("=")


def create_token(username: str) -> str:
    exp = int(time.time()) + get_settings().session_hours * 3600
    payload = base64.urlsafe_b64encode(json.dumps({"u": username, "exp": exp}).encode()).decode().rstrip("=")
    return f"{payload}.{_sign(payload.encode())}"


def read_token(token: str) -> str | None:
    try:
        payload, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(payload.encode())):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return data["u"] if data["exp"] > time.time() else None
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


_bearer = HTTPBearer(auto_error=False)


def role_of(username: str) -> str:
    with connect() as db:
        row = db.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    return row["role"] if row else "viewer"


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    user = read_token(cred.credentials) if cred else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessione non valida o scaduta")
    return user
