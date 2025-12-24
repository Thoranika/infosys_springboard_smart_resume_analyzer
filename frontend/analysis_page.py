import streamlit as st
import json
from backend.auth import get_current_user
from utils.database import get_latest_resume_analysis
from backend.llm_analyzer import (
    analyze_strengths,
    analyze_weaknesses,
    analyze_skills_gap,
    analyze_score
)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import matplotlib.pyplot as plt
import os
import io


def analysis_page():
    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    st.title("📊 Resume Analysis Dashboard")

    resume_data = get_latest_resume_analysis(user["id"])
    if not resume_data:
        st.warning("Upload resume first.")
        return

    resume_text = resume_data["resume_text"]

    if st.button("Run Full Analysis 🚀"):
        with st.spinner("Analyzing... this may take 10-20 seconds..."):

            score = analyze_score(resume_text)
            strengths = analyze_strengths(resume_text)
            weaknesses = analyze_weaknesses(resume_text)
            skills = analyze_skills_gap(resume_text, "Software Developer")

        st.session_state["analysis_results"] = {
            "score": score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "skills": skills,
        }

    if "analysis_results" not in st.session_state:
        st.info("Click 'Run Full Analysis' to continue.")
        return

    results = st.session_state["analysis_results"]


    # =======================================================
    #  OVERALL SCORE VISUAL
    # =======================================================
    st.subheader("🏆 Resume Score")

    score_value = results["score"]["score"]
    st.metric("Overall Score", f"{score_value}/100")

    fig, ax = plt.subplots(figsize=(3, 3))
    ax.pie([score_value, 100 - score_value], labels=["Score", ""], autopct="%1.0f%%")
    st.pyplot(fig)

    if score_value < 60:
        st.error("Needs Improvement")
    elif score_value < 75:
        st.warning("Average")
    elif score_value < 90:
        st.success("Good")
    else:
        st.balloons()
        st.success("Excellent 🔥")


    # =======================================================
    #  STRENGTHS
    # =======================================================
    st.subheader("💪 Strengths")
    for s in results["strengths"]["strengths"]:
        with st.container(border=True):
            st.write(f"**👉 {s['point']}**")
            st.write(f"📌 {s['reason']}")


    # =======================================================
    #  WEAKNESSES
    # =======================================================
    st.subheader("⚠ Weaknesses")
    for w in results["weaknesses"]["weaknesses"]:
        with st.container(border=True):
            st.write(f"**❗ {w['issue']}**")
            st.write(f"🛠 Fix: {w['fix']}")


    # =======================================================
    #  SKILLS GAP
    # =======================================================
    st.subheader("🧠 Skills Gap Analysis")

    st.write("### Resume Skills")
    st.json(results["skills"]["resume_skills"])

    st.write("### Industry Required Skills")
    st.json(results["skills"]["industry_required_skills"])

    st.write("### Missing Skills")
    st.json(results["skills"]["missing_skills"])

    st.write("### Recommended Skills to Learn")
    st.json(results["skills"]["skill_recommendations"])


    # =======================================================
    #  PDF REPORT
    # =======================================================
    st.subheader("📄 Download Full Report")

    if st.button("Generate PDF Report 📥"):

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.setFont("Helvetica", 14)

        pdf.drawString(50, 800, "Resume Analysis Report")
        pdf.setFont("Helvetica", 10)

        pdf.drawString(50, 780, f"Score: {score_value}")

        y = 760
        pdf.drawString(50, y, "Strengths:")
        y -= 20

        for s in results["strengths"]["strengths"]:
            pdf.drawString(60, y, f"- {s['point']}")
            y -= 15

        y -= 20
        pdf.drawString(50, y, "Weaknesses:")
        y -= 20

        for w in results["weaknesses"]["weaknesses"]:
            pdf.drawString(60, y, f"- {w['issue']}")
            y -= 15

        pdf.save()
        buffer.seek(0)

        st.download_button(
            "Download PDF",
            data=buffer,
            file_name="resume_analysis.pdf",
            mime="application/pdf"
        )


    # =======================================================
    #  ACTION BUTTONS
    # =======================================================
    st.subheader("✨ Next Steps")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.button("Re-Analyze 🔁")

    with col2:
        st.button("Improve Resume ✍️")

    with col3:
        st.button("Find Jobs 💼")
