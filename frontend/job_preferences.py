"""Job Search Customization & Preferences UI (Milestone 3 Task 19)."""

from __future__ import annotations

import streamlit as st

from backend.auth import get_current_user
from backend.job_search import search_jobs_for_user
from backend.scraper import build_linkedin_search_url
from backend.skills_analyzer import extract_skills_deterministic
from utils.database import (
    get_job_preferences,
    get_latest_resume_analysis,
    get_search_history_for_user,
    reset_job_preferences,
    save_job_preferences,
)
from utils.helpers import inject_custom_css

COMMON_LOCATIONS = [
    "Remote",
    "Bengaluru",
    "Hyderabad",
    "Mumbai",
    "New York, NY",
    "San Francisco, CA",
    "Austin, TX",
    "Seattle, WA",
    "Boston, MA",
    "Chicago, IL",
    "London",
]

INDUSTRY_OPTIONS = [
    "Technology",
    "Software & AI",
    "FinTech",
    "Healthcare",
    "E-Commerce",
    "Cloud & Cybersecurity",
    "Data & Analytics",
    "Consulting",
]


def _parse_csv_tags(raw: str) -> list[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


def job_preferences_page() -> None:
    """Render Job Search Preferences, Search Execution with Progress, and Search History."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Please log in to customize job search preferences.")
        return

    st.markdown(
        """
        <div class="hero-banner">
            <h2>🎯 Job Search Customization & Preferences</h2>
            <p>Tailor target titles, locations, work modes, and keywords, then launch intelligent job discovery.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    prefs = get_job_preferences(current["id"])

    with st.container():
        st.markdown("<div class='soft-card'><h4>Core Search Preferences</h4>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            desired_title = st.text_input(
                "Desired Job Title",
                value=prefs.get("desired_title") or "Software Developer",
                placeholder="e.g., Data Scientist, Software Engineer",
            )
            saved_locs = prefs.get("preferred_locations") or []
            loc_choices = list(dict.fromkeys(COMMON_LOCATIONS + saved_locs))
            preferred_locations = st.multiselect(
                "Preferred Locations",
                options=loc_choices,
                default=[l for l in saved_locs if l in loc_choices],
            )
            custom_loc = st.text_input(
                "Additional City/Country (comma-separated, optional)",
                placeholder="e.g., Toronto, Berlin",
            )
            if custom_loc.strip():
                preferred_locations = list(dict.fromkeys(preferred_locations + _parse_csv_tags(custom_loc)))

            remote_opts = ["Only Remote", "Hybrid", "On-site", "Any"]
            rem_idx = remote_opts.index(prefs["remote_preference"]) if prefs.get("remote_preference") in remote_opts else 3
            remote_preference = st.radio("Remote Work Preference", remote_opts, index=rem_idx, horizontal=True)

        with c2:
            exp_opts = ["Entry Level", "Mid Level", "Senior", "Lead/Manager"]
            exp_idx = exp_opts.index(prefs["experience_level"]) if prefs.get("experience_level") in exp_opts else 0
            experience_level = st.selectbox("Experience Level", exp_opts, index=exp_idx)

            st.markdown("**Job Types**")
            jt_cols = st.columns(4)
            saved_types = set(prefs.get("job_types") or ["Full-time"])
            job_types = []
            for idx_jt, jt in enumerate(["Full-time", "Part-time", "Contract", "Internship"]):
                if jt_cols[idx_jt].checkbox(jt, value=(jt in saved_types), key=f"pref_jt_{jt}"):
                    job_types.append(jt)

            min_salary = st.number_input(
                "Minimum Annual Salary Expectation (USD, 0 = Any)",
                min_value=0,
                max_value=500000,
                step=5000,
                value=int(prefs.get("min_salary") or 0),
            )

            industries = st.multiselect(
                "Industries of Interest",
                options=INDUSTRY_OPTIONS,
                default=[i for i in (prefs.get("industries") or []) if i in INDUSTRY_OPTIONS],
            )

            cs_opts = ["Any", "Startup", "Mid-size", "Enterprise"]
            cs_idx = cs_opts.index(prefs["company_size"]) if prefs.get("company_size") in cs_opts else 0
            company_size = st.selectbox("Company Size Preference", cs_opts, index=cs_idx)

        min_match_threshold = st.slider(
            "Default Minimum Match Threshold (%)",
            min_value=0,
            max_value=95,
            value=int(prefs.get("min_match_threshold") if prefs.get("min_match_threshold") is not None else 60),
            step=5,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("⚙️ Advanced Search Filters & Automated Notifications"):
        adv1, adv2 = st.columns(2)
        with adv1:
            include_kw_str = st.text_input(
                "Keywords to Include (comma-separated)",
                value=", ".join(prefs.get("include_keywords") or []),
                placeholder="e.g., Python, FastAPI, AI",
            )
            exclude_kw_str = st.text_input(
                "Keywords to Exclude (comma-separated)",
                value=", ".join(prefs.get("exclude_keywords") or []),
                placeholder="e.g., sales, cold calling, unpaid",
            )
            max_commute_mins = st.slider(
                "Maximum Commute Time for On-Site Jobs (minutes)",
                min_value=15,
                max_value=120,
                value=int(prefs.get("max_commute_mins") or 60),
                step=15,
            )
        with adv2:
            visa_sponsorship = st.checkbox(
                "Visa Sponsorship Required",
                value=bool(prefs.get("visa_sponsorship")),
            )
            preferred_companies = st.text_area(
                "Preferred Companies (one per line or comma-separated)",
                value=prefs.get("preferred_companies") or "",
                height=80,
                placeholder="e.g., Google, Microsoft, Anthropic",
            )
            sched_opts = ["Disabled", "Daily", "Weekly"]
            sched_idx = sched_opts.index(prefs["schedule_frequency"]) if prefs.get("schedule_frequency") in sched_opts else 0
            schedule_frequency = st.selectbox(
                "Automated Job Check Frequency (In-App Refresh)",
                sched_opts,
                index=sched_idx,
            )
            email_notifications = st.checkbox(
                "Enable New Matching Job Notifications",
                value=bool(prefs.get("email_notifications")),
            )

    updated_prefs = {
        "desired_title": desired_title.strip() or "Software Developer",
        "preferred_locations": preferred_locations,
        "remote_preference": remote_preference,
        "experience_level": experience_level,
        "job_types": job_types or ["Full-time"],
        "min_salary": int(min_salary),
        "industries": industries,
        "company_size": company_size,
        "include_keywords": _parse_csv_tags(include_kw_str),
        "exclude_keywords": _parse_csv_tags(exclude_kw_str),
        "max_commute_mins": int(max_commute_mins),
        "visa_sponsorship": bool(visa_sponsorship),
        "preferred_companies": preferred_companies.strip(),
        "min_match_threshold": float(min_match_threshold),
        "schedule_frequency": schedule_frequency,
        "email_notifications": bool(email_notifications),
    }

    b1, b2, b3, b4 = st.columns(4)
    save_clicked = b1.button("💾 Save Preferences", use_container_width=True)
    reset_clicked = b2.button("↩️ Reset Defaults", use_container_width=True)
    find_clicked = b3.button("🔍 Find Jobs Now", type="primary", use_container_width=True)
    refresh_clicked = b4.button("🔄 Refresh Recommendations", use_container_width=True)

    latest_resume = get_latest_resume_analysis(current["id"])
    top_skills = (
        extract_skills_deterministic(latest_resume["resume_text"]).get("programming_languages", [])[:2]
        if latest_resume and latest_resume.get("resume_text")
        else []
    )
    linkedin_url = build_linkedin_search_url(
        query=updated_prefs["desired_title"],
        location=updated_prefs["preferred_locations"][0] if updated_prefs["preferred_locations"] else "",
        remote_preference=updated_prefs["remote_preference"],
        experience_level=updated_prefs["experience_level"],
        job_types=updated_prefs["job_types"],
        resume_skills=top_skills,
    )
    li_col1, li_col2 = st.columns([1.4, 2.6])
    with li_col1:
        st.link_button("🔗 Open Customized LinkedIn Search", linkedin_url, use_container_width=True)
    with li_col2:
        st.caption(f"Dynamic LinkedIn Search Link: {linkedin_url}")

    if save_clicked:
        save_job_preferences(current["id"], updated_prefs)
        st.success("✅ Job preferences saved to your profile.")

    if reset_clicked:
        reset_job_preferences(current["id"])
        st.info("Preferences reset to defaults.")
        st.rerun()

    if find_clicked or refresh_clicked:
        save_job_preferences(current["id"], updated_prefs)
        st.session_state["cancel_job_search"] = False

        status_box = st.empty()
        prog_bar = st.progress(0.05, text="Initializing job search...")
        cancel_placeholder = st.empty()
        if cancel_placeholder.button("🛑 Cancel Search"):
            st.session_state["cancel_job_search"] = True

        def _on_progress(msg: str, pct: float, eta: float) -> None:
            prog_bar.progress(min(1.0, max(0.05, pct)), text=f"{msg} (Est. {eta:.1f}s remaining)")
            status_box.info(msg)

        result = search_jobs_for_user(
            user_id=current["id"],
            preferences=updated_prefs,
            progress_callback=_on_progress,
            cancel_check=lambda: bool(st.session_state.get("cancel_job_search")),
        )
        cancel_placeholder.empty()
        prog_bar.empty()
        status_box.empty()

        new_cnt = result["new_jobs_count"]
        total_cnt = result["total_found"]
        sources = ", ".join(result["sources_used"])
        st.session_state["last_new_jobs_count"] = new_cnt

        if new_cnt > 0:
            st.success(f"🔔 **{new_cnt} new job(s) found** ({total_cnt} total processed from {sources})!")
        else:
            st.info(f"✅ Refreshed {total_cnt} jobs from {sources}. No brand-new postings since last search.")

        if result.get("errors"):
            with st.expander("⚠️ Source Notes"):
                for err in result["errors"]:
                    st.caption(err)

        if st.button("➡️ View Ranked Job Recommendations", type="primary"):
            st.session_state["nav_page"] = "Job Recommendations"
            st.rerun()

    # Recent Search History
    st.markdown("### 🕒 Recent Search History")
    history = get_search_history_for_user(current["id"], limit=8)
    if not history:
        st.caption("No past job searches recorded yet. Click **Find Jobs Now** above to run your first search.")
    else:
        for h in history:
            h_col1, h_col2 = st.columns([3.5, 1])
            with h_col1:
                st.markdown(
                    f"**{h['query_title']}** ({h['locations'] or 'Any'}) — "
                    f"`{h['jobs_found_count']} jobs` (`+{h['new_jobs_count']} new`) · _{str(h['searched_at'])[:16]}_"
                )
            with h_col2:
                if st.button("Re-run", key=f"rerun_hist_{h['id']}", use_container_width=True):
                    rerun_prefs = dict(updated_prefs)
                    rerun_prefs["desired_title"] = h["query_title"]
                    save_job_preferences(current["id"], rerun_prefs)
                    res = search_jobs_for_user(current["id"], preferences=rerun_prefs)
                    st.success(f"Re-ran '{h['query_title']}': {res['total_found']} jobs ({res['new_jobs_count']} new).")
                    st.rerun()
