"""Intelligent job ranking, application tips, comparison, and tracking engine (Milestone 3 Task 17)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.llm_analyzer import APPLICATION_TIPS_PROMPT, call_llm
from utils.database import (
    deactivate_job_for_user,
    get_job_by_id,
    log_activity,
    update_job_match_details,
    upsert_job_application,
)


def _applicants_numeric(raw: Any) -> int:
    m = re.search(r"\d+", str(raw or ""))
    return int(m.group(0)) if m else 999


def _salary_numeric(raw: Any) -> int:
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]{3,}", str(raw or ""))]
    return max(nums) if nums else 0


def _compute_priority_score(job: Dict[str, Any], user_preferences: Optional[Dict[str, Any]] = None) -> float:
    """Compute composite ranking score factoring match %, recency, low applicants, salary & remote preference."""
    match_pct = float(job.get("match_percentage") or 0.0)
    prefs = user_preferences or {}

    # Recency bonus (0-8 points)
    recency_bonus = 0.0
    pdate = (job.get("posted_date") or "")[:10]
    try:
        d = datetime.strptime(pdate, "%Y-%m-%d").date()
        age_days = max(0, (datetime.now(timezone.utc).date() - d).days)
        recency_bonus = max(0.0, 8.0 - age_days * 0.8)
    except Exception:
        pass

    # Competition bonus (fewer applicants -> higher score, 0-5 points)
    apps = _applicants_numeric(job.get("applicants_count"))
    comp_bonus = 5.0 if apps <= 20 else (2.5 if apps <= 50 else 0.0)

    # Remote alignment bonus (0-4 points)
    remote_pref = (prefs.get("remote_preference") or "Any").lower()
    job_remote = (job.get("remote_status") or "").lower()
    remote_bonus = 4.0 if (remote_pref == "only remote" and "remote" in job_remote) else 0.0

    # Salary alignment bonus (0-3 points)
    min_sal = int(prefs.get("min_salary") or 0)
    sal_val = _salary_numeric(job.get("salary_range"))
    sal_bonus = 3.0 if (min_sal > 0 and sal_val >= min_sal) else 0.0

    return round(match_pct + recency_bonus + comp_bonus + remote_bonus + sal_bonus, 2)


def rank_job_recommendations(
    jobs: List[Dict[str, Any]],
    user_preferences: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Rank jobs primarily by match %, secondarily by posted date, and group into tiers."""
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

    enriched: List[Dict[str, Any]] = []
    for job in jobs:
        item = dict(job)
        item["priority_score"] = _compute_priority_score(item, user_preferences)
        is_urgent = (item.get("posted_date") or "")[:10] >= yesterday
        is_excellent = float(item.get("match_percentage") or 0.0) >= 85.0
        item["is_featured"] = is_excellent or is_urgent
        item["is_apply_first"] = (
            float(item.get("match_percentage") or 0.0) >= 75.0
            and is_urgent
            and _applicants_numeric(item.get("applicants_count")) <= 30
        )
        enriched.append(item)

    # Primary sort: match_percentage DESC, Secondary sort: posted_date DESC, Tertiary: priority_score DESC
    ranked = sorted(
        enriched,
        key=lambda j: (
            float(j.get("match_percentage") or 0.0),
            str(j.get("posted_date") or ""),
            float(j.get("priority_score") or 0.0),
        ),
        reverse=True,
    )

    best_matches = ranked[:20]
    excellent = [j for j in ranked if float(j.get("match_percentage") or 0.0) >= 85.0]
    good = [j for j in ranked if 70.0 <= float(j.get("match_percentage") or 0.0) < 85.0]
    fair = [j for j in ranked if 60.0 <= float(j.get("match_percentage") or 0.0) < 70.0]
    featured = [j for j in ranked if j.get("is_featured")]
    apply_first = sorted(
        [j for j in ranked if j.get("is_apply_first")],
        key=lambda x: x["priority_score"],
        reverse=True,
    )

    # Group jobs that share similar top skills so the user can reuse one base cover letter
    cover_groups: Dict[str, List[Dict[str, Any]]] = {}
    for j in ranked:
        reqs = tuple(sorted((j.get("required_skills") or [])[:3]))
        group_key = ", ".join(reqs) if reqs else j.get("experience_level") or "General Role"
        cover_groups.setdefault(group_key, []).append(j)
    reusable_groups = {k: v for k, v in cover_groups.items() if len(v) >= 2}

    return {
        "ranked_jobs": ranked,
        "best_matches": best_matches,
        "excellent": excellent,
        "good": good,
        "fair": fair,
        "featured": featured,
        "apply_first": apply_first,
        "cover_letter_groups": reusable_groups,
    }


def generate_application_tips(
    user_profile: Dict[str, Any],
    resume_data: Dict[str, Any],
    job: Dict[str, Any],
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Generate personalized application advice, interview prep, cover letter, and keyword tweaks."""
    cached_tips = job.get("application_tips")
    if isinstance(cached_tips, dict) and cached_tips.get("customized_cover_letter"):
        return cached_tips

    breakdown = job.get("match_breakdown") or {}
    matching = breakdown.get("matching_skills") or []
    missing = breakdown.get("missing_skills") or []
    title = job.get("job_title") or "Target Role"
    company = job.get("company_name") or "the Company"
    candidate_name = user_profile.get("name") or "Candidate"
    resume_text = (resume_data.get("resume_text") or "")[:4000]

    tips: Dict[str, Any] = {
        "skills_to_highlight": matching[:6] or ["Python", "Problem Solving", "Team Collaboration"],
        "how_to_address_gaps": [
            f"Address missing skill '{s}' by emphasizing rapid upskilling or transferable adjacent projects."
            for s in missing[:4]
        ] or ["All core requirements align well with your current profile."],
        "interview_talking_points": [
            f"Walk through a recent project demonstrating {', '.join(matching[:3]) or 'core engineering delivery'} with measurable results.",
            f"Explain how your architecture and debugging workflow meets {company}'s production quality goals.",
            "Prepare a concise STAR story covering technical trade-offs and cross-functional collaboration.",
        ],
        "company_research_tips": [
            f"Review {company}'s recent product launches, engineering blog posts, and tech stack choices.",
            f"Check {company}'s mission statement and recent press/LinkedIn updates before the recruiter screen.",
        ],
        "common_interview_questions": [
            f"Tell me about a challenging technical problem you solved relevant to {title}.",
            f"How have you used {', '.join(matching[:2]) or 'your primary stack'} in a production or team setting?",
            "Describe how you test, debug, and measure performance improvements in your code.",
        ],
        "customized_cover_letter": (
            f"Dear {company} Hiring Team,\n\n"
            f"I am excited to apply for the {title} position. With hands-on experience in "
            f"{', '.join(matching[:5]) or 'software engineering and analytical problem-solving'}, "
            f"I bring a strong track record of delivering clean, tested, and measurable technical solutions.\n\n"
            f"In my recent work, I have built and optimized systems closely aligned with your team's needs. "
            f"I am particularly energized by {company}'s focus on engineering excellence and would welcome "
            f"the opportunity to contribute immediately while rapidly expanding into "
            f"{', '.join(missing[:2]) or 'new domain initiatives'}.\n\n"
            f"Thank you for your time and consideration.\n\nSincerely,\n{candidate_name}"
        ),
        "resume_keyword_tweaks": (
            [f"Add exact skill/keyword phrasing where truthful: '{s}'" for s in missing[:5]]
            + [f"Move '{', '.join(matching[:4])}' near the top of your Skills and Summary sections."]
        ),
    }

    if use_llm:
        prompt = APPLICATION_TIPS_PROMPT.format(
            job_title=title,
            company_name=company,
            matching_skills=", ".join(matching[:8]),
            missing_skills=", ".join(missing[:6]),
            resume_text=resume_text,
        )
        llm_resp = call_llm(prompt=prompt, expect_json=True, task_name="application_tips")
        if llm_resp["success"] and isinstance(llm_resp["data"], dict):
            ai = llm_resp["data"]
            for key in tips:
                if ai.get(key):
                    tips[key] = ai[key]

    if job.get("id"):
        update_job_match_details(
            job_id=job["id"],
            match_percentage=float(job.get("match_percentage") or 0.0),
            match_breakdown=breakdown,
            match_explanation=job.get("match_explanation") or "",
            application_tips=tips,
        )

    return tips


def compare_jobs(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare 2+ jobs side-by-side and highlight differentiating factors."""
    if not jobs:
        return {"rows": [], "highlights": {}}

    rows = []
    for j in jobs:
        bd = j.get("match_breakdown") or {}
        rows.append(
            {
                "id": j.get("id"),
                "Job Title": j.get("job_title"),
                "Company": j.get("company_name"),
                "Match %": float(j.get("match_percentage") or 0.0),
                "Location": j.get("location"),
                "Remote": j.get("remote_status"),
                "Salary": j.get("salary_range") or "Unavailable",
                "Applicants": j.get("applicants_count") or "Unavailable",
                "Posted Date": j.get("posted_date") or "N/A",
                "Required Skills": ", ".join((j.get("required_skills") or [])[:6]) or "N/A",
                "Missing Skills Count": len(bd.get("missing_skills") or []),
            }
        )

    best_match = max(rows, key=lambda r: r["Match %"])
    fewest_gaps = min(rows, key=lambda r: r["Missing Skills Count"])
    most_recent = max(rows, key=lambda r: str(r["Posted Date"]))
    best_salary = max(rows, key=lambda r: _salary_numeric(r["Salary"]))

    highlights = {
        "highest_match": f"{best_match['Job Title']} at {best_match['Company']} ({best_match['Match %']}%)",
        "fewest_missing_skills": f"{fewest_gaps['Job Title']} ({fewest_gaps['Missing Skills Count']} missing)",
        "most_recent": f"{most_recent['Job Title']} ({most_recent['Posted Date']})",
    }
    if _salary_numeric(best_salary["Salary"]) > 0:
        highlights["best_salary"] = f"{best_salary['Job Title']} ({best_salary['Salary']})"

    return {"rows": rows, "highlights": highlights}


def update_job_application_status(
    user_id: int, job_id: int, status: str, notes: str = ""
) -> str:
    """Update tracking status ('Saved', 'Applied', 'Interviewing', 'Rejected', 'Not Interested')."""
    if status == "Not Interested":
        deactivate_job_for_user(user_id, job_id)
        log_activity(user_id, "Job Dismissed", f"Marked job #{job_id} as Not Interested.")
        return "Not Interested"

    allowed = {"Saved", "Applied", "Interviewing", "Rejected"}
    normalized = status if status in allowed else "Saved"
    upsert_job_application(user_id, job_id, normalized, notes)
    job = get_job_by_id(job_id)
    title = job["job_title"] if job else f"#{job_id}"
    log_activity(user_id, f"Job {normalized}", f"Updated '{title}' status to {normalized}.")
    return normalized
