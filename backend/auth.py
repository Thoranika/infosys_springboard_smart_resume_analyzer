# backend/auth.py

import bcrypt
import streamlit as st

from utils.database import (
    init_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
)

# --------------------------------------------------
# Helpers for session management (Streamlit)
# --------------------------------------------------


def _set_user_session(user: dict) -> None:
    """Store the logged-in user in Streamlit session_state."""
    st.session_state["user"] = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
    }


def get_current_user() -> dict | None:
    """Return the current logged-in user, or None."""
    return st.session_state.get("user")


def is_user_logged_in() -> bool:
    """True if a user is currently logged in."""
    return "user" in st.session_state


def logout_user() -> None:
    """Clear session data for logout."""
    if "user" in st.session_state:
        del st.session_state["user"]


# --------------------------------------------------
# Registration logic
# ----------------------------------------------
def register_user(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
) -> tuple[bool, str]:
    """
    Register a new user.

    Returns (success, message).
    success = True  -> registration OK
    success = False -> some error (explained in message)

    NOTE: This function does NOT log the user in automatically.
    User must log in separately after registration.
    """
    init_db()  # make sure DB exists

    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    password = password or ""
    confirm_password = confirm_password or ""

    # Basic validation
    if not full_name:
        return False, "Full name is required."

    if not email:
        return False, "Email is required."

    if "@" not in email or "." not in email:
        return False, "Please enter a valid email address."

    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if password != confirm_password:
        return False, "Passwords do not match."

    # Check if user already exists
    try:
        existing = get_user_by_email(email)
    except Exception as e:
        return False, f"Database error while checking email: {e}"

    if existing:
        return False, "An account with this email already exists. Please log in."

    # Hash password
    try:
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")
    except Exception as e:
        return False, f"Error while hashing password: {e}"

    # Save user
    try:
        create_user(
            name=full_name,
            email=email,
            password_hash=password_hash,
        )
    except Exception as e:
        return False, f"Database error while creating user: {e}"

    return True, "Registration successful! Please log in with your new account."



# --------------------------------------------------
# Login logic
# --------------------------------------------------


def login_user(email: str, password: str) -> tuple[bool, str]:
    """
    Log in a user.

    Returns (success, message).
    On success, the user is stored in session_state.
    """
    init_db()

    email = (email or "").strip().lower()
    password = password or ""

    if not email:
        return False, "Email is required."

    if not password:
        return False, "Password is required."

    try:
        user = get_user_by_email(email)
    except Exception as e:
        return False, f"Database error while fetching user: {e}"

    if not user:
        return False, "No account found with this email."

    stored_hash = user.get("password_hash")
    if not stored_hash:
        return False, "User record is missing password hash."

    try:
        password_ok = bcrypt.checkpw(
            password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )
    except Exception as e:
        return False, f"Error while verifying password: {e}"

    if not password_ok:
        return False, "Invalid password. Please try again."

    # Success: create session
    _set_user_session(user)
    return True, f"Welcome back, {user['name']}!"
