import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import time
from io import BytesIO
from datetime import datetime

import streamlit as st
from PyPDF2 import PdfReader
from docx import Document

from utils.database import update_user, get_user_by_id
from backend.auth import get_current_user, is_user_logged_in
from backend.resume_parser import extract_and_store_resume

# ------------ PATHS FOR STORING RESUMES -----------------

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESUME_DIR = os.path.join(DATA_DIR, "resumes")
os.makedirs(RESUME_DIR, exist_ok=True)  # create data/resumes if not present


# ------------ HELPER: VALIDATE & SAVE FILE ---------------

MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_and_save_resume(uploaded_file, user_id: int):
    """
    Validate uploaded file and save to disk.
    Returns (success: bool, message: str, saved_path: str | None)
    """
    if uploaded_file is None:
        return False, "No file uploaded.", None

    # size check
    if uploaded_file.size > MAX_SIZE_BYTES:
        return (
            False,
            "File is too large. Maximum allowed size is 5 MB.",
            None,
        )

    # extension check
    filename = uploaded_file.name
    name, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in [".pdf", ".docx"]:
        return False, "Only PDF and DOCX files are allowed.", None

    # read file bytes once
    file_bytes = uploaded_file.read()

    # corruption check: try to open with correct library
    try:
        if ext == ".pdf":
            PdfReader(BytesIO(file_bytes))  # will raise if corrupted
        else:  # .docx
            Document(BytesIO(file_bytes))
    except Exception as e:
        return False, f"File appears to be corrupted or unreadable: {e}", None

    # build unique file name: userId_timestamp.ext
    timestamp = int(time.time())
    unique_name = f"user_{user_id}_{timestamp}{ext}"
    save_path = os.path.join(RESUME_DIR, unique_name)

    # save file
    try:
        with open(save_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        return False, f"Error while saving file: {e}", None

    return True, "Resume uploaded successfully.", save_path


# ------------ MAIN PAGE FUNCTION -------------------------


def resume_upload_page():
    st.set_page_config(
        page_title="Resume Upload",
        page_icon="📄",
        layout="centered",
    )

    # ---------- HEADER + LOGIN CHECK ----------
    st.title("📄 Upload your Resume")

    if is_user_logged_in():
        user = get_current_user()
        user_id = user["id"]
        st.caption(f"Logged in as **{user['name']}** ({user['email']})")
    else:
        # For now, if not logged in, we fall back to demo user (ID=1)
        # Later, when login page is ready, this block will force login.
        st.warning(
            "You are not logged in. For testing, the resume will be linked to demo user with ID = 1."
        )
        user_id = 1
        user = get_user_by_id(user_id)

    st.markdown("---")

    # ---------- SHOW EXISTING RESUME (IF ANY) ----------
    current_resume_path = None
    if user and user.get("resume_path"):
        current_resume_path = user["resume_path"]
        st.subheader("Current Resume")
        st.write(f"**File:** {os.path.basename(current_resume_path)}")
        if os.path.exists(current_resume_path):
            size_kb = os.path.getsize(current_resume_path) / 1024
            st.write(f"**Size:** {size_kb:.1f} KB")
        st.write("You can upload a new resume to replace this one.")

        if st.button("Delete Existing Resume"):
            try:
                if os.path.exists(current_resume_path):
                    os.remove(current_resume_path)
                update_user(user_id, resume_path=None)
                st.success("Existing resume deleted successfully.")
            except Exception as e:
                st.error(f"Could not delete resume: {e}")

            st.stop()  # stop the script so UI refreshes cleanly

        st.markdown("---")

    # ---------- FILE UPLOADER ----------
    st.subheader("Upload a new Resume")

    uploaded_file = st.file_uploader(
        "Choose a PDF or DOCX file (max 5 MB)",
        type=["pdf", "docx"],
    )

    if uploaded_file is not None:
        # show quick preview info
        size_kb = uploaded_file.size / 1024
        st.write(f"**Selected file:** {uploaded_file.name}")
        st.write(f"**Size:** {size_kb:.1f} KB")
        st.write(f"**Upload time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Optional: for PDFs, we could show first page text instead of image
        # to keep it simple.

    # ---------- UPLOAD BUTTON ----------
    if st.button("Upload Resume"):
        if uploaded_file is None:
            st.error("Please select a file first.")
        else:
            with st.spinner("Uploading and validating your resume..."):
                # IMPORTANT: reset pointer before reading again
                uploaded_file.seek(0)
                success, message, saved_path = validate_and_save_resume(
                    uploaded_file, user_id
                )

            if success:
                try:
                    update_user(user_id, resume_path=saved_path)
                    st.success(message)
                    st.info(
                        f"Saved as: `{os.path.basename(saved_path)}` in `data/resumes/`."
                    )

                    # ---- NEW: Extract text and store analysis ----
                    with st.spinner("Extracting text from your resume..."):
                        ok, msg, analysis_id = extract_and_store_resume(
                            user_id=user_id,
                            file_path=saved_path,
                        )

                    if ok:
                        st.success(msg)
                        st.caption(f"Analysis record ID: {analysis_id}")
                    else:
                        st.warning(msg)

                except Exception as e:
                    st.error(f"Upload succeeded but updating database failed: {e}")

            else:
                st.error(message)

if __name__ == "__main__":
    resume_upload_page()
