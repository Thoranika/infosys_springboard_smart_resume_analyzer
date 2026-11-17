"""User Registration UI page with real-time validation and password strength meter."""

from __future__ import annotations

import streamlit as st

from backend.auth import register_user
from utils.helpers import inject_custom_css
from utils.validators import (
    get_password_strength,
    validate_confirm_password,
    validate_email,
    validate_name,
    validate_password,
)


def registration_page() -> None:
    """Render the user registration page."""
    inject_custom_css()

    st.markdown(
        """
        <div class="hero-banner" style="text-align:center;">
            <h1>🚀 AI-Powered Resume & Job Recommendation System</h1>
            <p>Create your account to analyze your resume, close skill gaps, and match with top jobs.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        st.markdown("<div class='soft-card'><h3>Create Your Account</h3>", unsafe_allow_html=True)

        full_name = st.text_input("Full Name", placeholder="e.g., Alex Morgan", key="reg_name")
        if full_name:
            name_err = validate_name(full_name)
            if name_err:
                st.error(name_err)

        email = st.text_input("Email Address", placeholder="e.g., alex@example.com", key="reg_email")
        if email:
            email_err = validate_email(email)
            if email_err:
                st.error(email_err)

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Minimum 8 chars with A-Z, a-z, 0-9, and symbol",
            key="reg_pwd",
        )

        if password:
            strength = get_password_strength(password)
            st.progress(strength["score"] / 5.0, text=f"Password Strength: {strength['label']}")
            checks = strength["checks"]
            st.caption(
                f"{'✅' if checks['min_length'] else '⬜'} 8+ chars  |  "
                f"{'✅' if checks['uppercase'] else '⬜'} Uppercase  |  "
                f"{'✅' if checks['lowercase'] else '⬜'} Lowercase  |  "
                f"{'✅' if checks['digit'] else '⬜'} Number  |  "
                f"{'✅' if checks['special'] else '⬜'} Special char"
            )
            pwd_err = validate_password(password)
            if pwd_err:
                st.warning(pwd_err)

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Re-enter your password",
            key="reg_confirm",
        )
        if confirm_password:
            confirm_err = validate_confirm_password(password, confirm_password)
            if confirm_err:
                st.error(confirm_err)

        st.write("")
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Register Account", type="primary", use_container_width=True):
                success, message = register_user(full_name, email, password, confirm_password)
                if success:
                    st.session_state["flash_success"] = message
                    st.session_state["page"] = "Login"
                    st.rerun()
                else:
                    st.error(message)
        with btn_col2:
            if st.button("Already have an account? Login", use_container_width=True):
                st.session_state["page"] = "Login"
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
