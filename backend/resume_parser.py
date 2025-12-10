# backend/resume_parser.py

import os
import logging
import re
from typing import Optional, Tuple

from PyPDF2 import PdfReader
from docx import Document

# allow importing from utils
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.database import create_resume_analysis  # assumes this exists in your database.py


# ----------------- LOGGING SETUP -----------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    # simple console logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


# ----------------- TEXT CLEANING -----------------

def clean_text(text: str) -> str:
    """
    Clean extracted text:
    - Convert Windows line endings
    - Remove extra spaces and blank lines
    """
    if not text:
        return ""

    # Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove very long sequences of whitespace
    text = re.sub(r"[ \t]+", " ", text)

    # Remove extra blank lines
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]  # remove empty lines
    return "\n".join(lines).strip()


# ----------------- PDF EXTRACTION -----------------

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from all pages of a PDF.
    NOTE: This works for text-based PDFs.
    For purely image-based PDFs (scanned documents), OCR would be needed.
    """
    logger.info(f"Starting PDF extraction: {file_path}")

    try:
        reader = PdfReader(file_path)
    except Exception as e:
        logger.error(f"Could not open PDF file: {e}")
        raise ValueError(f"Could not open PDF file: {e}")

    all_text = []

    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            all_text.append(page_text)
        except Exception as e:
            logger.warning(f"Error extracting text from page {page_num}: {e}")

    text = "\n".join(all_text)
    text = clean_text(text)

    if not text:
        logger.warning(
            "PDF extraction returned empty text. "
            "This may be an image-based (scanned) PDF. OCR is not implemented."
        )

    logger.info("PDF extraction completed.")
    return text


# ----------------- DOCX EXTRACTION -----------------

def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from a DOCX file using python-docx.
    Each paragraph becomes a line. Basic formatting is lost,
    but sections/line breaks are preserved.
    """
    logger.info(f"Starting DOCX extraction: {file_path}")

    try:
        doc = Document(file_path)
    except Exception as e:
        logger.error(f"Could not open DOCX file: {e}")
        raise ValueError(f"Could not open DOCX file: {e}")

    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    text = "\n".join(paragraphs)
    text = clean_text(text)

    logger.info("DOCX extraction completed.")
    return text


# ----------------- UNIFIED EXTRACTION -----------------

def extract_text_from_file(file_path: str) -> str:
    """
    Detect the file extension and call the correct extractor.
    Supported: .pdf, .docx
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF or DOCX.")


# ----------------- EXTRACT + STORE IN DB -----------

def extract_and_store_resume(
    user_id: int,
    file_path: str,
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    High-level function:
    - extract text from resume file
    - clean text
    - store in resume_analysis table linked to user_id
    Returns: (success, message, analysis_id)
    """
    logger.info(f"Starting resume extraction for user_id={user_id}")

    try:
        text = extract_text_from_file(file_path)
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return False, f"Text extraction failed: {e}", None

    if not text:
        msg = (
            "No readable text could be extracted from the resume. "
            "If this is a scanned PDF, OCR support would be needed."
        )
        logger.warning(msg)
        return False, msg, None

    # Store in database (minimal info, only text & timestamp)
    try:
        analysis_id = create_resume_analysis(
            user_id=user_id,
            resume_text=text,
            analysis_scores=None,
            strengths=None,
            weaknesses=None,
            identified_skills=None,
            recommended_skills=None,
        )
        logger.info(
            f"Resume text stored in database. user_id={user_id}, analysis_id={analysis_id}"
        )
        return True, "Resume text extracted and stored successfully.", analysis_id
    except Exception as e:
        logger.error(f"Could not store extracted text in database: {e}")
        return False, f"Could not store extracted text in database: {e}", None
