"""Streamlit AppTest UI smoke tests across login, registration, and all dashboard pages."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import utils.database as db
from backend.auth import register_user
from backend.job_search import search_jobs_for_user
from backend.resume_analyzer import run_full_resume_analysis


SAMPLE_RESUME = """
Maya Patel
maya.patel@example.com | +1 555-888-1122 | https://linkedin.com/in/mayapatel | https://github.com/mayapatel

SUMMARY
Software Developer with 3+ years of experience building Python, FastAPI, and React applications.

EXPERIENCE
Software Engineer - Acme Cloud (2022 - 2025)
- Built Python FastAPI microservices serving 25,000+ daily users, reducing latency by 30%.
- Automated Docker and GitHub Actions CI/CD pipelines with 90% pytest test coverage.

SKILLS
Python, SQL, JavaScript, FastAPI, React, Docker, Git, AWS, PostgreSQL, Agile, Communication

EDUCATION
B.Tech in Computer Science (2018 - 2022)
"""


class TestStreamlitUI(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self._tmpdir.name, "test_ui.db")
        db.init_db()

        ok, msg = register_user("Maya Patel", "maya@example.com", "Strong#2025", "Strong#2025")
        self.assertTrue(ok, msg)
        user = db.get_user_by_email("maya@example.com")
        self.uid = user["id"]
        db.update_user(self.uid, experience_years=3.0, education_level="Bachelor's", target_role="Software Developer")
        run_full_resume_analysis(self.uid, SAMPLE_RESUME, target_role="Software Developer", use_llm=False)
        search_jobs_for_user(self.uid, allow_network=False)
        db.upsert_job_recommendation(
            self.uid,
            {
                "job_title": "Python Software Engineer",
                "company_name": "LinkedIn Featured Partner",
                "location": "Bengaluru, India",
                "job_description": "Python, FastAPI, Docker, SQL, Git, 2+ years experience.",
                "job_url": "https://www.linkedin.com/jobs/view/3999111222",
                "match_percentage": 91.0,
                "source": "LinkedIn",
                "posted_date": "2026-11-17",
            },
        )

    def tearDown(self) -> None:
        db.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_login_register_and_all_dashboard_views(self) -> None:
        app_path = os.path.join(PROJECT_ROOT, "app.py")

        # 1. Verify initial Login page renders
        at = AppTest.from_file(app_path, default_timeout=20)
        at.run()
        self.assertEqual(len(at.exception), 0, f"Login exception: {at.exception}")

        # 2. Switch to Register page and verify rendering
        at.session_state["page"] = "Register"
        at.run()
        self.assertEqual(len(at.exception), 0, f"Register exception: {at.exception}")

        # 3. Authenticate session and verify every Dashboard module renders without exceptions
        pages_to_verify = [
            "Overview",
            "My Profile",
            "Upload Resume",
            "Resume Analysis",
            "Skills Gap",
            "Improve Resume",
            "Job Preferences",
            "Job Recommendations",
            "Settings",
        ]
        at.session_state["user"] = {
            "id": self.uid,
            "name": "Maya Patel",
            "email": "maya@example.com",
            "target_role": "Software Developer",
        }
        at.session_state["page"] = "Dashboard"

        for nav in pages_to_verify:
            at.session_state["nav_page"] = nav
            at.run()
            self.assertEqual(
                len(at.exception),
                0,
                f"Uncaught exception on dashboard page '{nav}': {at.exception}",
            )
            button_keys = {b.key for b in at.button if b.key}
            self.assertNotIn("top_logout_btn", button_keys)
            self.assertIn("bottom_right_logout_btn", button_keys)

            markdown_blob = "\n".join(m.value for m in at.markdown)
            self.assertIn("#101116", markdown_blob)
            self.assertIn("#252630", markdown_blob)
            self.assertIn("#192F46", markdown_blob)

        # 4. Verify bottom-right logout clears session and returns to Login
        at.button(key="bottom_right_logout_btn").click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.session_state["page"], "Login")
        self.assertNotIn("user", at.session_state)


if __name__ == "__main__":
    unittest.main()
