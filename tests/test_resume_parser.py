"""Resume upload validation and PDF/DOCX text extraction tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

import docx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.resume_parser import (
    clean_resume_text,
    detect_resume_sections,
    extract_resume_metadata,
    extract_text_from_file,
)
from utils.validators import validate_resume_file


class TestResumeParser(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_validate_resume_file_constraints(self) -> None:
        ok, _ = validate_resume_file("resume.txt", b"hello")
        self.assertFalse(ok)

        ok, _ = validate_resume_file("empty.pdf", b"")
        self.assertFalse(ok)

        oversized = b"%PDF-" + (b"0" * (5 * 1024 * 1024 + 10))
        ok, msg = validate_resume_file("big.pdf", oversized)
        self.assertFalse(ok)
        self.assertIn("5 mb", msg.lower())

        ok, _ = validate_resume_file("fake.pdf", b"NOTAPDF12345")
        self.assertFalse(ok)

        ok, _ = validate_resume_file("valid.pdf", b"%PDF-1.4\n1 0 obj")
        self.assertTrue(ok)

    def test_docx_extraction_and_metadata(self) -> None:
        docx_path = os.path.join(self._tmpdir.name, "sample_resume.docx")
        doc = docx.Document()
        doc.add_heading("Alex Rivera", level=1)
        doc.add_paragraph("alex@example.com | linkedin.com/in/alexrivera")
        doc.add_heading("Summary", level=2)
        doc.add_paragraph("Python Backend Engineer with 3+ years of experience building APIs.")
        doc.add_heading("Skills", level=2)
        doc.add_paragraph("Python, FastAPI, SQL, Docker, Git")
        doc.add_heading("Education", level=2)
        doc.add_paragraph("B.Tech in Computer Science")
        doc.save(docx_path)

        text = extract_text_from_file(docx_path)
        self.assertIn("Alex Rivera", text)
        self.assertIn("FastAPI", text)

        meta = extract_resume_metadata(docx_path, text)
        self.assertGreater(meta["word_count"], 15)
        self.assertTrue(meta["detected_sections"]["skills"])
        self.assertTrue(meta["detected_sections"]["education"])

    def test_existing_sample_pdf_extraction(self) -> None:
        sample_pdf = os.path.join(PROJECT_ROOT, "data", "resumes", "user_4.pdf")
        if os.path.exists(sample_pdf):
            text = extract_text_from_file(sample_pdf)
            self.assertGreater(len(text.strip()), 50)
            sections = detect_resume_sections(text)
            self.assertIsInstance(sections, dict)

    def test_corrupted_file_and_cleaning(self) -> None:
        corrupt_pdf = os.path.join(self._tmpdir.name, "corrupt.pdf")
        with open(corrupt_pdf, "wb") as f:
            f.write(b"%PDF-1.4 corrupted garbage bytes \x00\x01\x02")
        with self.assertRaises(ValueError):
            extract_text_from_file(corrupt_pdf)

        cleaned = clean_resume_text("Line   one\x00\r\n\r\n\r\nLine\t\ttwo")
        self.assertEqual(cleaned, "Line one\n\nLine two")


if __name__ == "__main__":
    unittest.main()
