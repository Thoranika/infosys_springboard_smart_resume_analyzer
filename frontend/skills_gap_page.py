import streamlit as st
from backend.auth import get_current_user
from backend.skills_gap_analyzer import run_skills_gap_analysis

def skills_gap_page():
    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    st.title("🧠 Skills Gap Analyzer")

    role = st.text_input("Enter target job role:", "Software Developer")

    if st.button("Analyze Skills Gap 🚀"):
        with st.spinner("Analyzing skills..."):
            result = run_skills_gap_analysis(user["id"], role)

        st.success("Analysis Complete ✔")

        st.subheader("Resume Skills")
        st.json(result.get("resume_skills", {}))

        st.subheader("Industry Requirements")
        st.json(result.get("industry_required_skills", {}))

        st.subheader("Missing Skills")
        st.json(result.get("missing_skills", {}))

        st.subheader("Skill Recommendations")
        st.json(result.get("skill_recommendations", []))

        st.subheader("Summary")
        st.write(result.get("summary", ""))
