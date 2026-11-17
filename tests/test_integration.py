"""End-to-end integration test covering Milestones 1, 2, and 3."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

import docx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import utils.database as db
from backend.auth import login_user, logout_user, register_user, update_user_profile
from backend.improvement_suggestions import (
    generate_improvement_suggestions,
    update_improvement_item_status,
)
from backend.job_filter import filter_jobs
from backend.job_recommendations import (
    rank_job_recommendations,
    update_job_application_status,
)
from backend.job_search import search_jobs_for_user
from backend.resume_analyzer import run_full_resume_analysis
from backend.resume_parser import extract_text_from_file
from utils.pdf_generator import generate_analysis_pdf_report


class TestEndToEndWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self._tmpdir.name, "test_e2e.db")
        db.init_db()
        logout_user()

    def tearDown(self) -> None:
        logout_user()
        db.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_complete_user_journey(self) -> None:
        # 1. Registration & Login
        ok_reg, _ = register_user("Samir Verma", "samir@example.com", "Career!2025", "Career!2025")
        self.assertTrue(ok_reg)
        ok_login, _ = login_user("samir@example.com", "Career!2025")
        self.assertTrue(ok_login)
        user = db.get_user_by_email("samir@example.com")
        uid = user["id"]

        # 2. Profile Update
        ok_prof, _ = update_user_profile(uid, target_role="Software Developer", experience_years=2.0, education_level="Bachelor's")
        self.assertTrue(ok_prof)

        # 3. Resume Creation, Extraction & DB Save
        resume_file = os.path.join(self._tmpdir.name, "samir_resume.docx")
        doc = docx.Document()
        doc.add_paragraph("Samir Verma | samir@example.com | +1 555-321-7890 | github.com/samir")
        doc.add_paragraph("Summary: Python Backend Developer with 2+ years building REST APIs and SQL systems.")
        doc.add_paragraph("Experience: Engineered FastAPI services serving 10,000+ users, cutting response time by 40%.")
        doc.add_paragraph("Skills: Python, SQL, FastAPI, Docker, Git, Unit Testing, REST API, Agile")
        doc.add_paragraph("Education: B.Tech in Computer Science")
        doc.save(resume_file)

        extracted_text = extract_text_from_file(resume_file, user_id=uid)
        self.assertIn("FastAPI", extracted_text)
        db.update_user(uid, resume_path=resume_file)

        # 4. Full AI Resume Analysis + PDF Report
        analysis = run_full_resume_analysis(uid, extracted_text, target_role="Software Developer", use_llm=False)
        self.assertGreater(analysis["overall_score"], 60.0)
        self.assertLessEqual(analysis["overall_score"], 100.0)
        pdf_bytes = generate_analysis_pdf_report("Samir Verma", analysis, save_to_disk=False)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

        # 5. Improvement Plan & Interactive Persistence
        plan = generate_improvement_suggestions(
            extracted_text,
            weaknesses=analysis["weaknesses"],
            skills_gap=analysis["skills_gap"],
            score_data=analysis["score_data"],
            user_id=uid,
            analysis_id=analysis["analysis_id"],
            use_llm=False,
        )
        item_id = plan["quick_wins"][0]["id"]
        status_map = update_improvement_item_status(uid, item_id, "Applied")
        self.assertEqual(status_map[item_id], "Applied")

        # 6. Job Preferences, Job Search, Filtering, Ranking & Application Tracking
        prefs = db.get_job_preferences(uid)
        prefs["desired_title"] = "Software Developer"
        prefs["min_match_threshold"] = 60.0
        db.save_job_preferences(uid, prefs)

        search_res = search_jobs_for_user(uid, preferences=prefs, allow_network=False)
        self.assertGreaterEqual(search_res["total_found"], 5)

        stored_jobs = db.get_job_recommendations_for_user(uid)
        filtered = filter_jobs(stored_jobs, {"min_match_threshold": 60.0})
        self.assertGreaterEqual(len(filtered), 1)

        ranked = rank_job_recommendations(filtered, prefs)["ranked_jobs"]
        top_job = ranked[0]
        update_job_application_status(uid, top_job["id"], "Saved", "Top match")
        update_job_application_status(uid, top_job["id"], "Applied", "Submitted today")

        # 7. Dashboard Stats & Logout/Login Persistence
        logout_user()
        ok_relogin, _ = login_user("samir@example.com", "Career!2025")
        self.assertTrue(ok_relogin)
        stats = db.get_dashboard_stats(uid)
        self.assertTrue(stats["has_resume"])
        self.assertIsNotNone(stats["last_score"])
        self.assertGreaterEqual(stats["total_jobs"], 5)
        self.assertEqual(stats["applied_jobs_count"], 1)


if __name__ == "__main__":
    unittest.main()
