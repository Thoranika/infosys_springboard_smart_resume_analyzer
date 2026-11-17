"""Job filtering logic with configurable match threshold, location, seniority, and keyword filters (Milestone 3 Task 16)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.job_matcher import SENIORITY_ORDER, calculate_job_match
from backend.scraper import deduplicate_jobs
from utils.database import update_job_match_details


def _parse_min_salary_from_text(salary_str: Optional[str]) -> Optional[int]:
    if not salary_str or "unavailable" in salary_str.lower():
        return None
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]{3,}", salary_str)]
    return min(nums) if nums else None


def filter_jobs(
    jobs: List[Dict[str, Any]],
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Filter a list of scored jobs by match threshold, location, remote, type, seniority, date, salary, and keywords."""
    cfg = filters or {}
    min_match = float(cfg.get("min_match_threshold") if cfg.get("min_match_threshold") is not None else 60.0)
    locations = [loc.strip().lower() for loc in (cfg.get("locations") or []) if loc and loc.strip()]
    remote_pref = (cfg.get("remote_preference") or "Any").strip()
    job_types = [jt.strip().lower() for jt in (cfg.get("job_types") or []) if jt]
    exp_levels = [el.strip().lower() for el in (cfg.get("experience_levels") or []) if el]
    posted_days = cfg.get("posted_within_days")
    min_salary = int(cfg.get("min_salary") or 0)
    include_kw = [k.strip().lower() for k in (cfg.get("include_keywords") or []) if k.strip()]
    exclude_kw = [k.strip().lower() for k in (cfg.get("exclude_keywords") or []) if k.strip()]
    user_max_seniority = cfg.get("max_seniority_gap")  # optional level cap

    cutoff_date = None
    if posted_days:
        cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=int(posted_days))).isoformat()

    filtered: List[Dict[str, Any]] = []
    for job in deduplicate_jobs(jobs):
        score = float(job.get("match_percentage") or 0.0)
        if score < min_match:
            continue

        job_loc = (job.get("location") or "").lower()
        remote_status = (job.get("remote_status") or "").lower()
        is_remote = "remote" in remote_status or "remote" in job_loc

        if remote_pref == "Only Remote" and not is_remote:
            continue
        if remote_pref == "On-site" and is_remote:
            continue
        if remote_pref == "Hybrid" and "hybrid" not in remote_status and "hybrid" not in job_loc:
            continue

        if locations:
            wants_remote = "remote" in locations
            matches_city = any(loc in job_loc for loc in locations if loc != "remote")
            if not (matches_city or (wants_remote and is_remote)):
                continue

        if job_types:
            jt_val = (job.get("job_type") or "full-time").lower()
            if not any(jt in jt_val for jt in job_types):
                continue

        if exp_levels:
            el_val = (job.get("experience_level") or "mid level").lower()
            if not any(el in el_val for el in exp_levels):
                continue

        if user_max_seniority and user_max_seniority in SENIORITY_ORDER:
            job_lvl = job.get("experience_level") or "Mid Level"
            if abs(SENIORITY_ORDER.get(job_lvl, 2) - SENIORITY_ORDER[user_max_seniority]) >= 3:
                continue

        if cutoff_date:
            pdate = (job.get("posted_date") or "")[:10]
            if pdate and pdate < cutoff_date:
                continue

        if min_salary > 0:
            parsed_sal = _parse_min_salary_from_text(job.get("salary_range"))
            if parsed_sal is not None and parsed_sal < min_salary:
                continue

        searchable = f"{job.get('job_title', '')} {job.get('company_name', '')} {job.get('job_description', '')}".lower()
        if include_kw and not all(kw in searchable for kw in include_kw):
            continue
        if exclude_kw and any(kw in searchable for kw in exclude_kw):
            continue

        filtered.append(job)

    return filtered


def filter_and_score_jobs(
    user_id: int,
    jobs: List[Dict[str, Any]],
    user_profile: Dict[str, Any],
    resume_data: Dict[str, Any],
    filters: Optional[Dict[str, Any]] = None,
    persist_scores: bool = True,
) -> List[Dict[str, Any]]:
    """Score jobs using the Milestone 3 weighted formula, optionally persist to DB, and apply filters."""
    scored_jobs: List[Dict[str, Any]] = []
    for job in jobs:
        match_res = calculate_job_match(user_profile, resume_data, job)
        enriched = {**job, **match_res}
        if persist_scores and enriched.get("id"):
            update_job_match_details(
                job_id=enriched["id"],
                match_percentage=enriched["match_percentage"],
                match_breakdown=enriched["match_breakdown"],
                match_explanation=enriched["match_explanation"],
            )
        scored_jobs.append(enriched)

    return filter_jobs(scored_jobs, filters)
