"""Authentication, registration, password security, and session management."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import streamlit as st

from utils.database import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    init_db,
    log_activity,
    update_user,
)
from utils.logger import get_logger, log_user_event
from utils.security import hash_password, verify_password
from utils.validators import (
    validate_confirm_password,
    validate_email,
    validate_name,
    validate_password,
    validate_url,
)

logger = get_logger("auth")


def _set_user_session(user: Dict[str, Any]) -> None:
    """Store the authenticated user profile in Streamlit session_state."""
    st.session_state["user"] = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "target_role": user.get("target_role") or "",
    }


def get_current_user() -> Optional[Dict[str, Any]]:
    """Return the currently logged-in user dictionary, or None."""
    user = st.session_state.get("user")
    if isinstance(user, dict) and user.get("id"):
        return user
    return None


def is_user_logged_in() -> bool:
    """Return True if an authenticated user session is active."""
    return get_current_user() is not None


def logout_user() -> None:
    """Clear authentication and cached page state on logout."""
    current = get_current_user()
    if current:
        log_user_event(current["id"], "logout", "User signed out")
    for key in [
        "user",
        "nav_page",
        "current_analysis",
        "current_skills_gap",
        "current_improvements",
        "last_search_results",
        "selected_job_id",
        "cancel_job_search",
    ]:
        if key in st.session_state:
            del st.session_state[key]


def require_authentication() -> Optional[Dict[str, Any]]:
    """Protect authenticated pages; redirect to Login when unauthenticated."""
    user = get_current_user()
    if not user:
        st.warning("Please log in to access this page.")
        st.session_state["page"] = "Login"
        return None
    return user


def register_user(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
) -> Tuple[bool, str]:
    """Validate inputs, hash password with bcrypt, and persist a new user account."""
    try:
        init_db()
    except Exception as exc:
        logger.error("Database initialization failed during registration: %s", exc)
        return False, f"Database error while initializing storage: {exc}"

    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    password = password or ""
    confirm_password = confirm_password or ""

    for err in [
        validate_name(full_name),
        validate_email(email),
        validate_password(password),
        validate_confirm_password(password, confirm_password),
    ]:
        if err:
            return False, err

    try:
        existing = get_user_by_email(email)
    except Exception as exc:
        logger.error("Database error checking email %s: %s", email, exc)
        return False, f"Database error while checking email: {exc}"

    if existing:
        return False, "An account with this email already exists. Please log in."

    try:
        pw_hash = hash_password(password)
    except Exception as exc:
        logger.error("Password hashing error: %s", exc)
        return False, f"Error while securing password: {exc}"

    try:
        uid = create_user(name=full_name, email=email, password_hash=pw_hash)
        log_activity(uid, "Account Created", "Registered a new user account.")
        log_user_event(uid, "register", f"Registered {email}")
    except ValueError as exc:
        return False, str(exc)
    except Exception as exc:
        logger.error("Database error creating user %s: %s", email, exc)
        return False, f"Database error while creating account: {exc}"

    return True, "Registration successful! Please log in with your new account."


def login_user(email: str, password: str) -> Tuple[bool, str]:
    """Verify credentials against stored bcrypt hash and establish user session."""
    try:
        init_db()
    except Exception as exc:
        logger.error("Database initialization failed during login: %s", exc)
        return False, f"Database connection error: {exc}"

    email = (email or "").strip().lower()
    password = password or ""

    email_err = validate_email(email)
    if email_err:
        return False, email_err
    if not password:
        return False, "Password is required."

    try:
        user = get_user_by_email(email)
    except Exception as exc:
        logger.error("Database error fetching user %s: %s", email, exc)
        return False, f"Database error while verifying account: {exc}"

    if not user:
        return False, "Invalid email or password."

    stored_hash = user.get("password_hash") or ""
    if not verify_password(password, stored_hash):
        return False, "Invalid email or password."

    _set_user_session(user)
    log_activity(user["id"], "Login", "Signed into AI Career Assistant.")
    log_user_event(user["id"], "login", f"User {email} logged in")
    return True, f"Welcome back, {user['name']}!"


def update_user_profile(user_id: int, **fields: Any) -> Tuple[bool, str]:
    """Validate and update user profile fields in the database."""
    name = fields.get("name")
    if name is not None:
        err = validate_name(str(name))
        if err:
            return False, err

    linkedin_url = fields.get("linkedin_url")
    if linkedin_url and not validate_url(str(linkedin_url)):
        return False, "LinkedIn URL must start with http:// or https://"

    try:
        update_user(user_id, **fields)
        refreshed = get_user_by_id(user_id)
        if refreshed and is_user_logged_in():
            curr = get_current_user()
            if curr and curr.get("id") == user_id:
                _set_user_session(refreshed)
        log_activity(user_id, "Profile Updated", "Updated profile preferences.")
        return True, "Profile updated successfully."
    except Exception as exc:
        logger.error("Error updating profile for user_id=%s: %s", user_id, exc)
        return False, f"Failed to update profile: {exc}"


def change_user_password(
    user_id: int,
    current_password: str,
    new_password: str,
    confirm_new_password: str,
) -> Tuple[bool, str]:
    """Verify current password and update bcrypt hash for new password."""
    user = get_user_by_id(user_id)
    if not user:
        return False, "User record not found."
    if not verify_password(current_password, user.get("password_hash") or ""):
        return False, "Current password is incorrect."

    for err in [
        validate_password(new_password),
        validate_confirm_password(new_password, confirm_new_password),
    ]:
        if err:
            return False, err

    try:
        new_hash = hash_password(new_password)
        update_user(user_id, password_hash=new_hash)
        log_activity(user_id, "Security", "Password changed successfully.")
        return True, "Password updated successfully."
    except Exception as exc:
        logger.error("Password change error for user_id=%s: %s", user_id, exc)
        return False, f"Could not update password: {exc}"
