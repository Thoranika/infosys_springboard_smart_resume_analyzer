import streamlit as st
from backend.auth import get_current_user
from utils.database import save_resume_analysis, update_user
from backend.resume_extractor import extract_text_from_file
import json
import os


def resume_upload_page():
    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    st.title("📄 Upload Resume")
    st.caption("Upload PDF or DOCX resume")

    uploaded = st.file_uploader("Choose resume file", type=["pdf", "docx"])

    if uploaded:
        # -----------------------------
        # SAVE FILE
        # -----------------------------
        save_dir = "data/resumes"
        os.makedirs(save_dir, exist_ok=True)

        file_ext = uploaded.name.split(".")[-1]
        file_path = os.path.join(save_dir, f"user_{user['id']}.{file_ext}")

        with open(file_path, "wb") as f:
            f.write(uploaded.read())

        update_user(user["id"], file_path)
        st.success("✅ Resume uploaded successfully")

        # -----------------------------
        # EXTRACT TEXT
        # -----------------------------
        with st.spinner("Extracting resume text..."):
            text = extract_text_from_file(file_path)

        if not text or len(text.strip()) < 100:
            st.error("⚠️ Could not extract enough text from resume.")
            st.info("If this is a scanned PDF, OCR was attempted.")
            return

        st.success("✅ Resume text extracted successfully")

        # -----------------------------
        # SHOW EXTRACTED TEXT (NEW)
        # -----------------------------
        with st.expander("📄 Show Extracted Resume Text"):
            st.text_area(
                label="Extracted Resume Content",
                value=text,
                height=400
            )

        # -----------------------------
        # SAVE INITIAL ANALYSIS
        # -----------------------------
        analysis = {
            "summary": "Resume uploaded successfully. Run analysis from dashboard.",
            "strengths": [],
            "weaknesses": [],
            "skills": [],
            "score": 0
        }

        save_resume_analysis(
            user_id=user["id"],
            resume_text=text,
            analysis_json=json.dumps(analysis)
        )

        st.success("📦 Resume data saved")
        st.info("👉 Go to **Full Analysis / Skills Gap** to run AI analysis")
