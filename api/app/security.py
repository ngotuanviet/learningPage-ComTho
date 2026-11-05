import hashlib
import hmac
import secrets

from app.config import get_settings

# No 0/O/1/I so codes are easy to read and type into a bank app.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256-bit


def new_order_code(length: int = 8) -> str:
    prefix = get_settings().order_code_prefix
    return prefix + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def keyed_hash(value: str) -> str:
    """HMAC so stored IPs cannot be reversed without the secret."""
    key = get_settings().app_secret.encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def same_hash(token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(sha256_hex(token), stored_hash)
