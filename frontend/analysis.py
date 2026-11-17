"""Resume Analysis Results Dashboard (Milestone 2 Task 12)."""

from __future__ import annotations

import html
import json
import pandas as pd
import streamlit as st

from backend.auth import get_current_user
from backend.llm_analyzer import get_llm_config, get_token_usage_summary
from backend.resume_analyzer import run_full_resume_analysis
from backend.skills_analyzer import ROLE_STANDARDS, infer_target_role
from utils.database import (
    get_latest_resume_analysis,
    get_resume_analysis_for_user,
    get_user_by_id,
)
from utils.helpers import (
    inject_custom_css,
    render_chips_html,
    render_circular_gauge_html,
    score_color_hex,
)
from utils.pdf_generator import generate_analysis_pdf_report


def _load_existing_full_analysis(latest_row: dict) -> dict | None:
    if not latest_row or not latest_row.get("analysis_json"):
        return None
    try:
        parsed = json.loads(latest_row["analysis_json"])
        if (
            isinstance(parsed, dict)
            and parsed.get("score_data")
            and parsed.get("strengths")
            and parsed.get("weaknesses")
            and parsed.get("skills_gap")
        ):
            parsed["analyzed_at"] = latest_row.get("analyzed_at")
            return parsed
    except Exception:
        return None
    return None


def analysis_page() -> None:
    """Render the full AI Resume Analysis dashboard with charts, cards, and PDF export."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Please log in to view resume analysis.")
        return

    user = get_user_by_id(current["id"]) or current
    latest_row = get_latest_resume_analysis(current["id"])

    st.markdown(
        """
        <div class="hero-banner">
            <h2>🤖 AI Resume Analysis & Scoring Dashboard</h2>
            <p>Weighted rubric evaluation, evidence-backed strengths & weaknesses, skills gap mapping, and PDF export.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not latest_row or not latest_row.get("resume_text"):
        st.warning("No uploaded resume found yet. Please upload your resume first.")
        if st.button("📤 Go to Upload Resume", type="primary"):
            st.session_state["nav_page"] = "Upload Resume"
            st.rerun()
        return

    resume_text = latest_row["resume_text"]
    inferred = infer_target_role(resume_text)
    default_role = user.get("target_role") or inferred

    llm_cfg = get_llm_config()
    if llm_cfg["is_live"]:
        st.caption(f"🟢 Live AI Provider Active: **{llm_cfg['active_provider'].upper()}** (`{llm_cfg['model']}`)")
    else:
        st.info(
            "ℹ️ **Evidence-Based Demo Mode Active**: No valid `GEMINI_API_KEY` or `OPENAI_API_KEY` is configured in `.env`. "
            "All scores, strengths, weaknesses, and skills gaps below are computed deterministically from your actual resume text. "
            "Add a live API key in `.env` at any time to enable generative LLM enrichment."
        )

    role_options = list(ROLE_STANDARDS.keys()) + ["Custom Role..."]
    init_idx = role_options.index(default_role) if default_role in role_options else 0

    ctrl1, ctrl2, ctrl3 = st.columns([2, 1.2, 1])
    with ctrl1:
        selected_opt = st.selectbox(
            f"🎯 Target Job Role (Auto-detected: {inferred})",
            role_options,
            index=init_idx,
            key="analysis_role_select",
        )
        if selected_opt == "Custom Role...":
            target_role = st.text_input("Enter Custom Target Role", value=default_role, key="analysis_custom_role")
        else:
            target_role = selected_opt

    with ctrl2:
        st.write("")
        st.write("")
        run_clicked = st.button("🚀 Analyze Resume", type="primary", use_container_width=True)
    with ctrl3:
        st.write("")
        st.write("")
        reanalyze_clicked = st.button("🔄 Re-analyze", use_container_width=True, help="Bypass cache and run fresh evaluation")

    if run_clicked or reanalyze_clicked:
        with st.spinner("Evaluating resume components, strengths, weaknesses, and skill alignment..."):
            result = run_full_resume_analysis(
                user_id=current["id"],
                resume_text=resume_text,
                target_role=target_role,
                force_refresh=reanalyze_clicked,
            )
            st.session_state["current_analysis"] = result
            st.session_state["current_skills_gap"] = result.get("skills_gap")

    analysis_result = st.session_state.get("current_analysis") or _load_existing_full_analysis(latest_row)

    if not analysis_result:
        st.info("Click **🚀 Analyze Resume** above to generate your comprehensive resume evaluation.")
        with st.expander("📄 View Extracted Resume Text"):
            st.text(resume_text)
        return

    score_data = analysis_result["score_data"]
    overall_score = score_data["overall_score"]
    classification = score_data["classification"]
    strengths = analysis_result["strengths"]
    weaknesses = analysis_result["weaknesses"]
    skills_gap = analysis_result["skills_gap"]

    if analysis_result.get("from_cache"):
        st.caption("⚡ Loaded cached analysis for this resume and target role. Click **Re-analyze** to force a fresh run.")

    # ---------------- TOP ACTION BAR ----------------
    act1, act2, act3, act4 = st.columns(4)
    pdf_bytes = generate_analysis_pdf_report(user["name"], analysis_result, save_to_disk=False)
    with act1:
        st.download_button(
            "📄 Download PDF Report",
            data=pdf_bytes,
            file_name=f"Resume_Analysis_{target_role.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with act2:
        if st.button("✨ Improve Resume", use_container_width=True):
            st.session_state["nav_page"] = "Improve Resume"
            st.rerun()
    with act3:
        if st.button("💼 Find Jobs", use_container_width=True):
            st.session_state["nav_page"] = "Job Recommendations"
            st.rerun()
    with act4:
        if st.button("📉 Detailed Skills Gap", use_container_width=True):
            st.session_state["nav_page"] = "Skills Gap"
            st.rerun()

    st.markdown("---")

    # ---------------- OVERALL SCORE & COMPONENT BREAKDOWN ----------------
    col_gauge, col_bars = st.columns([1, 2])
    with col_gauge:
        st.markdown(
            render_circular_gauge_html(
                overall_score,
                classification,
                f"Target: {analysis_result.get('target_role', target_role)}",
            ),
            unsafe_allow_html=True,
        )
        benchmark = score_data.get("industry_benchmark", 77.0)
        delta = round(overall_score - benchmark, 1)
        st.metric(
            "vs. Industry Benchmark",
            f"{overall_score:.1f} / 100",
            delta=f"{delta:+.1f} pts vs avg ({benchmark})",
        )

    with col_bars:
        st.markdown("<div class='soft-card'><h4>📊 Weighted Component Score Breakdown</h4>", unsafe_allow_html=True)
        for comp in score_data["components"].values():
            c_color = score_color_hex(comp["score"])
            label_col, bar_col = st.columns([2.2, 3])
            with label_col:
                st.markdown(
                    f"**{comp['label']}** ({comp['weight_pct']}%)",
                    help=comp["explanation"],
                )
                st.caption(f"Score: {comp['score']}/100 | Benchmark: {comp['industry_benchmark']}")
            with bar_col:
                st.markdown(
                    f"""
                    <div style="background:#252630; border-radius:999px; height:14px; width:100%; margin-top:8px;">
                        <div style="background:{c_color}; width:{comp['score']}%; height:14px; border-radius:999px;"></div>
                    </div>
                    <div style="font-size:0.8rem; color:#A8ACBA; margin-top:3px;">{html.escape(comp['explanation'])}</div>
                    """,
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- SCORE HISTORY TREND ----------------
    history_rows = [
        r for r in get_resume_analysis_for_user(current["id"]) if (r.get("overall_score") or 0) > 0
    ]
    if len(history_rows) >= 2:
        with st.expander("📈 Score History & Progress Over Time"):
            hist_df = pd.DataFrame(
                [
                    {
                        "Date": str(r["analyzed_at"])[:16],
                        "Score": float(r["overall_score"]),
                        "Role": r.get("target_role") or "N/A",
                    }
                    for r in reversed(history_rows[:10])
                ]
            )
            st.line_chart(hist_df.set_index("Date")["Score"])

    # ---------------- STRENGTHS & WEAKNESSES ----------------
    col_str, col_weak = st.columns(2)
    with col_str:
        st.markdown("### 💪 Key Strengths")
        for s in strengths:
            st.markdown(
                f"""
                <div class="strength-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>✅ {html.escape(str(s.get('title', 'Strength')))}</strong>
                        <span class="chip chip-green">{html.escape(str(s.get('category', 'General')))} · {s.get('confidence', 85)}% conf.</span>
                    </div>
                    <p style="margin:0.35rem 0 0.25rem 0; font-size:0.92rem;">{html.escape(str(s.get('description', '')))}</p>
                    <div style="font-size:0.82rem; opacity:0.85;"><em>Evidence: {html.escape(str(s.get('evidence', '')))}</em></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_weak:
        st.markdown("### ⚠️ Weaknesses & Areas to Improve")
        for w in weaknesses:
            sev = str(w.get("severity") or "moderate").lower()
            card_cls = (
                "weakness-critical"
                if sev == "critical"
                else ("weakness-minor" if sev == "minor" else "weakness-moderate")
            )
            badge_cls = "chip-red" if sev == "critical" else ("chip-amber" if sev == "moderate" else "chip-slate")
            st.markdown(
                f"""
                <div class="{card_cls}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>🔧 {html.escape(str(w.get('title', 'Weakness')))}</strong>
                        <span class="chip {badge_cls}">{sev.upper()} · {w.get('confidence', 85)}% conf.</span>
                    </div>
                    <p style="margin:0.35rem 0 0.25rem 0; font-size:0.92rem;">{html.escape(str(w.get('description', '')))}</p>
                    <div style="font-size:0.82rem; opacity:0.88;">
                        <strong>Location:</strong> {html.escape(str(w.get('location', 'Resume')))} |
                        <em>{html.escape(str(w.get('evidence', '')))}</em>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---------------- SKILLS ANALYSIS & FILTERS ----------------
    st.markdown("### 🧠 Skills Analysis & Gap Summary")
    extracted = skills_gap.get("extracted_skills") or {}
    filter_choice = st.radio(
        "Filter Identified Skills by Category",
        [
            "All Categories",
            "Technical (Languages & Frameworks)",
            "Tools & Platforms",
            "Soft Skills",
            "Domain Knowledge & Certifications",
        ],
        horizontal=True,
        key="analysis_skill_filter",
    )

    sk_col1, sk_col2 = st.columns([1.3, 1])
    with sk_col1:
        st.markdown("<div class='soft-card'><h5>✅ Identified Skills in Your Resume</h5>", unsafe_allow_html=True)
        if filter_choice in ("All Categories", "Technical (Languages & Frameworks)"):
            st.caption("Programming Languages & Frameworks")
            st.markdown(
                render_chips_html(
                    (extracted.get("programming_languages") or []) + (extracted.get("frameworks") or []),
                    variant="blue",
                ),
                unsafe_allow_html=True,
            )
        if filter_choice in ("All Categories", "Tools & Platforms"):
            st.caption("Tools & Platforms")
            st.markdown(render_chips_html(extracted.get("tools") or [], variant="purple"), unsafe_allow_html=True)
        if filter_choice in ("All Categories", "Soft Skills"):
            st.caption("Soft Skills")
            st.markdown(render_chips_html(extracted.get("soft_skills") or [], variant="green"), unsafe_allow_html=True)
        if filter_choice in ("All Categories", "Domain Knowledge & Certifications"):
            st.caption("Domain Knowledge & Certifications")
            st.markdown(
                render_chips_html(
                    (extracted.get("domain_knowledge") or []) + (extracted.get("certifications") or []),
                    variant="slate",
                ),
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with sk_col2:
        st.markdown("<div class='soft-card'><h5>🎯 Missing & Recommended Skills</h5>", unsafe_allow_html=True)
        st.caption("Missing Must-Have Skills")
        st.markdown(
            render_chips_html(skills_gap.get("missing_critical_skills") or [], variant="red", empty_text="No critical gaps detected!"),
            unsafe_allow_html=True,
        )
        st.caption("Recommended Next Skills to Learn")
        st.markdown(
            render_chips_html(skills_gap.get("recommended_skills") or [], variant="amber"),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    usage = get_token_usage_summary()
    if usage["live_calls"] > 0:
        st.caption(
            f"API Usage (Session): {usage['live_calls']} calls | {usage['total_tokens']} tokens | "
            f"Est. cost ${usage['estimated_cost_usd']:.5f}"
        )

    with st.expander("📄 View Analyzed Resume Text"):
        st.text(resume_text)
