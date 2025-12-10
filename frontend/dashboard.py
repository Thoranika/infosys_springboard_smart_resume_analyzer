# frontend/dashboard.py

import sys, os
sys.path.append(os.path.dirname(__file__))              # frontend
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # project root

from datetime import datetime

import streamlit as st

from backend.auth import get_current_user, logout_user
from utils.database import (
    get_resume_analysis_for_user,
    get_job_recommendations_for_user,
    get_user_by_id,
)
from resume_upload import resume_upload_page


def format_datetime(dt_str: str | None) -> str:
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str


def show_header(user: dict):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### 👋 Welcome, **{user['name']}**")
        st.caption(f"Logged in as {user['email']}")
    with col2:
        if st.button("Logout", key="logout_btn"):
            logout_user()
            st.success("You have been logged out.")
            st.session_state["page"] = "Login"
            st.rerun()


def show_quick_stats(user: dict):
    st.subheader("Quick Stats")
    user_id = user["id"]
    analyses = get_resume_analysis_for_user(user_id)
    jobs = get_job_recommendations_for_user(user_id)

    last_analysis_date = analyses[0]["analyzed_at"] if analyses else None
    resume_status = "Uploaded" if user.get("resume_path") else "Not uploaded yet"
    job_count = len(jobs)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Resume Status", resume_status)
    with c2:
        st.metric("Last Analysis", format_datetime(last_analysis_date))
    with c3:
        st.metric("Job Recommendations", job_count)


def show_recent_activity(user: dict):
    st.subheader("Recent Activity")
    user_id = user["id"]
    analyses = get_resume_analysis_for_user(user_id)
    jobs = get_job_recommendations_for_user(user_id)

    events = []
    for a in analyses[:3]:
        events.append({"time": a["analyzed_at"], "text": "Resume analysis completed"})
    for j in jobs[:3]:
        events.append(
            {"time": j["scraped_at"], "text": f"Job recommended: {j['job_title']}"}
        )

    events.sort(key=lambda e: e["time"] or "", reverse=True)
    events = events[:5]

    if not events:
        st.info("No recent activity yet. Upload your resume to get started!")
        return

    for e in events:
        st.markdown(f"- **{format_datetime(e['time'])}** – {e['text']}")


def show_call_to_actions(user: dict):
    st.subheader("Next Steps")
    user_id = user["id"]
    analyses = get_resume_analysis_for_user(user_id)
    jobs = get_job_recommendations_for_user(user_id)

    has_resume = bool(user.get("resume_path"))
    has_analysis = bool(analyses)
    has_jobs = bool(jobs)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("##### 📄 Resume")
        if has_resume:
            st.success("Resume uploaded.")
        else:
            st.warning("No resume uploaded. Upload to get started.")
    with col2:
        st.markdown("##### 🧠 Resume Analysis")
        if has_analysis:
            st.success("Analysis available.")
        else:
            st.info("Analysis not available. Upload resume first.")
    with col3:
        st.markdown("##### 💼 Job Recommendations")
        if has_jobs:
            st.success("Job matches found.")
        else:
            st.info("No job recommendations yet.")


def show_profile_section(user: dict):
    st.subheader("My Profile")
    st.write(f"**Name:** {user['name']}")
    st.write(f"**Email:** {user['email']}")
    if user.get("resume_path"):
        st.write(f"**Resume file:** `{os.path.basename(user['resume_path'])}`")
    else:
        st.write("**Resume file:** Not uploaded")


def show_upload_section(user: dict):
    st.subheader("Upload Resume")
    st.caption("Upload or replace your resume.")
    resume_upload_page()


def show_analysis_section(user: dict):
    st.subheader("Resume Analysis")
    analyses = get_resume_analysis_for_user(user["id"])
    if not analyses:
        st.warning("No analysis available yet. Please upload a resume first.")
        return
    latest = analyses[0]
    st.markdown(f"**Last analyzed at:** {format_datetime(latest['analyzed_at'])}")
    with st.expander("Show extracted resume text"):
        st.text(latest["resume_text"][:5000])


def show_jobs_section(user: dict):
    st.subheader("Job Recommendations")
    jobs = get_job_recommendations_for_user(user["id"])
    if not jobs:
        st.warning("No job recommendations available yet.")
        return
    for j in jobs:
        st.markdown(
            f"**{j['job_title']}**  \n"
            f"{j.get('company_name', 'Unknown company')} – {j.get('location','Unknown location')}  \n"
            f"Match: {j.get('match_percentage', 'N/A')}%"
        )
        if j.get("job_url"):
            st.markdown(f"[Job Link]({j['job_url']})")
        st.markdown("---")


def show_settings_section(user: dict):
    st.subheader("Settings")
    st.info("Settings page placeholder.")


def dashboard_page():
    # user must exist in session (app.py already checked)
    st.markdown("<h1 style='text-align: center; color: #E0FFFF;'>AI-Powered Resume & Job Recommendation System</h1>",
                unsafe_allow_html=True)
    st.write("")
    current = get_current_user()

    if not current:
        st.error("No user in session. Please log in again.")
        st.session_state["page"] = "Login"
        st.rerun()

    user = get_user_by_id(current["id"]) or current

    if "dashboard_page" not in st.session_state:
        st.session_state["dashboard_page"] = "Overview"

    st.sidebar.title("Dashboard")
    page = st.sidebar.radio(
        "Go to",
        ["Overview", "My Profile", "Upload Resume", "Resume Analysis", "Job Recommendations", "Settings"],
        index=["Overview", "My Profile", "Upload Resume", "Resume Analysis", "Job Recommendations", "Settings"].index(
            st.session_state["dashboard_page"]
        ),
    )
    st.session_state["dashboard_page"] = page

    show_header(user)
    st.markdown("---")

    if page == "Overview":
        show_quick_stats(user)
        st.markdown("---")
        show_recent_activity(user)
        st.markdown("---")
        show_call_to_actions(user)
    elif page == "My Profile":
        show_profile_section(user)
    elif page == "Upload Resume":
        show_upload_section(user)
    elif page == "Resume Analysis":
        show_analysis_section(user)
    elif page == "Job Recommendations":
        show_jobs_section(user)
    elif page == "Settings":
        show_settings_section(user)
