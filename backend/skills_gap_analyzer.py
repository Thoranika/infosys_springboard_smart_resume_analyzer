"""Compatibility wrapper for skills gap analysis."""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.skills_analyzer import analyze_skills_gap_structured, infer_target_role
from utils.database import get_latest_resume_analysis


def run_skills_gap_analysis(
    user_id: int, target_role: Optional[str] = None
) -> Dict[str, Any]:
    """Run structured skills gap analysis on the user's latest uploaded resume."""
    resume = get_latest_resume_analysis(user_id)
    if not resume:
        return {"error": "No resume found. Please upload your resume first."}

    text = resume["resume_text"]
    chosen_role = target_role or infer_target_role(text)
    return analyze_skills_gap_structured(text, target_role=chosen_role, user_id=user_id)
