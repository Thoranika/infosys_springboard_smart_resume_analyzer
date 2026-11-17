"""Skills Gap Analysis & Learning Roadmap UI (Milestone 2 Task 10)."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from backend.auth import get_current_user
from backend.skills_analyzer import (
    ROLE_STANDARDS,
    analyze_skills_gap_structured,
    infer_target_role,
)
from utils.database import (
    get_latest_resume_analysis,
    get_skills_analysis_history,
    get_user_by_id,
)
from utils.helpers import inject_custom_css, render_chips_html


def skills_gap_page() -> None:
    """Render detailed Skills Gap Analysis with 6-category breakdown, charts, and learning links."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Please log in to view skills gap analysis.")
        return

    user = get_user_by_id(current["id"]) or current
    latest_resume = get_latest_resume_analysis(current["id"])

    st.markdown(
        """
        <div class="hero-banner">
            <h2>📉 Skills Extraction & Gap Analysis</h2>
            <p>Discover technical, soft, and domain skills in your resume and get a prioritized learning roadmap.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not latest_resume or not latest_resume.get("resume_text"):
        st.warning("Upload your resume first so we can extract your skills.")
        if st.button("📤 Upload Resume", type="primary"):
            st.session_state["nav_page"] = "Upload Resume"
            st.rerun()
        return

    resume_text = latest_resume["resume_text"]
    inferred = infer_target_role(resume_text)
    default_role = user.get("target_role") or inferred

    role_list = list(ROLE_STANDARDS.keys()) + ["Custom Role..."]
    idx = role_list.index(default_role) if default_role in role_list else 0

    c1, c2 = st.columns([2.2, 1])
    with c1:
        choice = st.selectbox(
            f"🎯 Target Role (Auto-inferred from resume: {inferred})",
            role_list,
            index=idx,
            key="skills_gap_role_select",
        )
        if choice == "Custom Role...":
            target_role = st.text_input("Specify Custom Target Role", value=default_role, key="skills_gap_custom_role")
        else:
            target_role = choice
    with c2:
        st.write("")
        st.write("")
        analyze_btn = st.button("🚀 Run Skills Gap Analysis", type="primary", use_container_width=True)

    if analyze_btn or not st.session_state.get("current_skills_gap"):
        with st.spinner("Extracting skills across 6 categories and comparing against industry standards..."):
            gap = analyze_skills_gap_structured(
                resume_text=resume_text,
                target_role=target_role,
                user_id=current["id"],
            )
            st.session_state["current_skills_gap"] = gap

    gap = st.session_state.get("current_skills_gap")
    if not gap:
        return

    extracted = gap["extracted_skills"]
    chart_data = gap["chart_data"]

    # KPI Summary Row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Role Coverage", f"{chart_data['coverage_percentage']}%")
    k2.metric("Skills Identified", f"{chart_data['present_count']}")
    k3.metric("Missing Must-Have", f"{chart_data['missing_critical_count']}")
    k4.metric("Missing Nice-to-Have", f"{chart_data['missing_nice_count']}")

    st.markdown("---")

    # Charts Row
    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown("#### 📊 Present vs. Missing Skills")
        fig1, ax1 = plt.subplots(figsize=(5.2, 3.2), dpi=130, facecolor="#15171F")
        ax1.set_facecolor("#15171F")
        labels = ["Present", "Missing Must-Have", "Missing Nice-to-Have"]
        values = [
            chart_data["present_count"],
            chart_data["missing_critical_count"],
            chart_data["missing_nice_count"],
        ]
        colors = ["#4ADE80", "#F87171", "#FBBF24"]
        bars = ax1.bar(labels, values, color=colors, width=0.52)
        ax1.set_ylabel("Number of Skills", color="#F5F6FA")
        ax1.tick_params(colors="#A8ACBA", labelsize=8.5)
        for spine in ax1.spines.values():
            spine.set_color("#343640")
        ax1.grid(axis="y", linestyle="--", alpha=0.25, color="#A8ACBA")
        for b in bars:
            h = b.get_height()
            ax1.text(b.get_x() + b.get_width() / 2, h + 0.15, f"{int(h)}", ha="center", fontweight="bold", color="#F5F6FA")
        fig1.tight_layout()
        st.pyplot(fig1)
        plt.close(fig1)

    with ch2:
        st.markdown("#### 🧩 Skills by Category")
        cat_dist = chart_data["category_distribution"]
        fig2, ax2 = plt.subplots(figsize=(5.4, 3.2), dpi=130, facecolor="#15171F")
        ax2.set_facecolor("#15171F")
        cats = list(cat_dist.keys())
        counts = list(cat_dist.values())
        y_pos = list(range(len(cats)))
        ax2.barh(y_pos, counts, color="#3498F5", height=0.55)
        ax2.set_yticks(y_pos)
        ax2.set_yticklabels(cats, fontsize=8.5, color="#F5F6FA")
        ax2.invert_yaxis()
        ax2.set_xlabel("Detected Count", color="#F5F6FA")
        ax2.tick_params(colors="#A8ACBA", labelsize=8.5)
        for spine in ax2.spines.values():
            spine.set_color("#343640")
        ax2.grid(axis="x", linestyle="--", alpha=0.25, color="#A8ACBA")
        for i, v in enumerate(counts):
            ax2.text(v + 0.1, i, str(v), va="center", fontweight="bold", fontsize=8.5, color="#F5F6FA")
        fig2.tight_layout()
        st.pyplot(fig2)
        plt.close(fig2)

    # 6-Category Skill Inventory
    st.markdown("### 🗂️ Categorized Skills Extracted from Resume")
    cat_cols = st.columns(3)
    category_specs = [
        ("Programming Languages", "programming_languages", "blue"),
        ("Frameworks & Libraries", "frameworks", "purple"),
        ("Tools & Platforms", "tools", "slate"),
        ("Soft Skills", "soft_skills", "green"),
        ("Domain Knowledge", "domain_knowledge", "amber"),
        ("Certifications", "certifications", "green"),
    ]
    for i, (title, key, variant) in enumerate(category_specs):
        with cat_cols[i % 3]:
            st.markdown(f"<div class='soft-card'><h5>{title}</h5>", unsafe_allow_html=True)
            st.markdown(render_chips_html(extracted.get(key) or [], variant=variant), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    exp_years = extracted.get("skill_experience_years") or {}
    if exp_years:
        st.info("**Explicit Skill Experience Detected:** " + ", ".join(f"{k}: {v}" for k, v in exp_years.items()))

    # Missing Skills Comparison
    m1, m2 = st.columns(2)
    with m1:
        st.markdown("<div class='soft-card'><h5>🚨 Missing Must-Have Skills</h5>", unsafe_allow_html=True)
        st.markdown(
            render_chips_html(gap["missing_critical_skills"], variant="red", empty_text="All critical skills covered!"),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with m2:
        st.markdown("<div class='soft-card'><h5>💡 Missing Nice-to-Have Skills</h5>", unsafe_allow_html=True)
        st.markdown(
            render_chips_html(gap["missing_nice_to_have_skills"], variant="amber", empty_text="All bonus skills covered!"),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # 5-10 Prioritized Learning Recommendations
    st.markdown(f"### 🎓 Prioritized Learning Roadmap ({len(gap['recommendations'])} Recommendations)")
    for idx, rec in enumerate(gap["recommendations"], start=1):
        prio = rec.get("priority", "Medium")
        diff = rec.get("learning_difficulty", "Intermediate")
        with st.expander(f"{idx}. {rec['skill']} — [{prio} Priority | {diff}]", expanded=(idx <= 3)):
            st.write(f"**Category:** {rec.get('category', 'Technical')}")
            st.write(f"**Why It Matters:** {rec.get('why_important', '')}")
            st.write(f"**Typical Use Cases:** {rec.get('use_cases', '')}")
            resources = rec.get("resources") or []
            if resources:
                st.markdown("**Recommended Learning Resources:**")
                for r in resources:
                    st.markdown(f"- [{r.get('name', 'Resource')} ({r.get('platform', 'Docs')})]({r.get('url', '#')})")

    # History Tracking
    history = get_skills_analysis_history(current["id"], limit=6)
    if history:
        with st.expander("🕒 Skills Analysis History"):
            hist_df = pd.DataFrame(
                [
                    {
                        "Date": str(h["created_at"])[:16],
                        "Target Role": h["target_role"],
                        "Coverage %": f"{h['coverage_pct']:.1f}%",
                        "Missing Must-Have": len(h.get("missing_critical") or []),
                    }
                    for h in history
                ]
            )
            st.dataframe(hist_df, use_container_width=True, hide_index=True)
