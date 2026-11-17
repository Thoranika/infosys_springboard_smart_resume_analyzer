"""Main authenticated User Dashboard hub with full module navigation (Milestone 1 Task 7)."""

from __future__ import annotations

import streamlit as st

from backend.auth import get_current_user, logout_user
from frontend.analysis import analysis_page
from frontend.improvement import improvement_page
from frontend.job_preferences import job_preferences_page
from frontend.job_recommendations import job_recommendations_page
from frontend.profile import profile_page
from frontend.settings import settings_page
from frontend.skills_gap_page import skills_gap_page
from frontend.upload_resume import upload_resume_page
from utils.database import (
    get_dashboard_stats,
    get_recent_activities,
    get_user_by_id,
)
from utils.helpers import inject_custom_css

NAV_OPTIONS = [
    "Overview",
    "My Profile",
    "Upload Resume",
    "Resume Analysis",
    "Skills Gap",
    "Improve Resume",
    "Job Preferences",
    "Job Recommendations",
    "Settings",
]


def _render_overview(user: dict) -> None:
    stats = get_dashboard_stats(user["id"])
    activities = get_recent_activities(user["id"], limit=6)

    st.markdown(
        f"""
        <div class="hero-banner">
            <h2>👋 Welcome back, {user['name']}!</h2>
            <p>Your centralized AI career cockpit — analyze your resume, strengthen weak areas, and match with curated roles.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Quick Stats Row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Resume Status", "✅ Uploaded" if stats["has_resume"] else "⏳ Pending")
    k2.metric(
        "Latest Resume Score",
        f"{stats['last_score']:.1f} / 100" if stats["last_score"] is not None else "Not Analyzed",
    )
    k3.metric(
        "Last Analysis Date",
        str(stats["last_analysis_date"])[:10] if stats["last_analysis_date"] else "N/A",
    )
    k4.metric(
        "Job Matches / Tracked",
        f"{stats['total_jobs']} ({stats['saved_jobs_count']} tracked)",
    )

    st.write("")

    # Call-to-Action Workflow Cards
    st.markdown("### 🚀 Recommended Next Steps")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("<div class='soft-card'><h4>1️⃣ Resume Management</h4>", unsafe_allow_html=True)
        if stats["has_resume"]:
            st.write("Your resume is uploaded and extracted. You can replace it anytime or inspect extracted text.")
        else:
            st.write("Start by uploading your PDF or DOCX resume (max 5 MB) to unlock AI evaluation.")
        if st.button("📄 Go to Upload Resume", use_container_width=True, type=("secondary" if stats["has_resume"] else "primary")):
            st.session_state["nav_page"] = "Upload Resume"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='soft-card'><h4>2️⃣ AI Analysis & Coaching</h4>", unsafe_allow_html=True)
        if stats["last_score"] is not None:
            st.write(f"Your current score is **{stats['last_score']:.1f}/100**. Review strengths, weaknesses, and PDF report.")
        else:
            st.write("Run weighted scoring, strengths/weaknesses detection, skills gap mapping, and bullet rewrites.")
        if st.button("🤖 Open Resume Analysis", use_container_width=True, type=("primary" if stats["has_resume"] else "secondary")):
            st.session_state["nav_page"] = "Resume Analysis"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with c3:
        st.markdown("<div class='soft-card'><h4>3️⃣ Job Matching</h4>", unsafe_allow_html=True)
        if stats["total_jobs"] > 0:
            st.write(f"You have **{stats['total_jobs']}** matched job recommendations ready to filter, compare, and track.")
        else:
            st.write("Customize your job preferences and discover opportunities scored against your resume.")
        if st.button("💼 Explore Job Matches", use_container_width=True):
            st.session_state["nav_page"] = "Job Recommendations" if stats["total_jobs"] > 0 else "Job Preferences"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Onboarding & Recent Activity
    col_act, col_guide = st.columns([1.3, 1])
    with col_act:
        st.markdown("<div class='soft-card'><h4>🕒 Recent Activity</h4>", unsafe_allow_html=True)
        if not activities:
            st.info("No recent actions yet. Upload your resume to get started!")
        else:
            for act in activities:
                st.markdown(f"- **{act['activity_type']}**: {act['description']} _({str(act['created_at'])[:16]})_")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_guide:
        st.markdown("<div class='soft-card'><h4>💡 First-Time Onboarding Tips</h4>", unsafe_allow_html=True)
        st.markdown(
            """
            - Complete your **My Profile** (experience years & education) for more accurate job match scoring.
            - Check **Improve Resume** after analysis to mark applied edits and raise your score.
            - Use **Job Preferences** to filter out unwanted keywords and prioritize remote or local roles.
            """
        )
        st.markdown("</div>", unsafe_allow_html=True)


def dashboard_page() -> None:
    """Render the authenticated dashboard frame, sidebar navigation, and active module."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Session expired. Please log in again.")
        st.session_state["page"] = "Login"
        st.rerun()
        return

    user = get_user_by_id(current["id"]) or current

    if "nav_page" not in st.session_state or st.session_state["nav_page"] not in NAV_OPTIONS:
        st.session_state["nav_page"] = "Overview"

    # Sidebar Navigation
    st.sidebar.markdown("## 💼 AI Career Assistant")
    st.sidebar.caption(f"Signed in as **{user['name']}**")

    current_idx = NAV_OPTIONS.index(st.session_state["nav_page"])
    selected = st.sidebar.radio(
        "Navigation",
        NAV_OPTIONS,
        index=current_idx,
        key="sidebar_nav_radio",
    )
    if selected != st.session_state["nav_page"]:
        st.session_state["nav_page"] = selected
        st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        logout_user()
        st.session_state["page"] = "Login"
        st.rerun()

    # Active Module Breadcrumb (top logout removed per UI spec)
    st.caption(
        f"AI-Powered Resume Analysis & Intelligent Job Recommendation System · "
        f"Active Module: **{st.session_state['nav_page']}**"
    )

    active_page = st.session_state["nav_page"]
    if active_page == "Overview":
        _render_overview(user)
    elif active_page == "My Profile":
        profile_page()
    elif active_page == "Upload Resume":
        upload_resume_page()
    elif active_page == "Resume Analysis":
        analysis_page()
    elif active_page == "Skills Gap":
        skills_gap_page()
    elif active_page == "Improve Resume":
        improvement_page()
    elif active_page == "Job Preferences":
        job_preferences_page()
    elif active_page == "Job Recommendations":
        job_recommendations_page()
    elif active_page == "Settings":
        settings_page()

    # Compact, subtle Logout button positioned at bottom-right across all authenticated pages
    st.write("")
    st.markdown("<div class='bottom-logout-wrap'></div>", unsafe_allow_html=True)
    _, _, bottom_right_col = st.columns([6, 1, 1.1])
    with bottom_right_col:
        if st.button("🚪 Logout", key="bottom_right_logout_btn"):
            logout_user()
            st.session_state["page"] = "Login"
            st.rerun()
