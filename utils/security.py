"""Security helpers for password hashing, verification, content hashing, and key masking."""

from __future__ import annotations

import hashlib
import bcrypt


def hash_password(password: str) -> str:
    """Hash a plain-text password securely with bcrypt."""
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    if not password or not stored_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False


def compute_content_hash(*parts: str) -> str:
    """Return a deterministic SHA-256 hex digest for cache keying."""
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update((part or "").encode("utf-8"))
        hasher.update(b"\x00")
    return hasher.hexdigest()


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask API keys or secrets before displaying in UI or logs."""
    cleaned = (value or "").strip()
    if not cleaned:
        return "Not configured"
    if len(cleaned) <= visible_chars * 2:
        return "*" * len(cleaned)
    return f"{cleaned[:visible_chars]}...{cleaned[-visible_chars:]}"
