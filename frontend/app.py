"""Streamlit Application Entry Point (Frontend Router)."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st

from backend.auth import is_user_logged_in
from frontend.dashboard import dashboard_page
from frontend.login import login_page
from frontend.registration import registration_page
from utils.database import init_db


def show_login_page() -> None:
    """Compatibility wrapper for rendering the login view."""
    login_page()


def main() -> None:
    """Configure Streamlit and route between Login, Registration, and Dashboard."""
    st.set_page_config(
        page_title="AI Career Assistant | Resume & Job Platform",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_db()

    if "page" not in st.session_state:
        st.session_state["page"] = "Dashboard" if is_user_logged_in() else "Login"

    page = st.session_state["page"]
    if page == "Register":
        registration_page()
    elif page == "Dashboard":
        if not is_user_logged_in():
            st.session_state["page"] = "Login"
            login_page()
        else:
            dashboard_page()
    else:
        if is_user_logged_in():
            st.session_state["page"] = "Dashboard"
            dashboard_page()
        else:
            login_page()


if __name__ == "__main__":
    main()
