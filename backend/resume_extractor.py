"""Compatibility wrapper delegating resume extraction to backend.resume_parser."""

from backend.resume_parser import (
    clean_resume_text,
    detect_resume_sections,
    extract_resume_metadata,
    extract_text_from_docx,
    extract_text_from_file,
    extract_text_from_pdf,
)

__all__ = [
    "clean_resume_text",
    "detect_resume_sections",
    "extract_resume_metadata",
    "extract_text_from_docx",
    "extract_text_from_file",
    "extract_text_from_pdf",
]
