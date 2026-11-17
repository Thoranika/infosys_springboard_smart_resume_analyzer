"""Job Recommendations, Filtering, Comparison & Application Tracker UI (Milestone 3 Task 18)."""

from __future__ import annotations

import html
import math
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from backend.auth import get_current_user
from backend.job_filter import _parse_min_salary_from_text, filter_jobs
from backend.job_recommendations import (
    _applicants_numeric,
    _salary_numeric,
    compare_jobs,
    generate_application_tips,
    rank_job_recommendations,
    update_job_application_status,
)
from backend.job_search import search_jobs_for_user
from backend.scraper import (
    build_linkedin_job_fallback_url,
    build_linkedin_search_url,
    is_verified_linkedin_job_url,
)
from backend.skills_analyzer import extract_skills_deterministic
from utils.database import (
    delete_job_application,
    get_job_applications_for_user,
    get_job_preferences,
    get_job_recommendations_for_user,
    get_latest_resume_analysis,
    get_user_by_id,
)
from utils.helpers import inject_custom_css, match_badge_class, render_chips_html

ITEMS_PER_PAGE = 20


def _company_initials(company: str) -> str:
    parts = [p[0].upper() for p in (company or "Co").split() if p]
    return "".join(parts[:2]) or "CO"


def _render_job_card(
    job: Dict[str, Any],
    user_id: int,
    user: Dict[str, Any],
    resume_data: Dict[str, Any],
    tracked_map: Dict[int, Dict[str, Any]],
    key_prefix: str = "rec",
) -> None:
    jid = job["id"]
    score = float(job.get("match_percentage") or 0.0)
    badge_cls = match_badge_class(score)
    initials = html.escape(_company_initials(job.get("company_name") or ""))
    title = html.escape(str(job.get("job_title") or "Role"))
    company = html.escape(str(job.get("company_name") or "Company"))
    location = html.escape(str(job.get("location") or "Not specified"))
    remote = html.escape(str(job.get("remote_status") or "On-site"))
    posted = html.escape(str(job.get("posted_date") or "Recent"))
    source = html.escape(str(job.get("source") or "Job Feed"))
    salary = html.escape(str(job.get("salary_range") or "Unavailable"))
    applicants = html.escape(str(job.get("applicants_count") or "Unavailable"))

    featured_badge = "<span class='badge-featured'>⭐ Featured</span>" if job.get("is_featured") else ""
    urgent_badge = "<span class='badge-urgent'>⚡ Apply First</span>" if job.get("is_apply_first") else ""
    tracked = tracked_map.get(jid)
    tracked_status = tracked["status"] if tracked else None
    status_pill = (
        f"<span class='chip chip-blue'>{html.escape(tracked_status)}</span>" if tracked_status else ""
    )

    st.markdown(
        f"""
        <div class="job-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
                <div style="display:flex; gap:12px; align-items:center;">
                    <div style="width:44px; height:44px; border-radius:10px; background:#15171F; color:#3498F5;
                                font-weight:700; display:flex; align-items:center; justify-content:center;
                                border:1px solid #343640; flex-shrink:0;">
                        {initials}
                    </div>
                    <div>
                        <div style="font-size:1.05rem; font-weight:700; color:#F5F6FA;">
                            {title} {featured_badge} {urgent_badge} {status_pill}
                        </div>
                        <div style="font-size:0.9rem; color:#A8ACBA;">
                            <strong style="color:#F5F6FA;">{company}</strong> · 📍 {location} ({remote}) · 🗓️ {posted}
                        </div>
                    </div>
                </div>
                <div style="text-align:right; flex-shrink:0;">
                    <span class="{badge_cls}">{score:.0f}% Match</span>
                    <div style="font-size:0.74rem; color:#A8ACBA; margin-top:4px;">{source}</div>
                </div>
            </div>
            <div style="margin-top:0.55rem; font-size:0.84rem; color:#A8ACBA;">
                <strong style="color:#F5F6FA;">Salary:</strong> {salary} &nbsp;|&nbsp;
                <strong style="color:#F5F6FA;">Applicants:</strong> {applicants} &nbsp;|&nbsp;
                <strong style="color:#F5F6FA;">Type:</strong> {html.escape(str(job.get('job_type') or 'Full-time'))} ({html.escape(str(job.get('experience_level') or 'Mid Level'))})
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Progress bar match indicator + quick actions
    st.progress(max(0.0, min(1.0, score / 100.0)))

    b1, b2, b3, b4 = st.columns([1.3, 1, 1, 1])
    job_url = (job.get("job_url") or "").strip()
    is_linkedin_direct = is_verified_linkedin_job_url(job_url)
    is_valid_third_party = job_url.startswith("http") and ".example/" not in job_url and not is_linkedin_direct
    linkedin_fallback_url = build_linkedin_job_fallback_url(
        str(job.get("job_title") or ""),
        str(job.get("company_name") or ""),
        str(job.get("location") or ""),
    )

    with b1:
        if is_linkedin_direct:
            st.link_button("🔗 Apply on LinkedIn", job_url, use_container_width=True)
        elif is_valid_third_party:
            st.link_button("🔗 Apply on Source", job_url, use_container_width=True)
        else:
            st.link_button("🔍 Search on LinkedIn", linkedin_fallback_url, use_container_width=True)
    with b2:
        if st.button(
            "✅ Saved" if tracked_status == "Saved" else "🔖 Save Job",
            key=f"{key_prefix}_save_{jid}",
            use_container_width=True,
        ):
            update_job_application_status(user_id, jid, "Saved")
            st.success(f"Saved '{job.get('job_title')}'!")
            st.rerun()
    with b3:
        if st.button("✉️ Mark Applied", key=f"{key_prefix}_apply_{jid}", use_container_width=True):
            update_job_application_status(user_id, jid, "Applied")
            st.success(f"Marked '{job.get('job_title')}' as Applied!")
            st.rerun()
    with b4:
        if st.button("🚫 Not Interested", key=f"{key_prefix}_hide_{jid}", use_container_width=True):
            update_job_application_status(user_id, jid, "Not Interested")
            st.info("Removed from active recommendations.")
            st.rerun()

    with st.expander("📋 View Full Details, Match Breakdown & Application Tips"):
        bd = job.get("match_breakdown") or {}
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Skills (50%)", f"{bd.get('skills_match', 0)}%")
        mc2.metric("Experience (25%)", f"{bd.get('experience_match', 0)}%")
        mc3.metric("Education (15%)", f"{bd.get('education_match', 0)}%")
        mc4.metric("Responsibilities (10%)", f"{bd.get('responsibilities_match', 0)}%")

        if job.get("match_explanation"):
            st.info(f"**Match Reasoning:** {job['match_explanation']}")

        sk1, sk2 = st.columns(2)
        with sk1:
            st.markdown("**✅ Matching Skills**")
            st.markdown(render_chips_html(bd.get("matching_skills") or [], variant="green"), unsafe_allow_html=True)
        with sk2:
            st.markdown("**❌ Missing Skills**")
            st.markdown(
                render_chips_html(bd.get("missing_skills") or [], variant="red", empty_text="No skill gaps!"),
                unsafe_allow_html=True,
            )

        st.markdown("**Job Description**")
        st.write(job.get("job_description") or "No detailed description provided by source.")

        if is_linkedin_direct:
            st.caption(f"✅ Verified LinkedIn job posting: {job_url}")
        elif is_valid_third_party:
            st.caption(
                f"📌 Original Source: **{source}** ({job_url}) · "
                f"[🔍 Find similar role on LinkedIn (Search Link)]({linkedin_fallback_url})"
            )
        else:
            st.caption(
                f"🔍 Individual posting URL unavailable for this fallback listing — "
                f"[Open LinkedIn Search for '{job.get('job_title')}' at '{job.get('company_name')}' (Search Link)]({linkedin_fallback_url})"
            )

        st.markdown("---")
        tips_key = f"tips_loaded_{jid}"
        if st.button("💡 View / Generate Personalized Application Tips", key=f"{key_prefix}_tips_btn_{jid}"):
            st.session_state[tips_key] = True

        if st.session_state.get(tips_key) or (job.get("application_tips") and job["application_tips"].get("customized_cover_letter")):
            tips = generate_application_tips(user, resume_data, job)
            t1, t2 = st.columns(2)
            with t1:
                st.markdown("**🎯 Skills to Highlight**")
                for s in tips.get("skills_to_highlight") or []:
                    st.markdown(f"- {s}")
                st.markdown("**🗣️ Interview Talking Points**")
                for tp in tips.get("interview_talking_points") or []:
                    st.markdown(f"- {tp}")
                st.markdown("**🔍 Company Research Links**")
                comp_q = str(job.get("company_name") or "").replace(" ", "+")
                st.markdown(
                    f"- [Search {job.get('company_name')} News & Reviews](https://www.google.com/search?q={comp_q}+engineering+careers)"
                )
                for cr in tips.get("company_research_tips") or []:
                    st.markdown(f"- {cr}")
            with t2:
                st.markdown("**🧩 Addressing Missing Requirements**")
                for g in tips.get("how_to_address_gaps") or []:
                    st.markdown(f"- {g}")
                st.markdown("**❓ Likely Interview Questions**")
                for iq in tips.get("common_interview_questions") or []:
                    st.markdown(f"- {iq}")
                st.markdown("**🔑 Resume Keyword Tweaks**")
                for kw in tips.get("resume_keyword_tweaks") or []:
                    st.markdown(f"- {kw}")

            st.markdown("**✉️ Customized Cover Letter Draft**")
            st.text_area(
                "Tailored Cover Letter",
                value=tips.get("customized_cover_letter") or "",
                height=200,
                key=f"{key_prefix}_cl_{jid}",
            )


def job_recommendations_page() -> None:
    """Render the Job Recommendations dashboard, filters, comparison, and application tracker."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Please log in to view job recommendations.")
        return

    user = get_user_by_id(current["id"]) or current
    prefs = get_job_preferences(current["id"])
    latest_resume = get_latest_resume_analysis(current["id"])
    resume_text = (latest_resume or {}).get("resume_text") or ""
    resume_data = {
        "resume_text": resume_text,
        "extracted_skills": extract_skills_deterministic(resume_text),
    }

    st.markdown(
        """
        <div class="hero-banner">
            <h2>💼 Intelligent Job Recommendations & Tracker</h2>
            <p>Jobs ranked by weighted skills, experience, education, and responsibility fit against your resume.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not resume_text:
        st.warning("Upload your resume first so we can calculate accurate job match scores.")
        if st.button("📤 Go to Upload Resume", type="primary"):
            st.session_state["nav_page"] = "Upload Resume"
            st.rerun()
        return

    all_jobs = get_job_recommendations_for_user(current["id"])
    if not all_jobs:
        st.info("No job listings loaded for your account yet. Fetch matching jobs using your preferences now.")
        c_btn1, c_btn2 = st.columns([1.3, 1])
        with c_btn1:
            if st.button("🔍 Find Matching Jobs Now", type="primary", use_container_width=True):
                with st.spinner("Searching job sources and scoring matches against your resume..."):
                    res = search_jobs_for_user(current["id"], preferences=prefs)
                st.success(f"Found and scored {res['total_found']} matching opportunities!")
                st.rerun()
        with c_btn2:
            if st.button("🎯 Customize Preferences First", use_container_width=True):
                st.session_state["nav_page"] = "Job Preferences"
                st.rerun()
        return

    tracked_apps = get_job_applications_for_user(current["id"])
    tracked_map = {a["job_id"]: a for a in tracked_apps}

    # ---------------- SUMMARY STATISTICS ----------------
    today_iso = datetime.now(timezone.utc).date().isoformat()
    avg_score = round(sum(float(j.get("match_percentage") or 0.0) for j in all_jobs) / len(all_jobs), 1)
    new_today = sum(1 for j in all_jobs if (j.get("posted_date") or "").startswith(today_iso))
    high_matches = sum(1 for j in all_jobs if float(j.get("match_percentage") or 0.0) >= 75.0)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Jobs Found", f"{len(all_jobs)}")
    s2.metric("Average Match Score", f"{avg_score}%")
    s3.metric("Posted Today / Fresh", f"{new_today}")
    s4.metric("Strong Matches (75%+)", f"{high_matches}")

    # ---------------- SIDEBAR REAL-TIME FILTERS ----------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Job Filters")

    default_thresh = int(prefs.get("min_match_threshold") if prefs.get("min_match_threshold") is not None else 60)
    if "override_match_threshold" in st.session_state:
        default_thresh = int(st.session_state.pop("override_match_threshold"))

    min_threshold = st.sidebar.slider("Minimum Match %", 0, 95, value=default_thresh, step=5)
    remote_filter = st.sidebar.radio("Work Mode", ["Any", "Only Remote", "Hybrid", "On-site"], index=0)

    unique_cities = sorted(
        {str(j.get("location") or "").strip() for j in all_jobs if j.get("location")}
    )
    selected_locs = st.sidebar.multiselect("Filter by Location", options=unique_cities, default=[])

    selected_types = st.sidebar.multiselect(
        "Job Type",
        options=["Full-time", "Part-time", "Contract", "Internship"],
        default=[],
    )
    selected_levels = st.sidebar.multiselect(
        "Experience Level",
        options=["Entry Level", "Mid Level", "Senior", "Lead/Manager"],
        default=[],
    )
    posted_window = st.sidebar.selectbox(
        "Posted Date",
        ["All Time", "Last 24 hours", "Last week", "Last month"],
    )
    posted_days_map = {"All Time": None, "Last 24 hours": 1, "Last week": 7, "Last month": 30}
    min_sal_filter = st.sidebar.number_input("Minimum Salary ($)", min_value=0, max_value=400000, step=10000, value=0)

    # Apply real-time filters
    filtered_jobs = filter_jobs(
        all_jobs,
        {
            "min_match_threshold": min_threshold,
            "locations": selected_locs,
            "remote_preference": remote_filter,
            "job_types": selected_types,
            "experience_levels": selected_levels,
            "posted_within_days": posted_days_map[posted_window],
            "min_salary": min_sal_filter,
        },
    )

    ranked_bundle = rank_job_recommendations(filtered_jobs, user_preferences=prefs)
    ranked_jobs = ranked_bundle["ranked_jobs"]

    # ---------------- TABS ----------------
    tab_rec, tab_cmp, tab_saved = st.tabs(
        [
            f"💼 Recommended Jobs ({len(ranked_jobs)})",
            "⚖️ Compare Jobs",
            f"📌 Saved & Applied Jobs ({len(tracked_apps)})",
        ]
    )

    with tab_rec:
        top_skills = resume_data["extracted_skills"].get("programming_languages", [])[:2]
        pref_locs = prefs.get("preferred_locations") or []
        dynamic_linkedin_url = build_linkedin_search_url(
            query=prefs.get("desired_title") or user.get("target_role") or "Software Developer",
            location=pref_locs[0] if pref_locs else "",
            remote_preference=prefs.get("remote_preference") or "Any",
            experience_level=prefs.get("experience_level") or "",
            job_types=prefs.get("job_types") or [],
            resume_skills=top_skills,
        )

        top_c1, top_c2, top_c3, top_c4 = st.columns([1.6, 1.2, 1, 1.1])
        with top_c1:
            sort_by = st.selectbox(
                "Sort Recommendations By",
                ["Best Match", "Most Recent", "Highest Salary", "Fewest Applicants"],
            )
        with top_c2:
            tier_view = st.selectbox(
                "Score Tier Filter",
                ["All Matching", "Best Matches (Top 10)", "Excellent (85-100%)", "Good (70-84%)", "Fair (60-69%)"],
            )
        with top_c3:
            st.write("")
            st.write("")
            if st.button("🔄 Fetch Latest Jobs", use_container_width=True):
                with st.spinner("Refreshing job feeds..."):
                    search_jobs_for_user(current["id"], preferences=prefs)
                st.rerun()
        with top_c4:
            st.write("")
            st.write("")
            st.link_button("🔗 Search on LinkedIn", dynamic_linkedin_url, use_container_width=True)

        display_list = list(ranked_jobs)
        if tier_view == "Best Matches (Top 10)":
            display_list = ranked_bundle["best_matches"][:10]
        elif tier_view == "Excellent (85-100%)":
            display_list = ranked_bundle["excellent"]
        elif tier_view == "Good (70-84%)":
            display_list = ranked_bundle["good"]
        elif tier_view == "Fair (60-69%)":
            display_list = ranked_bundle["fair"]

        if sort_by == "Most Recent":
            display_list.sort(key=lambda j: (str(j.get("posted_date") or ""), float(j.get("match_percentage") or 0)), reverse=True)
        elif sort_by == "Highest Salary":
            display_list.sort(key=lambda j: (_salary_numeric(j.get("salary_range")), float(j.get("match_percentage") or 0)), reverse=True)
        elif sort_by == "Fewest Applicants":
            display_list.sort(key=lambda j: (_applicants_numeric(j.get("applicants_count")), -float(j.get("match_percentage") or 0)))

        if not display_list:
            st.warning("No jobs found matching your current filters. Try lowering the match threshold or expanding location filters.")
            ec1, ec2 = st.columns(2)
            with ec1:
                if st.button("📉 Lower Match Threshold to 40%", use_container_width=True):
                    st.session_state["override_match_threshold"] = 40
                    st.rerun()
            with ec2:
                if st.button("🎯 Adjust Search Preferences", use_container_width=True):
                    st.session_state["nav_page"] = "Job Preferences"
                    st.rerun()
        else:
            # Cover Letter Reuse Tip if applicable
            if ranked_bundle["cover_letter_groups"]:
                sample_group = next(iter(ranked_bundle["cover_letter_groups"].items()))
                st.info(
                    f"💡 **Smart Application Batching:** {len(sample_group[1])} jobs share overlapping core skills "
                    f"({sample_group[0]}) — you can efficiently reuse one customized cover letter template across them."
                )

            # Pagination (20 jobs per page)
            total_pages = max(1, math.ceil(len(display_list) / ITEMS_PER_PAGE))
            page_num = st.number_input(
                f"Page (20 jobs per page · {total_pages} page(s))",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
            )
            start_idx = (page_num - 1) * ITEMS_PER_PAGE
            page_jobs = display_list[start_idx : start_idx + ITEMS_PER_PAGE]

            st.caption(f"Showing jobs {start_idx + 1}–{start_idx + len(page_jobs)} of {len(display_list)}")
            for job in page_jobs:
                _render_job_card(job, current["id"], user, resume_data, tracked_map, key_prefix="rec")

    with tab_cmp:
        st.markdown("### ⚖️ Side-by-Side Job Comparison")
        label_map = {f"{j['job_title']} @ {j['company_name']} ({j['match_percentage']:.0f}%)": j for j in ranked_jobs[:30]}
        chosen_labels = st.multiselect(
            "Select 2 to 4 jobs to compare",
            options=list(label_map.keys()),
            default=list(label_map.keys())[:2] if len(label_map) >= 2 else list(label_map.keys()),
            max_selections=4,
        )
        if len(chosen_labels) < 2:
            st.info("Select at least 2 jobs above to view a side-by-side comparison.")
        else:
            cmp_result = compare_jobs([label_map[lbl] for lbl in chosen_labels])
            df_cmp = pd.DataFrame(cmp_result["rows"]).drop(columns=["id"], errors="ignore")
            st.dataframe(df_cmp, use_container_width=True, hide_index=True)
            hl = cmp_result["highlights"]
            hc1, hc2, hc3 = st.columns(3)
            hc1.success(f"🏆 **Highest Match:**\n{hl.get('highest_match', 'N/A')}")
            hc2.info(f"🧩 **Fewest Gaps:**\n{hl.get('fewest_missing_skills', 'N/A')}")
            hc3.warning(f"🕒 **Most Recent:**\n{hl.get('most_recent', 'N/A')}")

    with tab_saved:
        st.markdown("### 📌 Saved & Tracked Applications")
        if not tracked_apps:
            st.info("You haven't saved or applied to any jobs yet. Click **Save Job** or **Mark Applied** on any recommendation.")
        else:
            status_filter = st.radio(
                "Filter by Status",
                ["All", "Saved", "Applied", "Interviewing", "Rejected"],
                horizontal=True,
            )
            filtered_apps = [
                a for a in tracked_apps if status_filter == "All" or a.get("status") == status_filter
            ]
            for app_row in filtered_apps:
                jid = app_row["job_id"]
                with st.container():
                    st.markdown(
                        f"**{app_row['job_title']}** at **{app_row['company_name']}** "
                        f"({app_row['location']}) — Match: **{app_row['match_percentage']:.0f}%** · "
                        f"Status: `{app_row['status']}`"
                    )
                    c_st, c_nt, c_upd, c_del = st.columns([1.3, 2.2, 0.9, 0.9])
                    statuses = ["Saved", "Applied", "Interviewing", "Rejected"]
                    cur_idx = statuses.index(app_row["status"]) if app_row["status"] in statuses else 0
                    new_st = c_st.selectbox(
                        "Status",
                        statuses,
                        index=cur_idx,
                        key=f"app_status_{jid}",
                        label_visibility="collapsed",
                    )
                    new_notes = c_nt.text_input(
                        "Notes",
                        value=app_row.get("notes") or "",
                        placeholder="Interview date, recruiter contact...",
                        key=f"app_notes_{jid}",
                        label_visibility="collapsed",
                    )
                    if c_upd.button("Update", key=f"app_upd_{jid}", use_container_width=True):
                        update_job_application_status(current["id"], jid, new_st, new_notes)
                        st.success("Updated!")
                        st.rerun()
                    if c_del.button("Remove", key=f"app_del_{jid}", use_container_width=True):
                        delete_job_application(current["id"], jid)
                        st.info("Removed from tracker.")
                        st.rerun()
                    st.caption(
                        f"Applied Date: {app_row.get('applied_date') or 'Not yet applied'} | "
                        f"Last Updated: {str(app_row.get('app_updated_at') or '')[:16]}"
                    )
                    st.markdown("---")
