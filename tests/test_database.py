"""Database CRUD, schema migration, and persistence tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import utils.database as db
from utils.security import compute_content_hash


class TestDatabaseModule(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self._tmpdir.name, "test_app.db")
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_user_crud_and_unique_email(self) -> None:
        uid = db.create_user("Alice Johnson", "alice@example.com", "hashed_pw_123")
        self.assertIsInstance(uid, int)

        fetched = db.get_user_by_email("ALICE@example.com")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["name"], "Alice Johnson")

        with self.assertRaises(ValueError):
            db.create_user("Alice Duplicate", "alice@example.com", "hashed_pw_456")

        db.update_user(uid, resume_path="data/resumes/user_1.pdf", location="Remote", experience_years=3.0)
        updated = db.get_user_by_id(uid)
        self.assertEqual(updated["resume_path"], "data/resumes/user_1.pdf")
        self.assertEqual(updated["location"], "Remote")
        self.assertEqual(updated["experience_years"], 3.0)

    def test_resume_analysis_and_cache(self) -> None:
        uid = db.create_user("Bob Smith", "bob@example.com", "hashed_pw")
        h = compute_content_hash("Python SQL FastAPI resume", "Software Developer")
        aid = db.save_resume_analysis(
            user_id=uid,
            resume_text="Python SQL FastAPI resume",
            analysis_json='{"overall_score": 82.5}',
            overall_score=82.5,
            classification="Good",
            target_role="Software Developer",
            content_hash=h,
        )
        self.assertGreater(aid, 0)
        cached = db.get_cached_resume_analysis(uid, h)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["overall_score"], 82.5)

        db.delete_resume_analysis(aid)
        self.assertIsNone(db.get_latest_resume_analysis(uid))

    def test_job_preferences_recommendations_and_applications(self) -> None:
        uid = db.create_user("Carol Lee", "carol@example.com", "hashed_pw")
        prefs = db.get_job_preferences(uid)
        self.assertEqual(prefs["min_match_threshold"], 60.0)

        prefs["desired_title"] = "AI Engineer"
        prefs["min_match_threshold"] = 75.0
        db.save_job_preferences(uid, prefs)
        reloaded = db.get_job_preferences(uid)
        self.assertEqual(reloaded["desired_title"], "AI Engineer")
        self.assertEqual(reloaded["min_match_threshold"], 75.0)

        jid, is_new = db.upsert_job_recommendation(
            uid,
            {
                "job_title": "AI Engineer",
                "company_name": "TechCorp",
                "location": "Remote",
                "job_url": "https://example.com/jobs/1",
                "match_percentage": 88.5,
            },
        )
        self.assertTrue(is_new)
        jid2, is_new2 = db.upsert_job_recommendation(
            uid,
            {
                "job_title": "AI Engineer",
                "company_name": "TechCorp",
                "location": "Remote",
                "job_url": "https://example.com/jobs/1",
                "match_percentage": 90.0,
            },
        )
        self.assertFalse(is_new2)
        self.assertEqual(jid, jid2)

        db.upsert_job_application(uid, jid, "Saved", "Looks great")
        db.upsert_job_application(uid, jid, "Applied", "Submitted via portal")
        apps = db.get_job_applications_for_user(uid)
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["status"], "Applied")
        self.assertEqual(len(apps[0]["status_history"]), 2)


if __name__ == "__main__":
    unittest.main()
