"""Milestone 2 tests: weighted resume scoring, strengths/weaknesses, skills gap, improvements & PDF export."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import utils.database as db
from backend.improvement_suggestions import (
    generate_improvement_suggestions,
    update_improvement_item_status,
)
from backend.resume_analyzer import analyze_strengths_and_weaknesses, run_full_resume_analysis
from backend.resume_scorer import calculate_resume_score, classify_resume_score
from backend.skills_analyzer import analyze_skills_gap_structured, extract_resume_skills
from utils.pdf_generator import generate_analysis_pdf_report

STRONG_RESUME = """
Alex Morgan
alex.morgan@example.com | +1 555-234-5678 | https://linkedin.com/in/alexmorgan | https://github.com/alexmorgan

SUMMARY
Software Developer with 3+ years of experience building Python, FastAPI, and SQL microservices on AWS.

EXPERIENCE
Software Engineer - FinTech Corp (2022 - 2025)
- Engineered REST APIs in Python and FastAPI serving 50,000+ daily users, reducing p95 latency by 35%.
- Automated Docker and GitHub Actions CI/CD pipelines, cutting deployment times by 60%.
- Collaborated across Agile teams to optimize PostgreSQL queries and achieve 95% unit test coverage.

PROJECTS
AI Resume Screener
- Developed a Streamlit and LangChain NLP assistant achieving 92% parsing accuracy across 1,000+ documents.

SKILLS
Programming Languages: Python, SQL, JavaScript
Frameworks: FastAPI, Django, React, Streamlit, LangChain
Tools: Git, Docker, AWS, PostgreSQL, Linux
Soft Skills: Communication, Leadership, Problem Solving, Agile

EDUCATION
Bachelor of Science in Computer Science (2018 - 2022)
Certifications: AWS Certified Cloud Practitioner
"""

WEAK_RESUME = """
John
Worked on website project in college.
Responsible for helping with database tasks.
"""


class TestResumeAnalysis(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self._tmpdir.name, "test_analysis.db")
        db.init_db()
        self.user_id = db.create_user("Alex Morgan", "alex@example.com", "hashed_pw")

    def tearDown(self) -> None:
        db.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_weighted_scoring_formula_and_classifications(self) -> None:
        self.assertEqual(classify_resume_score(92), "Excellent")
        self.assertEqual(classify_resume_score(80), "Good")
        self.assertEqual(classify_resume_score(65), "Average")
        self.assertEqual(classify_resume_score(45), "Needs Improvement")

        strong = calculate_resume_score(STRONG_RESUME, target_role="Software Developer", use_llm=False)
        weak = calculate_resume_score(WEAK_RESUME, target_role="Software Developer", use_llm=False)

        self.assertGreater(strong["overall_score"], weak["overall_score"])
        self.assertGreaterEqual(strong["overall_score"], 75.0)
        self.assertLess(weak["overall_score"], 60.0)

        # Verify exact weighted sum
        comps = strong["components"]
        expected = round(
            0.25 * comps["completeness"]["score"]
            + 0.30 * comps["content_quality"]["score"]
            + 0.15 * comps["formatting"]["score"]
            + 0.20 * comps["keyword_relevance"]["score"]
            + 0.10 * comps["experience"]["score"],
            1,
        )
        self.assertEqual(strong["overall_score"], expected)

    def test_strengths_weaknesses_and_skills_gap(self) -> None:
        sw = analyze_strengths_and_weaknesses(STRONG_RESUME, target_role="Software Developer", use_llm=False)
        self.assertGreaterEqual(len(sw["strengths"]), 5)
        self.assertLessEqual(len(sw["strengths"]), 7)
        self.assertGreaterEqual(len(sw["weaknesses"]), 5)
        self.assertLessEqual(len(sw["weaknesses"]), 7)
        for w in sw["weaknesses"]:
            self.assertIn(w["severity"], {"minor", "moderate", "critical"})
            self.assertGreaterEqual(w["confidence"], 0)
            self.assertLessEqual(w["confidence"], 100)

        skills = extract_resume_skills(STRONG_RESUME, use_llm=False)
        self.assertIn("Python", skills["programming_languages"])
        self.assertIn("FastAPI", skills["frameworks"])
        self.assertIn("Docker", skills["tools"])
        self.assertIn("3+ years", skills["skill_experience_years"].get("Python", ""))

        gap = analyze_skills_gap_structured(STRONG_RESUME, target_role="Software Developer", user_id=self.user_id, use_llm=False)
        self.assertGreaterEqual(len(gap["recommendations"]), 5)
        self.assertIn("coverage_percentage", gap["chart_data"])

    def test_full_pipeline_improvements_and_pdf_report(self) -> None:
        full = run_full_resume_analysis(self.user_id, STRONG_RESUME, target_role="Software Developer", use_llm=False)
        self.assertIn("analysis_id", full)

        # Cache hit check
        cached = run_full_resume_analysis(self.user_id, STRONG_RESUME, target_role="Software Developer", use_llm=False)
        self.assertTrue(cached.get("from_cache"))

        # Improvement suggestions & status persistence
        plan = generate_improvement_suggestions(
            STRONG_RESUME,
            weaknesses=full["weaknesses"],
            skills_gap=full["skills_gap"],
            score_data=full["score_data"],
            user_id=self.user_id,
            analysis_id=full["analysis_id"],
            use_llm=False,
        )
        self.assertGreaterEqual(len(plan["before_after_examples"]), 1)
        self.assertIn("Professional Summary", plan["section_recommendations"])
        first_id = plan["high_impact"][0]["id"]
        updated_map = update_improvement_item_status(self.user_id, first_id, "Applied")
        self.assertEqual(updated_map[first_id], "Applied")

        # PDF Export check
        pdf_bytes = generate_analysis_pdf_report("Alex Morgan", full, save_to_disk=False)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_bytes), 2000)


if __name__ == "__main__":
    unittest.main()
