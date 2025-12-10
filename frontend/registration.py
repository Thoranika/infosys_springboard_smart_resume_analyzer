# frontend/registration.py

import sys, os
# allow importing backend
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # project root

import re
import streamlit as st

from backend.auth import register_user

# ---- Validation regex ----
NAME_REGEX = re.compile(r"^[A-Za-z ]+$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$"
)


def validate_name(name: str) -> str | None:
    if not name.strip():
        return "Name cannot be empty."
    if not NAME_REGEX.match(name):
        return "Name should contain only letters and spaces."
    return None


def validate_email(email: str) -> str | None:
    if not email.strip():
        return "Email cannot be empty."
    if not EMAIL_REGEX.match(email):
        return "Please enter a valid email address."
    return None


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not PASSWORD_REGEX.match(password):
        return (
            "Password must contain uppercase, lowercase, number "
            "and special character."
        )
    return None


def validate_confirm_password(password: str, confirm: str) -> str | None:
    if confirm == "":
        return "Please confirm your password."
    if password != confirm:
        return "Passwords do not match."
    return None


def registration_page():
    # ⚠ DO NOT call st.set_page_config here (handled in app.py)

    # Project title
    st.markdown(
        "<h1 style='text-align: center; color: #E0FFFF;'>"
        "AI-Powered Resume &amp; Job Recommendation System"
        "</h1>",
        unsafe_allow_html=True,
    )
    st.write("")

    st.markdown("## Create your account")
    st.caption("Join and get personalized job recommendations.")

    # ---- Inputs ----
    full_name = st.text_input("Full Name")
    email = st.text_input("Email Address")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")

    # ---- Live validation ----
    name_error = validate_name(full_name) if full_name else None
    email_error = validate_email(email) if email else None
    password_error = validate_password(password) if password else None
    confirm_error = (
        validate_confirm_password(password, confirm_password)
        if confirm_password
        else None
    )

    for err in [name_error, email_error, password_error, confirm_error]:
        if err:
            st.error(err)

    # ---- Register button ----
    if st.button("Register"):
        success, message = register_user(
            full_name,
            email,
            password,
            confirm_password,
        )
        if success:
            st.success(message)
            # After successful registration, go to Login page
            st.session_state["page"] = "Login"
            st.rerun()
        else:
            st.error(message)

    st.markdown("---")

    # ---- Go to login button ----
    if st.button("Go to Login page"):
        st.session_state["page"] = "Login"
        st.rerun()
