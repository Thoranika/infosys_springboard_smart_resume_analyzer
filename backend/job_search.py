"""Multi-source job search pipeline with deduplication, progress callbacks, and DB persistence (Milestone 3 Task 15)."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from backend.job_matcher import calculate_job_match
from backend.scraper import (
    ArbeitnowJobSource,
    CuratedVerifiedJobSource,
    LinkedInPublicJobSource,
    LinkedInSeleniumScraper,
    RemotiveJobSource,
    TheMuseJobSource,
    build_linkedin_search_url,
    deduplicate_jobs,
)
from backend.skills_analyzer import extract_skills_deterministic
from utils.database import (
    get_job_preferences,
    get_latest_resume_analysis,
    get_user_by_id,
    log_activity,
    save_search_history,
    upsert_job_recommendation,
)
from utils.logger import get_logger

logger = get_logger("job_search")


def search_jobs_for_user(
    user_id: int,
    preferences: Optional[Dict[str, Any]] = None,
    max_results: int = 35,
    progress_callback: Optional[Callable[[str, float, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    allow_network: bool = True,
) -> Dict[str, Any]:
    """Execute job collection across compliant sources, score matches, and persist results."""
    start_time = time.time()
    prefs = preferences or get_job_preferences(user_id)
    user = get_user_by_id(user_id) or {"id": user_id}
    latest_resume = get_latest_resume_analysis(user_id)
    resume_text = (latest_resume or {}).get("resume_text") or ""
    extracted_skills = extract_skills_deterministic(resume_text)
    resume_data = {
        "resume_text": resume_text,
        "extracted_skills": extracted_skills,
    }

    desired_title = (prefs.get("desired_title") or user.get("target_role") or "Software Developer").strip()
    top_skills = extracted_skills.get("programming_languages", [])[:2] + extracted_skills.get("frameworks", [])[:1]
    query = desired_title if desired_title else " ".join(top_skills) or "Software Developer"
    pref_locs = prefs.get("preferred_locations") or []
    location_hint = pref_locs[0] if pref_locs else ""
    linkedin_search_url = build_linkedin_search_url(
        query=query,
        location=location_hint,
        remote_preference=prefs.get("remote_preference") or "Any",
        experience_level=prefs.get("experience_level") or "",
        job_types=prefs.get("job_types") or [],
        resume_skills=top_skills,
    )

    raw_jobs: List[Dict[str, Any]] = []
    sources_used: List[str] = []
    errors: List[str] = []

    def _report(msg: str, pct: float) -> None:
        if progress_callback:
            elapsed = time.time() - start_time
            est_remaining = max(0.0, (elapsed / max(pct, 0.05)) * (1.0 - pct))
            progress_callback(msg, pct, est_remaining)

    _report(f"Searching LinkedIn & public job sources for '{query}'...", 0.15)

    if allow_network:
        # 1. Prioritize Compliant LinkedIn Public Job Feed
        li_public = LinkedInPublicJobSource()
        try:
            _report("Querying LinkedIn public job listings...", 0.20)
            li_pub_jobs = li_public.fetch_jobs(
                query=query,
                location=location_hint,
                limit=15,
                remote_preference=prefs.get("remote_preference") or "Any",
                experience_level=prefs.get("experience_level") or "",
                job_types=prefs.get("job_types") or [],
            )
            if li_pub_jobs:
                raw_jobs.extend(li_pub_jobs)
                sources_used.append(li_public.source_name)
        except Exception as exc:
            errors.append(f"LinkedIn Public Feed: {exc}")

        # 2. Optional compliant LinkedIn Selenium source (only if enabled in .env)
        li_scraper = LinkedInSeleniumScraper()
        if li_scraper.is_enabled():
            try:
                li_jobs = li_scraper.fetch_jobs(query=query, location=location_hint, limit=12)
                if li_jobs:
                    raw_jobs.extend(li_jobs)
                    if li_scraper.source_name not in sources_used:
                        sources_used.append(li_scraper.source_name)
            except Exception as exc:
                errors.append(f"LinkedIn Selenium: {exc}")

        if cancel_check and cancel_check():
            return _finalize_partial(user_id, query, pref_locs, prefs, raw_jobs, resume_data, user, sources_used, errors, cancelled=True)

        # 3. Compliant Public REST APIs
        public_sources = [RemotiveJobSource(), TheMuseJobSource(), ArbeitnowJobSource()]
        for idx, src in enumerate(public_sources):
            if cancel_check and cancel_check():
                return _finalize_partial(user_id, query, pref_locs, prefs, raw_jobs, resume_data, user, sources_used, errors, cancelled=True)
            _report(f"Querying {src.source_name}...", 0.35 + idx * 0.12)
            try:
                fetched = src.fetch_jobs(query=query, location=location_hint, limit=15)
                if fetched:
                    raw_jobs.extend(fetched)
                    sources_used.append(src.source_name)
            except Exception as exc:
                errors.append(f"{src.source_name}: {exc}")

    # Offline-resilient verified public catalog fallback if network APIs returned too few results
    if len(raw_jobs) < 5:
        fallback = CuratedVerifiedJobSource()
        fallback_jobs = fallback.fetch_jobs(query=query, location=location_hint, limit=15)
        raw_jobs.extend(fallback_jobs)
        sources_used.append(fallback.source_name)

    deduped = deduplicate_jobs(raw_jobs)[:max_results]
    _report(f"Found {len(deduped)} unique jobs. Analyzing match scores...", 0.72)

    saved_jobs: List[Dict[str, Any]] = []
    new_jobs_count = 0

    for idx, job in enumerate(deduped):
        if cancel_check and cancel_check():
            break
        match_res = calculate_job_match(user, resume_data, job)
        enriched = {**job, **match_res}
        jid, is_new = upsert_job_recommendation(user_id, enriched)
        enriched["id"] = jid
        if is_new:
            new_jobs_count += 1
        saved_jobs.append(enriched)
        if idx % 5 == 0:
            _report(
                f"Scored {idx + 1}/{len(deduped)} jobs...",
                0.72 + 0.25 * ((idx + 1) / max(1, len(deduped))),
            )

    save_search_history(
        user_id=user_id,
        query_title=query,
        locations=", ".join(pref_locs) if pref_locs else "Any",
        filters=prefs,
        jobs_found_count=len(saved_jobs),
        new_jobs_count=new_jobs_count,
    )
    log_activity(
        user_id,
        "Job Search Completed",
        f"Searched '{query}' across {len(sources_used)} source(s): {len(saved_jobs)} jobs ({new_jobs_count} new).",
    )
    _report("Completed job matching!", 1.0)

    return {
        "jobs": saved_jobs,
        "total_found": len(saved_jobs),
        "new_jobs_count": new_jobs_count,
        "sources_used": sources_used,
        "errors": errors,
        "linkedin_search_url": linkedin_search_url,
        "cancelled": False,
    }


def _finalize_partial(
    user_id: int,
    query: str,
    pref_locs: List[str],
    prefs: Dict[str, Any],
    raw_jobs: List[Dict[str, Any]],
    resume_data: Dict[str, Any],
    user: Dict[str, Any],
    sources_used: List[str],
    errors: List[str],
    cancelled: bool,
) -> Dict[str, Any]:
    deduped = deduplicate_jobs(raw_jobs)
    saved: List[Dict[str, Any]] = []
    new_cnt = 0
    for job in deduped:
        match_res = calculate_job_match(user, resume_data, job)
        enriched = {**job, **match_res}
        jid, is_new = upsert_job_recommendation(user_id, enriched)
        enriched["id"] = jid
        if is_new:
            new_cnt += 1
        saved.append(enriched)
    save_search_history(
        user_id=user_id,
        query_title=query,
        locations=", ".join(pref_locs) if pref_locs else "Any",
        filters=prefs,
        jobs_found_count=len(saved),
        new_jobs_count=new_cnt,
    )
    return {
        "jobs": saved,
        "total_found": len(saved),
        "new_jobs_count": new_cnt,
        "sources_used": sources_used,
        "errors": errors,
        "cancelled": cancelled,
    }
