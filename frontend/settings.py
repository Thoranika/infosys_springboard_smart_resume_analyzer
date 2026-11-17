"""Settings, LLM Connection Tester, Help/FAQ, Onboarding Tutorial & Feedback UI."""

from __future__ import annotations

import streamlit as st

from backend.auth import get_current_user
from backend.llm_analyzer import get_llm_config, get_token_usage_summary, test_api_connection
from utils.database import save_user_feedback
from utils.helpers import inject_custom_css


def settings_page() -> None:
    """Render application settings, LLM connectivity diagnostics, help/FAQ, and feedback form."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Please log in to access settings.")
        return

    st.markdown(
        """
        <div class="hero-banner">
            <h2>⚙️ Settings, Help & Feedback</h2>
            <p>Inspect AI provider status, clear cached results, review tutorials, and submit feedback.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_cfg, tab_help, tab_fb = st.tabs(["🤖 AI & System Settings", "❓ Help, Tutorial & FAQ", "💬 Feedback & Support"])

    with tab_cfg:
        cfg = get_llm_config()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='soft-card'><h4>LLM Provider Configuration</h4>", unsafe_allow_html=True)
            st.write(f"**Configured Provider:** `{cfg['preferred_provider']}`")
            st.write(f"**Active Runtime Mode:** `{'Live AI (' + cfg['active_provider'] + ')' if cfg['is_live'] else 'Evidence-Based Demo Mode'}`")
            st.write(f"**Model:** `{cfg['model']}`")
            st.write(f"**Gemini Key Detected:** {'✅ Yes' if cfg['has_gemini_key'] else '❌ Not configured'}")
            st.write(f"**OpenAI Key Detected:** {'✅ Yes' if cfg['has_openai_key'] else '❌ Not configured'}")
            if st.button("🔌 Test LLM API Connection", type="primary"):
                with st.spinner("Testing connectivity..."):
                    ok, prov, msg = test_api_connection()
                if ok:
                    st.success(f"[{prov}] {msg}")
                else:
                    st.warning(f"[{prov}] {msg}")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            usage = get_token_usage_summary()
            st.markdown("<div class='soft-card'><h4>Session API Usage & Cache</h4>", unsafe_allow_html=True)
            st.write(f"**Total LLM Calls:** {usage['total_calls']}")
            st.write(f"**Live API Calls:** {usage['live_calls']}")
            st.write(f"**Total Tokens Used:** {usage['total_tokens']}")
            st.write(f"**Estimated Session Cost:** ${usage['estimated_cost_usd']:.6f}")
            if st.button("🧹 Clear Session Analysis Cache"):
                for k in ["current_analysis", "current_skills_gap", "current_improvements", "last_search_results"]:
                    st.session_state.pop(k, None)
                st.success("Session cache cleared.")
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_help:
        st.markdown("### 🧭 Step-by-Step Quick Start Tutorial")
        st.markdown(
            """
            1. **Upload Resume:** Go to **Upload Resume** and upload a text-based `.pdf` or `.docx` (up to 5 MB).
            2. **Run AI Analysis:** Open **Resume Analysis**, select your target role, and click **Analyze Resume** to get weighted scores, strengths, weaknesses, and a downloadable PDF report.
            3. **Bridge Skill Gaps:** Visit **Skills Gap** to inspect your 6-category skill inventory and learning links.
            4. **Improve Your Resume:** Open **Improve Resume** for before/after bullet rewrites and track fixes you have applied.
            5. **Discover Matching Jobs:** Configure your criteria in **Job Preferences**, run **Find Jobs Now**, and filter, compare, and track applications in **Job Recommendations**.
            """
        )

        st.markdown("### ❓ Frequently Asked Questions")
        with st.expander("Why am I seeing Evidence-Based Demo Mode?"):
            st.write(
                "When no valid `GEMINI_API_KEY` or `OPENAI_API_KEY` is configured in `.env`, the app runs deterministic "
                "evidence-based scoring, skill extraction, and job matching directly on your uploaded resume text so you "
                "still receive accurate, reproducible feedback without API failures."
            )
        with st.expander("How is the Resume Score calculated?"):
            st.write(
                "Your overall score uses five weighted criteria: Completeness (25%), Content Quality (30%), "
                "Formatting (15%), Keyword Relevance (20%), and Experience Depth (10%)."
            )
        with st.expander("How is the Job Match Percentage calculated?"):
            st.write(
                "Job matching weights Skills Match (50%), Experience Match (25%), Education Match (15%), "
                "and Responsibilities Match (10%). Jobs below your threshold (default 60%) are filtered out."
            )
        with st.expander("Why does a scanned PDF fail extraction?"):
            st.write(
                "Scanned PDFs contain images rather than selectable text. Upload a text-based PDF exported from Word/Google Docs/LaTeX or a `.docx` file."
            )

    with tab_fb:
        st.markdown("### 💬 Submit Feedback or Contact Support")
        with st.form("user_feedback_form", clear_on_submit=True):
            category = st.selectbox("Feedback Category", ["Feature Request", "Bug Report", "AI Accuracy", "General Praise", "Support Request"])
            rating = st.slider("Overall Experience Rating", min_value=1, max_value=5, value=5)
            comments = st.text_area("Comments / Support Details", placeholder="Share your experience or issue details...", height=120)
            submitted = st.form_submit_button("Submit Feedback", type="primary")
            if submitted:
                if not comments.strip():
                    st.error("Please enter your comments before submitting.")
                else:
                    save_user_feedback(current["id"], category, rating, comments)
                    st.success("Thank you! Your feedback has been recorded.")
        st.caption("Need direct assistance? Contact support at `support@aicareerassistant.local`.")
