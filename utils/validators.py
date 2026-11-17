"""Input and file validation helpers aligned with Milestone 1 requirements."""

from __future__ import annotations

import os
import re
from typing import Dict, Optional, Tuple

NAME_REGEX = re.compile(r"^[A-Za-z][A-Za-z\s\.\-']{1,99}$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_UPPER_REGEX = re.compile(r"[A-Z]")
PASSWORD_LOWER_REGEX = re.compile(r"[a-z]")
PASSWORD_DIGIT_REGEX = re.compile(r"\d")
PASSWORD_SPECIAL_REGEX = re.compile(r"[^A-Za-z0-9\s]")

MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx"}


def validate_name(name: str) -> Optional[str]:
    """Validate user full name. Returns error string or None if valid."""
    cleaned = (name or "").strip()
    if not cleaned:
        return "Full name cannot be empty."
    if len(cleaned) < 2:
        return "Full name must be at least 2 characters long."
    if not NAME_REGEX.match(cleaned):
        return "Full name should contain only letters, spaces, hyphens, or periods."
    return None


def validate_email(email: str) -> Optional[str]:
    """Validate email format. Returns error string or None if valid."""
    cleaned = (email or "").strip()
    if not cleaned:
        return "Email address cannot be empty."
    if not EMAIL_REGEX.match(cleaned) or ".." in cleaned:
        return "Please enter a valid email address (e.g., name@example.com)."
    return None


def get_password_strength(password: str) -> Dict[str, object]:
    """Return password strength score (0-5), label, and boolean checklist."""
    pwd = password or ""
    checks = {
        "min_length": len(pwd) >= 8,
        "uppercase": bool(PASSWORD_UPPER_REGEX.search(pwd)),
        "lowercase": bool(PASSWORD_LOWER_REGEX.search(pwd)),
        "digit": bool(PASSWORD_DIGIT_REGEX.search(pwd)),
        "special": bool(PASSWORD_SPECIAL_REGEX.search(pwd)),
    }
    score = sum(1 for passed in checks.values() if passed)
    labels = {
        0: "Very Weak",
        1: "Weak",
        2: "Weak",
        3: "Fair",
        4: "Strong",
        5: "Very Strong",
    }
    return {
        "score": score,
        "max_score": 5,
        "label": labels[score],
        "checks": checks,
        "is_valid": score == 5,
    }


def validate_password(password: str) -> Optional[str]:
    """Enforce Milestone 1 password policy (8+ chars, upper, lower, digit, special)."""
    pwd = password or ""
    if not pwd:
        return "Password cannot be empty."
    strength = get_password_strength(pwd)
    checks = strength["checks"]
    missing = []
    if not checks["min_length"]:
        missing.append("at least 8 characters")
    if not checks["uppercase"]:
        missing.append("an uppercase letter")
    if not checks["lowercase"]:
        missing.append("a lowercase letter")
    if not checks["digit"]:
        missing.append("a number")
    if not checks["special"]:
        missing.append("a special character")
    if missing:
        return "Password must contain " + ", ".join(missing) + "."
    return None


def validate_confirm_password(password: str, confirm_password: str) -> Optional[str]:
    """Verify confirm password matches password."""
    if not (confirm_password or ""):
        return "Please confirm your password."
    if (password or "") != (confirm_password or ""):
        return "Passwords do not match."
    return None


def validate_url(url: str) -> bool:
    """Basic HTTP/HTTPS URL validator."""
    if not url or not url.strip():
        return True
    return bool(re.match(r"^https?://[^\s/$.?#].[^\s]*$", url.strip(), re.IGNORECASE))


def validate_resume_file(
    filename: str,
    file_bytes: bytes,
    max_size_bytes: int = MAX_RESUME_SIZE_BYTES,
) -> Tuple[bool, str]:
    """Validate uploaded resume file extension, size, and magic-byte signature."""
    if not filename:
        return False, "No file selected."

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        return False, "Unsupported file format. Please upload a PDF (.pdf) or Word (.docx) file."

    if not file_bytes or len(file_bytes) == 0:
        return False, "The uploaded file is empty (0 bytes)."

    if len(file_bytes) > max_size_bytes:
        size_mb = len(file_bytes) / (1024 * 1024)
        return False, f"File size ({size_mb:.2f} MB) exceeds the maximum allowed limit of 5 MB."

    if ext == ".pdf":
        # Allow minor leading whitespace/BOM before %PDF-
        header = file_bytes[:1024].lstrip()
        if not header.startswith(b"%PDF-"):
            return False, "Invalid or corrupted PDF file (missing PDF signature)."
    elif ext == ".docx":
        if not file_bytes.startswith(b"PK\x03\x04"):
            return False, "Invalid or corrupted DOCX file (missing ZIP/DOCX container signature)."

    return True, "File validation passed."
