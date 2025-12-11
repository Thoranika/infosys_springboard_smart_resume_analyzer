# frontend/app.py

import sys, os
# allow imports from frontend, backend, utils
sys.path.append(os.path.dirname(__file__))  # frontend
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # project root

import streamlit as st

from backend.auth import (
    is_user_logged_in,
    login_user,
)
from registration import registration_page
from dashboard import dashboard_page


def show_login_page():
    st.markdown("<h1 style='text-align: center; color: #E0FFFF;'>AI-Powered Resume & Job Recommendation System</h1>",
                unsafe_allow_html=True)
    st.write("")  # spacing
    st.header("🔐 Login")
    # if already logged in, go to dashboard
    if is_user_logged_in():
        st.success("You are already logged in. Redirecting to dashboard...")
        st.session_state["page"] = "Dashboard"
        st.rerun()
        return

    email = st.text_input("Email Address")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        success, message = login_user(email, password)
        if success:
            st.success(message)
            st.session_state["page"] = "Dashboard"
            st.rerun()
        else:
            st.error(message)

    st.markdown("---")
    if st.button("Create a new account"):
        st.session_state["page"] = "Register"
        st.rerun()


def main():
    st.set_page_config(
        page_title="AI Career Assistant",
        page_icon="💼",
        layout="wide",
    )

    # navigation state: which screen are we on?
    if "page" not in st.session_state:
        st.session_state["page"] = "Login"

    page = st.session_state["page"]

    if page == "Login":
        show_login_page()

    elif page == "Register":
        registration_page()

    elif page == "Dashboard":
        # safety: if not logged in, go back to login
        if not is_user_logged_in():
            st.session_state["page"] = "Login"
            st.rerun()
        dashboard_page()


if __name__ == "__main__":
    main()
