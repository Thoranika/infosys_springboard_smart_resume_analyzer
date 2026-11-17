"""User Login UI page with validation and seamless registration navigation."""

from __future__ import annotations

import streamlit as st

from backend.auth import is_user_logged_in, login_user
from utils.helpers import inject_custom_css


def login_page() -> None:
    """Render the login form and authenticate users."""
    inject_custom_css()

    if is_user_logged_in():
        st.session_state["page"] = "Dashboard"
        st.rerun()
        return

    st.markdown(
        """
        <div class="hero-banner" style="text-align:center;">
            <h1>💼 Smart Resume Analyzer</h1>
            <p>Personalized Job Recommendations & LinkedIn-Based Profile Enhancement</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1, 1.7, 1])
    with center_col:
        if "flash_success" in st.session_state:
            st.success(st.session_state.pop("flash_success"))

        st.markdown("<div class='soft-card'><h3>🔐 Sign In</h3>", unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email Address", placeholder="name@example.com")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

            if submitted:
                success, message = login_user(email, password)
                if success:
                    st.success(message)
                    st.session_state["page"] = "Dashboard"
                    st.session_state["nav_page"] = "Overview"
                    st.rerun()
                else:
                    st.error(message)

        st.markdown("---")
        st.caption("New to AI Career Assistant?")
        if st.button("Create a new account", use_container_width=True):
            st.session_state["page"] = "Register"
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
