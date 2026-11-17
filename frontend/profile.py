"""User Profile management page (personal info, career background, password change)."""

from __future__ import annotations

import streamlit as st

from backend.auth import change_user_password, get_current_user, update_user_profile
from utils.database import get_latest_resume_analysis, get_user_by_id
from utils.helpers import inject_custom_css


def profile_page() -> None:
    """Render user profile editing and password management page."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Please log in to view your profile.")
        return

    user = get_user_by_id(current["id"]) or current
    latest_resume = get_latest_resume_analysis(current["id"])

    st.markdown(
        """
        <div class="hero-banner">
            <h2>👤 My Career Profile</h2>
            <p>Keep your profile details updated to improve resume evaluation and job matching accuracy.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_info, col_pwd = st.columns([1.4, 1])

    with col_info:
        st.markdown("<div class='soft-card'><h4>Personal & Career Information</h4>", unsafe_allow_html=True)
        with st.form("profile_update_form"):
            name = st.text_input("Full Name", value=user.get("name") or "")
            st.text_input("Email Address (read-only)", value=user.get("email") or "", disabled=True)

            c1, c2 = st.columns(2)
            with c1:
                phone = st.text_input("Phone Number", value=user.get("phone") or "", placeholder="+1 555-0192")
                target_role = st.text_input(
                    "Target Job Role",
                    value=user.get("target_role") or "Software Developer",
                    placeholder="e.g., Data Scientist, Full Stack Engineer",
                )
            with c2:
                location = st.text_input("Current Location", value=user.get("location") or "", placeholder="e.g., Bengaluru / Remote")
                exp_years = st.number_input(
                    "Years of Experience",
                    min_value=0.0,
                    max_value=50.0,
                    step=0.5,
                    value=float(user.get("experience_years") or 0.0),
                )

            edu_options = ["High School", "Associate", "Bachelor's", "Master's", "PhD", "Bootcamp / Diploma"]
            saved_edu = user.get("education_level") or "Bachelor's"
            edu_index = edu_options.index(saved_edu) if saved_edu in edu_options else 2
            education_level = st.selectbox("Highest Education Level", edu_options, index=edu_index)

            linkedin_url = st.text_input(
                "LinkedIn / Portfolio URL",
                value=user.get("linkedin_url") or "",
                placeholder="https://www.linkedin.com/in/your-profile",
            )
            bio = st.text_area(
                "Professional Summary / Career Goal",
                value=user.get("bio") or "",
                height=90,
                placeholder="Briefly summarize your experience and career objectives...",
            )

            submitted = st.form_submit_button("💾 Save Profile Changes", type="primary", use_container_width=True)
            if submitted:
                ok, msg = update_user_profile(
                    current["id"],
                    name=name,
                    phone=phone,
                    location=location,
                    linkedin_url=linkedin_url,
                    target_role=target_role,
                    experience_years=exp_years,
                    education_level=education_level,
                    bio=bio,
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_pwd:
        st.markdown("<div class='soft-card'><h4>Account Summary</h4>", unsafe_allow_html=True)
        st.write(f"**Member Since:** {str(user.get('registered_at') or 'N/A')[:10]}")
        st.write(f"**Resume On File:** {'✅ Yes' if (user.get('resume_path') or latest_resume) else '❌ Not uploaded'}")
        if latest_resume and (latest_resume.get("overall_score") or 0) > 0:
            st.write(f"**Latest Resume Score:** {latest_resume['overall_score']:.1f} / 100 ({latest_resume.get('classification') or 'Rated'})")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='soft-card'><h4>🔐 Change Password</h4>", unsafe_allow_html=True)
        with st.form("change_password_form", clear_on_submit=True):
            cur_pwd = st.text_input("Current Password", type="password")
            new_pwd = st.text_input("New Password", type="password")
            conf_pwd = st.text_input("Confirm New Password", type="password")
            pwd_btn = st.form_submit_button("Update Password", use_container_width=True)
            if pwd_btn:
                ok, msg = change_user_password(current["id"], cur_pwd, new_pwd, conf_pwd)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        st.markdown("</div>", unsafe_allow_html=True)
