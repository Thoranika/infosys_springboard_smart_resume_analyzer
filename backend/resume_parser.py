"""Resume text extraction, cleaning, metadata inspection, and error handling."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import docx
import pdfplumber
from PyPDF2 import PdfReader

from utils.database import save_resume_analysis
from utils.logger import get_logger

logger = get_logger("resume_parser")

SECTION_PATTERNS = {
    "contact": re.compile(r"(@|linkedin\.com|github\.com|\+?\d[\d\-\s\(\)]{7,}\d)", re.IGNORECASE),
    "summary": re.compile(r"\b(summary|objective|profile|about me)\b", re.IGNORECASE),
    "experience": re.compile(r"\b(experience|employment|work history|internship|career)\b", re.IGNORECASE),
    "education": re.compile(r"\b(education|university|college|bachelor|master|b\.?tech|m\.?tech|b\.?s\.?|m\.?s\.?|degree|gpa)\b", re.IGNORECASE),
    "skills": re.compile(r"\b(skills|technologies|technical stack|competencies|tools)\b", re.IGNORECASE),
    "projects": re.compile(r"\b(projects|portfolio|publications)\b", re.IGNORECASE),
    "certifications": re.compile(r"\b(certifications?|licenses?|awards?|achievements?)\b", re.IGNORECASE),
}


def clean_resume_text(raw_text: str) -> str:
    """Normalize whitespace and non-printable characters while preserving sections/lines."""
    if not raw_text:
        return ""
    # Replace Windows/old-Mac newlines and strip control chars except newline/tab
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    # Collapse horizontal spaces per line while preserving paragraph structure
    cleaned_lines: List[str] = []
    blank_streak = 0
    for line in text.split("\n"):
        normalized = re.sub(r"[ \t]+", " ", line).strip()
        if not normalized:
            blank_streak += 1
            if blank_streak <= 1 and cleaned_lines:
                cleaned_lines.append("")
        else:
            blank_streak = 0
            cleaned_lines.append(normalized)
    return "\n".join(cleaned_lines).strip()


def _attempt_ocr_pdf(path: str) -> str:
    """Attempt optional OCR for scanned/image-based PDFs when OCR tools are installed."""
    try:
        import pytesseract  # type: ignore
        from pdf2image import convert_from_path  # type: ignore
    except ImportError:
        logger.warning(
            "Image-based PDF detected at %s, but optional OCR packages (pytesseract/pdf2image) are not installed.",
            path,
        )
        return ""

    try:
        images = convert_from_path(path)
        ocr_pages = [pytesseract.image_to_string(img) for img in images]
        return "\n".join(ocr_pages).strip()
    except Exception as exc:
        logger.warning("OCR fallback failed for %s: %s", path, exc)
        return ""


def extract_text_from_pdf(path: str) -> str:
    """Extract text from all pages of a PDF file using pdfplumber with PyPDF2 fallback."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Resume file not found: {path}")

    # Check encryption / corruption upfront with PyPDF2
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                decrypt_result = reader.decrypt("")
                if decrypt_result == 0:
                    raise ValueError("PDF file is password-protected and cannot be read.")
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("PDF file is password-protected and cannot be decrypted.") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Corrupted or unreadable PDF file: {exc}") from exc

    text_blocks: List[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_blocks.append(page_text)
    except Exception as exc:
        logger.warning("pdfplumber extraction failed on %s (%s); trying PyPDF2 fallback", path, exc)

    combined = "\n".join(text_blocks).strip()

    # Fallback to PyPDF2 text extraction if pdfplumber yielded very little
    if len(combined) < 40:
        try:
            reader = PdfReader(path)
            pypdf_blocks = []
            for page in reader.pages:
                pt = page.extract_text() or ""
                if pt.strip():
                    pypdf_blocks.append(pt)
            pypdf_combined = "\n".join(pypdf_blocks).strip()
            if len(pypdf_combined) > len(combined):
                combined = pypdf_combined
        except Exception as exc:
            logger.error("PyPDF2 fallback also failed for %s: %s", path, exc)

    # Attempt OCR if PDF appears to be scanned/image-only
    if len(combined) < 40:
        ocr_text = _attempt_ocr_pdf(path)
        if ocr_text:
            combined = ocr_text

    return clean_resume_text(combined)


def extract_text_from_docx(path: str) -> str:
    """Extract paragraphs and table rows from a DOCX resume preserving structure."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Resume file not found: {path}")

    try:
        document = docx.Document(path)
    except Exception as exc:
        raise ValueError(f"Corrupted or unreadable DOCX file: {exc}") from exc

    blocks: List[str] = []
    for para in document.paragraphs:
        text = para.text.strip()
        if text:
            blocks.append(text)

    for table in document.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                # Deduplicate merged cells while preserving order
                unique_cells = list(dict.fromkeys(row_cells))
                blocks.append(" | ".join(unique_cells))

    return clean_resume_text("\n".join(blocks))


def detect_resume_sections(text: str) -> Dict[str, bool]:
    """Identify standard resume sections present in extracted text."""
    return {
        section: bool(pattern.search(text or ""))
        for section, pattern in SECTION_PATTERNS.items()
    }


def extract_resume_metadata(path: str, extracted_text: str) -> Dict[str, Any]:
    """Return file diagnostics, counts, and detected sections for an extracted resume."""
    ext = os.path.splitext(path)[1].lower()
    size_bytes = os.path.getsize(path) if os.path.exists(path) else 0
    page_count = 0
    is_image_pdf = False

    if ext == ".pdf" and os.path.exists(path):
        try:
            reader = PdfReader(path)
            page_count = len(reader.pages)
            if page_count > 0 and len((extracted_text or "").strip()) < 50:
                is_image_pdf = True
        except Exception:
            pass
    elif ext == ".docx" and os.path.exists(path):
        try:
            d = docx.Document(path)
            page_count = max(1, len(d.paragraphs) // 30 + 1)
        except Exception:
            page_count = 1

    words = re.findall(r"\b\w+\b", extracted_text or "")
    return {
        "file_name": os.path.basename(path),
        "extension": ext,
        "size_bytes": size_bytes,
        "page_count": page_count,
        "word_count": len(words),
        "char_count": len(extracted_text or ""),
        "is_likely_scanned_pdf": is_image_pdf,
        "detected_sections": detect_resume_sections(extracted_text),
    }


def extract_text_from_file(path: str, user_id: Optional[int] = None) -> str:
    """Unified extractor supporting PDF and DOCX with validation, cleaning, logging, and optional DB persistence."""
    ext = os.path.splitext(path)[1].lower()
    logger.info("Starting resume text extraction path=%s ext=%s user_id=%s", path, ext, user_id)

    if ext == ".pdf":
        text = extract_text_from_pdf(path)
    elif ext == ".docx":
        text = extract_text_from_docx(path)
    else:
        logger.error("Unsupported resume extension=%s for path=%s", ext, path)
        raise ValueError("Unsupported resume format. Only PDF and DOCX are supported.")

    if not text or not text.strip():
        logger.warning("Empty extracted text for path=%s", path)
        if ext == ".pdf":
            raise ValueError(
                "No extractable text found in PDF. This appears to be an image-based/scanned PDF "
                "and OCR dependencies (Tesseract/Poppler) are not available in this environment. "
                "Please upload a text-based PDF or DOCX file."
            )
        raise ValueError("The uploaded DOCX document contains no readable text.")

    logger.info(
        "Extraction succeeded path=%s chars=%d words=%d",
        path,
        len(text),
        len(text.split()),
    )

    if user_id is not None:
        initial_payload = {
            "summary": "Resume extracted successfully. Run AI Analysis to generate full insights.",
            "strengths": [],
            "weaknesses": [],
            "skills": [],
            "score": 0,
        }
        save_resume_analysis(
            user_id=user_id,
            resume_text=text,
            analysis_json=json.dumps(initial_payload),
        )

    return text
