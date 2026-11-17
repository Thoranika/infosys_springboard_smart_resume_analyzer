"""Resume Upload UI page with validation, preview, replace/delete, and text extraction."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Optional

import streamlit as st

from backend.auth import get_current_user
from backend.resume_parser import extract_resume_metadata, extract_text_from_file
from utils.database import (
    BASE_DIR,
    delete_all_resumes_for_user,
    get_latest_resume_analysis,
    get_user_by_id,
    log_activity,
    save_resume_analysis,
    update_user,
)
from utils.helpers import format_file_size, inject_custom_css, render_chips_html
from utils.validators import validate_resume_file


def _render_pdf_first_page_preview(file_path: str) -> Optional[bytes]:
    """Attempt to render page 1 of a PDF file as PNG bytes if supported."""
    try:
        import pypdfium2 as pdfium  # type: ignore

        pdf = pdfium.PdfDocument(file_path)
        if len(pdf) == 0:
            return None
        page = pdf[0]
        pil_image = page.render(scale=1.2).to_pil()
        import io

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def upload_resume_page() -> None:
    """Render the Resume Upload, Validation, Preview, and Text Extraction interface."""
    inject_custom_css()

    current = get_current_user()
    if not current:
        st.error("Please log in to upload your resume.")
        return

    user = get_user_by_id(current["id"]) or current
    latest_analysis = get_latest_resume_analysis(current["id"])
    existing_path = user.get("resume_path")
    abs_existing = (
        existing_path
        if existing_path and os.path.isabs(existing_path)
        else (os.path.join(BASE_DIR, existing_path) if existing_path else None)
    )

    st.markdown(
        """
        <div class="hero-banner">
            <h2>📄 Resume Upload & Text Extraction</h2>
            <p>Upload your PDF or DOCX resume (max 5 MB). We validate, extract, and prepare your resume for AI analysis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Current Resume Status Card
    if existing_path or latest_analysis:
        st.markdown("<div class='soft-card'><h4>📌 Current Resume on File</h4>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        file_exists = bool(abs_existing and os.path.exists(abs_existing))
        fname = os.path.basename(abs_existing) if existing_path else "Extracted Resume Text"
        fsize = format_file_size(os.path.getsize(abs_existing)) if file_exists else "Stored in DB"
        fdate = (
            datetime.fromtimestamp(os.path.getmtime(abs_existing)).strftime("%Y-%m-%d %H:%M")
            if file_exists
            else (latest_analysis.get("analyzed_at") or "N/A")
        )
        word_count = len((latest_analysis.get("resume_text") or "").split()) if latest_analysis else 0

        c1.metric("File Name", fname[:24] + ("..." if len(fname) > 24 else ""))
        c2.metric("File Size", fsize)
        c3.metric("Last Updated", str(fdate)[:16])
        c4.metric("Extracted Words", f"{word_count}")

        act1, act2, act3 = st.columns([1.2, 1.2, 1])
        with act1:
            if st.button("🤖 Analyze Current Resume", type="primary", use_container_width=True):
                st.session_state["nav_page"] = "Resume Analysis"
                st.rerun()
        with act2:
            if st.button("🎯 Find Matching Jobs", use_container_width=True):
                st.session_state["nav_page"] = "Job Preferences"
                st.rerun()
        with act3:
            if st.button("🗑️ Delete Resume", use_container_width=True):
                if file_exists and abs_existing:
                    try:
                        os.remove(abs_existing)
                    except OSError:
                        pass
                delete_all_resumes_for_user(current["id"])
                log_activity(current["id"], "Resume Deleted", f"Deleted resume {fname}.")
                st.success("Resume and stored analyses removed.")
                st.rerun()

        if latest_analysis and latest_analysis.get("resume_text"):
            with st.expander("📄 View Extracted Resume Text"):
                st.text_area(
                    "Extracted Content",
                    value=latest_analysis["resume_text"],
                    height=260,
                    disabled=True,
                    key="existing_resume_text_preview",
                )
        st.markdown("</div>", unsafe_allow_html=True)

    # Upload New / Replacement Resume
    st.markdown("### ⬆️ Upload New or Replacement Resume")
    uploaded = st.file_uploader(
        "Choose a PDF or DOCX file (Max 5 MB)",
        type=["pdf", "docx"],
        help="Supported formats: text-based PDF (.pdf) and Microsoft Word (.docx) up to 5 MB.",
    )

    if uploaded is not None:
        file_bytes = uploaded.getvalue()
        is_valid, validation_msg = validate_resume_file(uploaded.name, file_bytes)

        if not is_valid:
            st.error(f"❌ {validation_msg}")
            return

        p1, p2, p3 = st.columns(3)
        p1.info(f"**File:** {uploaded.name}")
        p2.info(f"**Size:** {format_file_size(len(file_bytes))}")
        p3.info(f"**Selected:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        if st.button("📤 Upload & Extract Resume", type="primary", use_container_width=True):
            progress = st.progress(0, text="Validating file...")
            save_dir = os.path.join(BASE_DIR, "data", "resumes")
            os.makedirs(save_dir, exist_ok=True)

            ext = os.path.splitext(uploaded.name)[1].lower()
            unique_filename = f"user_{current['id']}_{int(time.time())}{ext}"
            rel_path = os.path.join("data", "resumes", unique_filename)
            abs_path = os.path.join(BASE_DIR, rel_path)

            try:
                progress.progress(25, text="Saving uploaded file securely...")
                with open(abs_path, "wb") as handle:
                    handle.write(file_bytes)

                progress.progress(55, text="Extracting and cleaning text from resume...")
                with st.spinner("Extracting text across all pages/paragraphs..."):
                    extracted_text = extract_text_from_file(abs_path)

                if len(extracted_text.strip()) < 50:
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                    progress.empty()
                    st.error(
                        "⚠️ Extracted text is too short (< 50 characters). "
                        "If your PDF is scanned/image-only, please upload a searchable PDF or DOCX."
                    )
                    return

                progress.progress(80, text="Saving extracted text to database...")
                metadata = extract_resume_metadata(abs_path, extracted_text)

                update_user(current["id"], resume_path=rel_path)
                initial_payload = {
                    "summary": "Resume uploaded successfully. Run AI Analysis to generate full insights.",
                    "strengths": [],
                    "weaknesses": [],
                    "skills": [],
                    "score": 0,
                    "metadata": metadata,
                }
                save_resume_analysis(
                    user_id=current["id"],
                    resume_text=extracted_text,
                    analysis_json=json.dumps(initial_payload),
                )
                log_activity(
                    current["id"],
                    "Resume Uploaded",
                    f"Uploaded {uploaded.name} ({metadata['word_count']} words extracted).",
                )
                progress.progress(100, text="Complete!")
                st.success(f"✅ Resume uploaded and {metadata['word_count']} words extracted successfully!")

                # Section detection summary + optional PDF page 1 preview
                detected = [k.title() for k, found in metadata["detected_sections"].items() if found]
                st.markdown("**Detected Resume Sections:**")
                st.markdown(render_chips_html(detected, variant="green"), unsafe_allow_html=True)

                if ext == ".pdf":
                    preview_png = _render_pdf_first_page_preview(abs_path)
                    if preview_png:
                        with st.expander("🖼️ Page 1 Visual Preview"):
                            st.image(preview_png, caption=f"{uploaded.name} - Page 1", width=420)

                with st.expander("📄 Preview Extracted Resume Text", expanded=True):
                    st.text_area(
                        "Extracted Resume Content",
                        value=extracted_text,
                        height=300,
                        disabled=True,
                        key="new_resume_text_preview",
                    )

                st.info("👉 Next step: Go to **Resume Analysis** in the sidebar to run full AI scoring and skills gap analysis.")

            except ValueError as exc:
                progress.empty()
                if os.path.exists(abs_path):
                    try:
                        os.remove(abs_path)
                    except OSError:
                        pass
                st.error(f"❌ {exc}")
            except Exception as exc:
                progress.empty()
                if os.path.exists(abs_path):
                    try:
                        os.remove(abs_path)
                    except OSError:
                        pass
                st.error(f"❌ Unexpected error processing resume: {exc}")


def resume_upload_page() -> None:
    """Compatibility alias for upload_resume_page."""
    upload_resume_page()
