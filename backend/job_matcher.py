"""Job requirement extraction and weighted resume-job matching engine (Milestone 3 Task 16)."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from backend.llm_analyzer import JOB_MATCH_EXPLANATION_PROMPT, JOB_REQUIREMENTS_PROMPT, call_llm
from backend.resume_scorer import ACTION_VERBS
from backend.skills_analyzer import SKILL_CATALOG, extract_skills_deterministic

MATCH_WEIGHTS = {
    "skills": 0.50,
    "experience": 0.25,
    "education": 0.15,
    "responsibilities": 0.10,
}

SENIORITY_ORDER = {
    "Entry Level": 1,
    "Mid Level": 2,
    "Senior": 3,
    "Lead/Manager": 4,
}

EDUCATION_ORDER = {
    "high school": 1,
    "diploma": 2,
    "associate": 2,
    "bootcamp": 2,
    "bachelor": 3,
    "b.tech": 3,
    "b.s": 3,
    "b.e": 3,
    "master": 4,
    "m.tech": 4,
    "m.s": 4,
    "mba": 4,
    "phd": 5,
    "doctorate": 5,
}


def extract_job_requirements(
    job_description: str, job_title: str = "", use_llm: bool = False
) -> Dict[str, Any]:
    """Parse job description into must-have skills, nice-to-have skills, experience, education & responsibilities."""
    text = (job_description or "").strip()
    lower = text.lower()

    # Deterministic skill extraction across description
    all_catalog_skills = [s for group in SKILL_CATALOG.values() for s in group]
    found_skills = []
    for skill in all_catalog_skills:
        escaped = re.escape(skill)
        if re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", text, re.IGNORECASE):
            if skill not in found_skills:
                found_skills.append(skill)

    # Split around "Nice to have" / "Preferred" if present
    nice_split = re.split(r"(?:nice to have|preferred|bonus|plus)\s*:", lower, maxsplit=1)
    must_text = nice_split[0] if nice_split else lower
    nice_text = nice_split[1] if len(nice_split) > 1 else ""

    must_have = []
    nice_to_have = []
    for skill in found_skills:
        escaped = re.escape(skill)
        if nice_text and re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", nice_text, re.IGNORECASE):
            if not re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", must_text, re.IGNORECASE):
                nice_to_have.append(skill)
                continue
        must_have.append(skill)

    if not must_have and nice_to_have:
        must_have, nice_to_have = nice_to_have, []

    # Required experience years
    exp_matches = [int(m) for m in re.findall(r"(\d+)\+?\s*(?:years?|yrs?)", lower)]
    req_years = float(min(exp_matches)) if exp_matches else 0.0

    # Seniority level
    combined_title_desc = f"{job_title} {text}".lower()
    if any(k in combined_title_desc for k in ("lead", "principal", "staff", "manager", "architect", "director")):
        seniority = "Lead/Manager"
        if req_years == 0:
            req_years = 5.0
    elif any(k in combined_title_desc for k in ("senior", "sr.", "sr ")):
        seniority = "Senior"
        if req_years == 0:
            req_years = 4.0
    elif any(k in combined_title_desc for k in ("intern", "junior", "entry", "graduate", "fresher")):
        seniority = "Entry Level"
    elif req_years >= 3:
        seniority = "Mid Level"
    else:
        seniority = "Mid Level" if req_years >= 2 else "Entry Level"

    # Education requirement
    req_edu = "Bachelor's"
    if "phd" in lower or "doctorate" in lower:
        req_edu = "PhD"
    elif "master" in lower or "m.tech" in lower or "m.s." in lower:
        req_edu = "Master's"
    elif "bachelor" in lower or "b.tech" in lower or "degree" in lower:
        req_edu = "Bachelor's"
    elif "associate" in lower or "diploma" in lower:
        req_edu = "Associate"

    # Responsibilities sentences
    resp_matches = re.findall(r"(?:responsibilities\s*:|you will\s*:?)([^\n]+)", text, re.IGNORECASE)
    responsibilities: List[str] = []
    if resp_matches:
        for chunk in resp_matches:
            parts = [p.strip(" •-.") for p in re.split(r"[,;]", chunk) if len(p.strip()) > 6]
            responsibilities.extend(parts)
    if not responsibilities:
        sentences = [s.strip() for s in re.split(r"[\.\n]+", text) if len(s.strip().split()) >= 5]
        responsibilities = sentences[:4]

    if use_llm:
        prompt = JOB_REQUIREMENTS_PROMPT.format(job_description=text[:4000])
        resp = call_llm(prompt=prompt, expect_json=True, task_name="job_requirements")
        if resp["success"] and isinstance(resp["data"], dict):
            ai = resp["data"]
            if isinstance(ai.get("must_have_skills"), list) and ai["must_have_skills"]:
                must_have = [str(x).strip() for x in ai["must_have_skills"] if str(x).strip()]
            if isinstance(ai.get("nice_to_have_skills"), list):
                nice_to_have = [str(x).strip() for x in ai["nice_to_have_skills"] if str(x).strip()]
            if isinstance(ai.get("required_experience_years"), (int, float)):
                req_years = float(ai["required_experience_years"])
            if ai.get("seniority_level") in SENIORITY_ORDER:
                seniority = ai["seniority_level"]
            if ai.get("required_education"):
                req_edu = str(ai["required_education"])
            if isinstance(ai.get("responsibilities"), list) and ai["responsibilities"]:
                responsibilities = [str(r).strip() for r in ai["responsibilities"][:6]]

    return {
        "must_have_skills": must_have,
        "nice_to_have_skills": nice_to_have,
        "required_experience_years": req_years,
        "seniority_level": seniority,
        "required_education": req_edu,
        "responsibilities": responsibilities[:6],
    }


def _education_rank(text: str) -> int:
    lower = (text or "").lower()
    best = 0
    for key, rank in EDUCATION_ORDER.items():
        if key in lower:
            best = max(best, rank)
    return best or 3  # Default Bachelor's equivalent if unspecified


def _estimate_candidate_years(user_profile: Dict[str, Any], resume_text: str) -> float:
    prof_years = user_profile.get("experience_years")
    if isinstance(prof_years, (int, float)) and float(prof_years) > 0:
        return float(prof_years)
    lower = (resume_text or "").lower()
    explicit = [int(y) for y in re.findall(r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", lower)]
    if explicit:
        return float(max(explicit))
    years = [int(y) for y in re.findall(r"\b(20[0-2]\d)\b", resume_text or "")]
    if len(years) >= 2:
        return float(max(0, min(15, max(years) - min(years))))
    return 1.0 if "intern" in lower or "project" in lower else 0.5


def calculate_job_match(
    user_profile: Dict[str, Any],
    resume_data: Dict[str, Any],
    job: Dict[str, Any],
    use_llm_explanation: bool = False,
) -> Dict[str, Any]:
    """Compute exact Milestone 3 weighted match percentage (0-100) and detailed breakdown."""
    resume_text = resume_data.get("resume_text") or ""
    extracted_skills = resume_data.get("extracted_skills") or extract_skills_deterministic(resume_text)

    candidate_skills = list(
        dict.fromkeys(
            (extracted_skills.get("programming_languages") or [])
            + (extracted_skills.get("frameworks") or [])
            + (extracted_skills.get("tools") or [])
            + (extracted_skills.get("domain_knowledge") or [])
            + (extracted_skills.get("soft_skills") or [])
            + (extracted_skills.get("certifications") or [])
        )
    )
    cand_lower = {s.lower() for s in candidate_skills}

    reqs = {
        "must_have_skills": job.get("required_skills") or [],
        "nice_to_have_skills": job.get("nice_to_have_skills") or [],
        "required_experience_years": job.get("required_experience_years"),
        "seniority_level": job.get("experience_level"),
        "required_education": job.get("required_education"),
        "responsibilities": job.get("responsibilities") or [],
    }
    if not reqs["must_have_skills"] or reqs["required_experience_years"] is None:
        parsed = extract_job_requirements(job.get("job_description") or "", job.get("job_title") or "")
        reqs["must_have_skills"] = reqs["must_have_skills"] or parsed["must_have_skills"]
        reqs["nice_to_have_skills"] = reqs["nice_to_have_skills"] or parsed["nice_to_have_skills"]
        if reqs["required_experience_years"] is None:
            reqs["required_experience_years"] = parsed["required_experience_years"]
        reqs["seniority_level"] = reqs["seniority_level"] or parsed["seniority_level"]
        reqs["required_education"] = reqs["required_education"] or parsed["required_education"]
        reqs["responsibilities"] = reqs["responsibilities"] or parsed["responsibilities"]

    must_have = reqs["must_have_skills"]
    nice_to_have = reqs["nice_to_have_skills"]

    # 1. SKILLS MATCH (50%)
    matching_must = [s for s in must_have if s.lower() in cand_lower]
    missing_must = [s for s in must_have if s.lower() not in cand_lower]
    matching_nice = [s for s in nice_to_have if s.lower() in cand_lower]

    if must_have:
        base_skill_pct = (len(matching_must) / len(must_have)) * 100.0
        bonus = (len(matching_nice) / max(1, len(nice_to_have))) * 10.0 if nice_to_have else 0.0
        skills_match = min(100.0, round(base_skill_pct + bonus, 1))
    else:
        # Keyword fallback on title + description when no explicit skills extracted
        job_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", f"{job.get('job_title', '')} {job.get('job_description', '')}".lower()))
        overlap = sum(1 for s in cand_lower if s in job_words)
        skills_match = min(100.0, round(45.0 + overlap * 10.0, 1))

    # 2. EXPERIENCE MATCH (25%)
    cand_years = _estimate_candidate_years(user_profile, resume_text)
    req_years = float(reqs.get("required_experience_years") or 0.0)
    if req_years <= 0:
        experience_match = 95.0 if cand_years >= 0.5 else 80.0
    elif cand_years >= req_years:
        experience_match = 100.0
    else:
        experience_match = round(max(25.0, (cand_years / req_years) * 100.0), 1)

    # 3. EDUCATION MATCH (15%)
    cand_edu_rank = _education_rank(
        f"{user_profile.get('education_level', '')} {resume_text[:1500]}"
    )
    req_edu_rank = _education_rank(str(reqs.get("required_education") or "Bachelor's"))
    if cand_edu_rank >= req_edu_rank:
        education_match = 100.0
    elif cand_edu_rank == req_edu_rank - 1:
        education_match = 75.0
    else:
        education_match = 50.0

    # 4. RESPONSIBILITIES MATCH (10%)
    resp_text = " ".join(reqs.get("responsibilities") or []) + " " + (job.get("job_description") or "")
    resp_tokens = {
        w for w in re.findall(r"\b[a-zA-Z]{4,}\b", resp_text.lower())
        if w not in {"with", "that", "this", "from", "have", "will", "your", "team", "work"}
    }
    resume_tokens = set(re.findall(r"\b[a-zA-Z]{4,}\b", resume_text.lower()))
    verb_bonus = sum(1 for v in ACTION_VERBS if v in resume_tokens)
    if resp_tokens:
        overlap_ratio = len(resp_tokens & resume_tokens) / min(25, len(resp_tokens))
        responsibilities_match = min(100.0, round(overlap_ratio * 80.0 + min(20.0, verb_bonus * 3.0), 1))
    else:
        responsibilities_match = 75.0

    overall_match = round(
        (skills_match * MATCH_WEIGHTS["skills"])
        + (experience_match * MATCH_WEIGHTS["experience"])
        + (education_match * MATCH_WEIGHTS["education"])
        + (responsibilities_match * MATCH_WEIGHTS["responsibilities"]),
        1,
    )

    matching_all = list(dict.fromkeys(matching_must + matching_nice))
    explanation = (
        f"Matched {len(matching_must)}/{max(1, len(must_have))} required skills "
        f"({skills_match:.0f}% skill alignment), with {cand_years:.1f} yrs experience vs "
        f"{req_years:.1f} yrs required."
    )
    if missing_must:
        explanation += f" Key gaps to address: {', '.join(missing_must[:4])}."

    if use_llm_explanation:
        prompt = JOB_MATCH_EXPLANATION_PROMPT.format(
            job_title=job.get("job_title", ""),
            company_name=job.get("company_name", ""),
            match_score=overall_match,
            matching_skills=", ".join(matching_all[:8]),
            missing_skills=", ".join(missing_must[:6]),
        )
        llm_resp = call_llm(prompt=prompt, expect_json=False, task_name="job_match_explanation")
        if llm_resp["success"] and llm_resp["text"]:
            explanation = llm_resp["text"]

    breakdown = {
        "skills_match": round(skills_match, 1),
        "experience_match": round(experience_match, 1),
        "education_match": round(education_match, 1),
        "responsibilities_match": round(responsibilities_match, 1),
        "matching_skills": matching_all,
        "missing_skills": missing_must,
        "seniority_level": reqs["seniority_level"],
        "required_experience_years": req_years,
        "candidate_experience_years": round(cand_years, 1),
        "required_education": reqs["required_education"],
    }

    return {
        "match_percentage": overall_match,
        "match_breakdown": breakdown,
        "match_explanation": explanation,
        "required_skills": must_have,
        "nice_to_have_skills": nice_to_have,
        "responsibilities": reqs["responsibilities"],
        "qualifications": [reqs["required_education"], f"{req_years:.0f}+ years experience"],
        "experience_level": job.get("experience_level") or reqs["seniority_level"],
    }
