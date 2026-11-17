"""Milestone 3 tests: scraping deduplication, job matching formula, filtering, ranking & tracking."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import utils.database as db
from backend.job_filter import filter_jobs
from backend.job_matcher import calculate_job_match, extract_job_requirements
from backend.job_recommendations import (
    compare_jobs,
    generate_application_tips,
    rank_job_recommendations,
    update_job_application_status,
)
from backend.job_search import search_jobs_for_user
from backend.scraper import (
    build_linkedin_job_fallback_url,
    build_linkedin_search_url,
    deduplicate_jobs,
    is_verified_linkedin_job_url,
    normalize_posted_date,
)
from backend.skills_analyzer import extract_skills_deterministic


class TestJobMatchingAndRecommendations(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self._tmpdir.name, "test_jobs.db")
        db.init_db()
        self.uid = db.create_user("Priya Nair", "priya@example.com", "hashed_pw")
        db.update_user(self.uid, experience_years=2.5, education_level="Bachelor's", location="Remote")
        self.resume_text = (
            "Priya Nair\nBachelor of Technology in Computer Science\n"
            "2+ years of experience with Python, FastAPI, SQL, Docker, Git, REST API, Unit Testing.\n"
            "Engineered scalable backend microservices and automated CI/CD deployments."
        )
        db.save_resume_analysis(self.uid, self.resume_text, '{"score": 82}')

    def tearDown(self) -> None:
        db.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_exact_match_formula_and_requirement_extraction(self) -> None:
        job = {
            "job_title": "Backend Python Developer",
            "company_name": "CloudNova",
            "location": "Remote",
            "remote_status": "Remote",
            "posted_date": "2026-11-16",
            "job_description": (
                "Required: Python, FastAPI, SQL, Docker, Git, REST API, 2+ years experience, Bachelor's degree. "
                "Responsibilities: Build scalable backend microservices and write unit tests. "
                "Nice to have: AWS, Kubernetes."
            ),
        }
        reqs = extract_job_requirements(job["job_description"], job["job_title"])
        self.assertIn("Python", reqs["must_have_skills"])
        self.assertEqual(reqs["required_experience_years"], 2.0)

        user_profile = db.get_user_by_id(self.uid)
        resume_data = {
            "resume_text": self.resume_text,
            "extracted_skills": extract_skills_deterministic(self.resume_text),
        }
        match = calculate_job_match(user_profile, resume_data, job)
        bd = match["match_breakdown"]
        expected = round(
            0.50 * bd["skills_match"]
            + 0.25 * bd["experience_match"]
            + 0.15 * bd["education_match"]
            + 0.10 * bd["responsibilities_match"],
            1,
        )
        self.assertEqual(match["match_percentage"], expected)
        self.assertGreaterEqual(match["match_percentage"], 80.0)

    def test_filtering_ranking_comparison_and_search(self) -> None:
        # Offline fallback search populates real DB entries and scores them
        res = search_jobs_for_user(self.uid, allow_network=False)
        self.assertGreaterEqual(res["total_found"], 5)
        jobs = db.get_job_recommendations_for_user(self.uid)
        self.assertGreaterEqual(len(jobs), 5)

        filtered = filter_jobs(jobs, {"min_match_threshold": 60.0, "remote_preference": "Only Remote"})
        for j in filtered:
            self.assertGreaterEqual(j["match_percentage"], 60.0)

        ranked_bundle = rank_job_recommendations(jobs)
        ranked = ranked_bundle["ranked_jobs"]
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(ranked[i]["match_percentage"], ranked[i + 1]["match_percentage"])

        # Tips & Comparison
        user_profile = db.get_user_by_id(self.uid)
        resume_data = {"resume_text": self.resume_text, "extracted_skills": extract_skills_deterministic(self.resume_text)}
        tips = generate_application_tips(user_profile, resume_data, ranked[0], use_llm=False)
        self.assertIn("customized_cover_letter", tips)

        cmp = compare_jobs(ranked[:2])
        self.assertEqual(len(cmp["rows"]), 2)
        self.assertIn("highest_match", cmp["highlights"])

        # Tracking & Not Interested
        update_job_application_status(self.uid, ranked[0]["id"], "Applied", "Applied online")
        apps = db.get_job_applications_for_user(self.uid)
        self.assertEqual(apps[0]["status"], "Applied")

        # Date & Deduplication helpers
        self.assertRegex(normalize_posted_date("2 days ago"), r"^\d{4}-\d{2}-\d{2}$")
        deduped = deduplicate_jobs([
            {"job_title": "Dev", "company_name": "A", "location": "Remote", "job_url": "https://x.com/1"},
            {"job_title": "Dev", "company_name": "A", "location": "Remote", "job_url": "https://x.com/1"},
        ])
        self.assertEqual(len(deduped), 1)

    def test_linkedin_url_helpers_and_verification(self) -> None:
        search_url = build_linkedin_search_url(
            query="Software Developer",
            location="India",
            remote_preference="Only Remote",
            experience_level="Entry Level",
            job_types=["Full-time"],
            resume_skills=["Python"],
        )
        self.assertTrue(search_url.startswith("https://www.linkedin.com/jobs/search/?"))
        self.assertIn("Software%20Developer", search_url)
        self.assertIn("location=India", search_url)
        self.assertIn("f_WT=2", search_url)
        self.assertIn("f_E=2", search_url)
        self.assertIn("f_JT=F", search_url)

        fallback_url = build_linkedin_job_fallback_url("Backend Engineer", "Acme Corp", "Bengaluru")
        self.assertIn("linkedin.com/jobs/search/", fallback_url)
        self.assertIn("Backend%20Engineer%20Acme%20Corp", fallback_url)

        self.assertTrue(is_verified_linkedin_job_url("https://www.linkedin.com/jobs/view/3987654321"))
        self.assertFalse(is_verified_linkedin_job_url(search_url))
        self.assertFalse(is_verified_linkedin_job_url("https://www.arbeitnow.com/jobs/123"))


if __name__ == "__main__":
    unittest.main()
