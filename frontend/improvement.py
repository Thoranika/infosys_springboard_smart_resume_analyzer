"""Resume Improvement Suggestions UI with Before/After comparisons and persistent tracking (Milestone 2 Task 13)."""

from __future__ import annotations

import html
import streamlit as st

from backend.auth import get_current_user
from backend.improvement_suggestions import (
    generate_improvement_suggestions,
    update_improvement_item_status,
)
from backend.skills_analyzer import ROLE_STANDARDS, infer_target_role
from utils.database import (
    get_latest_improvement_suggestions,
    get_latest_resume_analysis,
    get_user_by_id,
)
from utils.helpers import inject_custom_css


def improvement_page() -> None:
    """Render actionable improvement plan, before/after examples, and progress tracking."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Please log in to view resume improvements.")
        return

    user = get_user_by_id(current["id"]) or current
    latest_resume = get_latest_resume_analysis(current["id"])

    st.markdown(
        """
        <div class="hero-banner">
            <h2>✨ Personalized Resume Improvement Coach</h2>
            <p>High-impact action items, before-and-after bullet rewrites, section coaching, and progress tracking.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not latest_resume or not latest_resume.get("resume_text"):
        st.warning("Upload your resume first to receive personalized improvement suggestions.")
        if st.button("📤 Go to Upload Resume", type="primary"):
            st.session_state["nav_page"] = "Upload Resume"
            st.rerun()
        return

    resume_text = latest_resume["resume_text"]
    inferred = infer_target_role(resume_text)
    default_role = user.get("target_role") or inferred

    role_options = list(ROLE_STANDARDS.keys())
    idx = role_options.index(default_role) if default_role in role_options else 0

    c1, c2 = st.columns([2.2, 1])
    with c1:
        target_role = st.selectbox("🎯 Target Role for Improvement Tailoring", role_options, index=idx)
    with c2:
        st.write("")
        st.write("")
        gen_btn = st.button("🚀 Generate Improvement Plan", type="primary", use_container_width=True)

    stored_plan = get_latest_improvement_suggestions(current["id"])
    if gen_btn or not stored_plan:
        with st.spinner("Analyzing weaknesses and generating tailored before/after improvements..."):
            analysis_ctx = st.session_state.get("current_analysis") or {}
            plan = generate_improvement_suggestions(
                resume_text=resume_text,
                weaknesses=analysis_ctx.get("weaknesses"),
                skills_gap=analysis_ctx.get("skills_gap"),
                score_data=analysis_ctx.get("score_data"),
                target_role=target_role,
                user_id=current["id"],
                analysis_id=latest_resume.get("id"),
            )
            stored_plan = get_latest_improvement_suggestions(current["id"])
    else:
        plan = stored_plan["suggestions"]

    status_map = (stored_plan or {}).get("status_map") or {}
    all_priority_items = (plan.get("high_impact") or []) + (plan.get("quick_wins") or [])
    applied_count = sum(1 for item in all_priority_items if status_map.get(item.get("id")) == "Applied")

    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated Potential Boost", plan.get("estimated_total_potential_gain", "+15 to +20 pts"))
    m2.metric("Actionable Suggestions", f"{len(all_priority_items)}")
    m3.metric("Applied by You", f"{applied_count} / {len(all_priority_items)}")

    if all_priority_items:
        st.progress(applied_count / len(all_priority_items), text=f"Improvement Checklist Completion: {applied_count}/{len(all_priority_items)}")

    # ---------------- PRIORITY SUGGESTIONS WITH TRACKING ----------------
    st.markdown("### 🔥 High-Impact Improvements & Quick Wins")
    p_col1, p_col2 = st.columns(2)

    def _render_priority_column(items: list, header: str, accent: str) -> None:
        st.markdown(f"#### {header}")
        for item in items:
            item_id = item.get("id") or item.get("title", "item")
            current_status = status_map.get(item_id, "Pending")
            st.markdown(
                f"""
                <div class="soft-card" style="border-left: 5px solid {accent};">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>{html.escape(str(item.get('title', 'Improvement')))}</strong>
                        <span class="chip chip-green">{html.escape(str(item.get('estimated_score_gain', '+3 pts')))}</span>
                    </div>
                    <div style="font-size:0.8rem; color:#A8ACBA; margin-bottom:0.35rem;">Category: {html.escape(str(item.get('category', 'General')))}</div>
                """,
                unsafe_allow_html=True,
            )
            for step in item.get("action_steps") or []:
                st.markdown(f"- {step}")
            new_status = st.radio(
                f"Status for {item.get('title', item_id)}",
                ["Pending", "Applied", "Not Relevant"],
                index=["Pending", "Applied", "Not Relevant"].index(current_status)
                if current_status in {"Pending", "Applied", "Not Relevant"}
                else 0,
                horizontal=True,
                key=f"impr_status_{item_id}",
                label_visibility="collapsed",
            )
            if new_status != current_status:
                update_improvement_item_status(current["id"], item_id, new_status)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with p_col1:
        _render_priority_column(plan.get("high_impact") or [], "🚀 High-Impact Changes", "#2563eb")
    with p_col2:
        _render_priority_column(plan.get("quick_wins") or [], "⚡ Quick Wins", "#16a34a")

    # ---------------- BEFORE VS AFTER EXAMPLES ----------------
    st.markdown("### ✍️ Before vs. After Resume Rewrites")
    for idx, ex in enumerate(plan.get("before_after_examples") or [], start=1):
        st.markdown(f"**Example {idx} — {ex.get('section', 'Experience')}**")
        b_col, a_col = st.columns(2)
        with b_col:
            st.error(f"**Before (Original):**\n\n{ex.get('original', '')}")
        with a_col:
            st.success(f"**After (Improved):**\n\n{ex.get('improved', '')}")
        st.caption(f"💡 Why this works: {ex.get('explanation', '')}")

    # ---------------- WEAKNESS-SPECIFIC ACTIONS ----------------
    st.markdown("### 🎯 Weakness-by-Weakness Action Plan")
    for wa in plan.get("weakness_actions") or []:
        with st.expander(f"🔧 {wa.get('weakness_title', 'Weakness')} ({str(wa.get('severity', 'moderate')).upper()})"):
            for action in wa.get("actions") or []:
                st.markdown(f"- {action}")

    # ---------------- SECTION-BY-SECTION COACHING ----------------
    st.markdown("### 📑 Section-by-Section Recommendations")
    sec_recs = plan.get("section_recommendations") or {}
    if sec_recs:
        tabs = st.tabs(list(sec_recs.keys()))
        for tab, sec_name in zip(tabs, sec_recs.keys()):
            with tab:
                items = sec_recs[sec_name]
                if isinstance(items, list):
                    for tip in items:
                        st.markdown(f"- {tip}")
                else:
                    st.write(items)

    # ---------------- LEARNING RESOURCES & TEMPLATES ----------------
    st.markdown("### 📚 Learning Resources & ATS Resume Templates")
    lr = plan.get("learning_resources") or {}
    lr_col1, lr_col2 = st.columns(2)
    with lr_col1:
        st.markdown("**Skill Courses & Documentation**")
        for sr in lr.get("skill_resources") or []:
            links = ", ".join(
                f"[{r.get('name', 'Course')}]({r.get('url', '#')})" for r in (sr.get("resources") or [])
            )
            st.markdown(f"- **{sr.get('skill')}**: {links or 'Search official documentation'}")
    with lr_col2:
        st.markdown("**Formatting & Resume Templates**")
        for fg in lr.get("formatting_guides") or []:
            st.markdown(f"- [{fg.get('title', 'Template')}]({fg.get('url', '#')})")
