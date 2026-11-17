"""Weighted multi-factor resume scoring system (Milestone 2 Task 11)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.llm_analyzer import SCORING_PROMPT, call_llm
from backend.resume_parser import detect_resume_sections
from backend.skills_analyzer import ROLE_STANDARDS, extract_skills_deterministic

COMPONENT_WEIGHTS: Dict[str, float] = {
    "completeness": 0.25,
    "content_quality": 0.30,
    "formatting": 0.15,
    "keyword_relevance": 0.20,
    "experience": 0.10,
}

COMPONENT_LABELS: Dict[str, str] = {
    "completeness": "Completeness",
    "content_quality": "Content Quality",
    "formatting": "Formatting & Structure",
    "keyword_relevance": "Keyword Relevance",
    "experience": "Experience Depth",
}

INDUSTRY_BENCHMARKS: Dict[str, float] = {
    "completeness": 82.0,
    "content_quality": 76.0,
    "formatting": 80.0,
    "keyword_relevance": 74.0,
    "experience": 72.0,
    "overall": 77.0,
}

ACTION_VERBS = {
    "achieved", "architected", "automated", "built", "collaborated", "created",
    "decreased", "delivered", "deployed", "designed", "developed", "engineered",
    "enhanced", "established", "executed", "generated", "implemented", "improved",
    "increased", "integrated", "launched", "led", "managed", "mentored", "migrated",
    "optimized", "orchestrated", "reduced", "refactored", "resolved", "scaled",
    "spearheaded", "streamlined", "tested", "trained",
}


def classify_resume_score(score: float) -> str:
    """Classify numeric resume score according to Milestone 2 rubric."""
    if score >= 90.0:
        return "Excellent"
    if score >= 75.0:
        return "Good"
    if score >= 60.0:
        return "Average"
    return "Needs Improvement"


def _find_matching_lines(text: str, pattern: re.Pattern[str], limit: int = 2) -> List[str]:
    matches: List[str] = []
    for line in (text or "").splitlines():
        clean = line.strip()
        if clean and pattern.search(clean):
            matches.append(clean[:140])
            if len(matches) >= limit:
                break
    return matches


def _score_deterministic(
    resume_text: str, target_role: str, extracted_skills: Optional[Dict[str, Any]] = None
) -> Dict[str, Dict[str, Any]]:
    """Compute evidence-based component scores (0-100) from actual resume text."""
    text = (resume_text or "").strip()
    lower = text.lower()
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    sections = detect_resume_sections(text)
    skills_data = extracted_skills or extract_skills_deterministic(text)

    # 1. COMPLETENESS (25%)
    has_email = bool(re.search(r"[\w\.\+\-]+@[\w\-]+\.[\w\.\-]+", text))
    has_phone = bool(re.search(r"(\+?\d[\d\-\s\(\)]{7,}\d)", text))
    has_link = bool(re.search(r"(linkedin\.com|github\.com|portfolio|https?://)", lower))
    completeness_points = 0
    completeness_examples = []
    if has_email:
        completeness_points += 15
    if has_phone or has_link:
        completeness_points += 10
    if sections["summary"]:
        completeness_points += 15
        completeness_examples.append("Summary/Profile section detected")
    if sections["experience"] or sections["projects"]:
        completeness_points += 25
        completeness_examples.append("Experience/Projects section detected")
    if sections["education"]:
        completeness_points += 20
        completeness_examples.append("Education section detected")
    if sections["skills"]:
        completeness_points += 15
        completeness_examples.append("Skills section detected")
    completeness_score = min(100, completeness_points)

    missing_sections = [
        name.title()
        for name, present in [
            ("email", has_email),
            ("summary", sections["summary"]),
            ("experience", sections["experience"] or sections["projects"]),
            ("education", sections["education"]),
            ("skills", sections["skills"]),
        ]
        if not present
    ]
    completeness_expl = (
        "All essential resume sections and contact details are present."
        if not missing_sections
        else f"Detected core sections, but missing or unclear: {', '.join(missing_sections)}."
    )

    # 2. CONTENT QUALITY (30%)
    found_verbs = sorted({v for v in ACTION_VERBS if re.search(rf"\b{v}\b", lower)})
    metric_matches = re.findall(
        r"(\b\d+(?:\.\d+)?%|\$\d+[\d,]*|\b\d+\+?\s*(?:users|clients|ms|x|times|projects|engineers|months|years|k|m)\b)",
        lower,
    )
    verb_score = min(45, len(found_verbs) * 6)
    metric_score = min(40, len(metric_matches) * 10)
    depth_score = 15 if word_count >= 220 else int((word_count / 220) * 15)
    content_score = min(100, verb_score + metric_score + depth_score)

    content_examples = _find_matching_lines(
        text, re.compile(r"(\d+%|\$\d+|\b(?:" + "|".join(list(ACTION_VERBS)[:15]) + r")\b)", re.IGNORECASE), limit=2
    )
    content_expl = (
        f"Found {len(found_verbs)} strong action verbs and {len(metric_matches)} quantified metrics/numbers."
    )

    # 3. FORMATTING (15%)
    bullet_lines = [ln for ln in lines if ln.startswith(("-", "•", "*", "▪", "–")) or re.match(r"^\d+[\.\)]", ln)]
    avg_line_len = sum(len(ln) for ln in lines) / max(1, len(lines))
    fmt_points = 30
    if 220 <= word_count <= 950:
        fmt_points += 30
    elif 120 <= word_count < 220 or 950 < word_count <= 1300:
        fmt_points += 18
    else:
        fmt_points += 8
    if len(bullet_lines) >= 4:
        fmt_points += 25
    elif len(bullet_lines) >= 1:
        fmt_points += 12
    if avg_line_len <= 115:
        fmt_points += 15
    else:
        fmt_points += 5
    formatting_score = min(100, fmt_points)
    formatting_expl = (
        f"Word count is {word_count} words across {len(lines)} lines with {len(bullet_lines)} bulleted statements."
    )
    formatting_examples = bullet_lines[:2] if bullet_lines else lines[:2]

    # 4. KEYWORD RELEVANCE (20%)
    role_spec = ROLE_STANDARDS.get(target_role, ROLE_STANDARDS["Software Developer"])
    role_skills = list(dict.fromkeys(role_spec["must_have"] + role_spec["nice_to_have"]))
    present_skills_lower = {
        s.lower()
        for s in (
            skills_data["programming_languages"]
            + skills_data["frameworks"]
            + skills_data["tools"]
            + skills_data["domain_knowledge"]
            + skills_data["soft_skills"]
        )
    }
    matched_role_skills = [s for s in role_skills if s.lower() in present_skills_lower]
    kw_ratio = len(matched_role_skills) / max(1, len(role_spec["must_have"]))
    keyword_score = min(100, int(round(min(1.0, kw_ratio) * 85 + min(15, len(present_skills_lower) * 1.5))))
    keyword_expl = (
        f"Matched {len(matched_role_skills)} target-role skills for {target_role} "
        f"({len(present_skills_lower)} total distinct skills extracted)."
    )
    keyword_examples = [", ".join(matched_role_skills[:8])] if matched_role_skills else ["No target-role keywords detected"]

    # 5. EXPERIENCE (10%)
    year_mentions = [int(y) for y in re.findall(r"\b(20[0-2]\d|199\d)\b", text)]
    explicit_exp = re.findall(r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", lower)
    est_years = 0
    if explicit_exp:
        est_years = max(int(y) for y in explicit_exp)
    elif len(year_mentions) >= 2:
        est_years = max(0, min(20, max(year_mentions) - min(year_mentions)))

    exp_points = 25 if (sections["experience"] or sections["projects"]) else 10
    exp_points += min(45, est_years * 12)
    if re.search(r"\b(intern|engineer|developer|analyst|scientist|lead|manager|architect)\b", lower):
        exp_points += 20
    if sections["certifications"]:
        exp_points += 10
    experience_score = min(100, exp_points)
    experience_expl = (
        f"Detected ~{est_years} year(s) timeline span and relevant role/project progression."
        if est_years > 0
        else "Experience timeline years were not explicitly quantified; scored based on project/role markers."
    )
    experience_examples = _find_matching_lines(
        text, re.compile(r"\b(20[0-2]\d|intern|developer|engineer|analyst|manager|lead)\b", re.IGNORECASE), limit=2
    )

    return {
        "completeness": {
            "score": int(completeness_score),
            "explanation": completeness_expl,
            "examples": completeness_examples[:2],
        },
        "content_quality": {
            "score": int(content_score),
            "explanation": content_expl,
            "examples": content_examples[:2],
        },
        "formatting": {
            "score": int(formatting_score),
            "explanation": formatting_expl,
            "examples": formatting_examples[:2],
        },
        "keyword_relevance": {
            "score": int(keyword_score),
            "explanation": keyword_expl,
            "examples": keyword_examples[:2],
        },
        "experience": {
            "score": int(experience_score),
            "explanation": experience_expl,
            "examples": experience_examples[:2],
        },
    }


def calculate_resume_score(
    resume_text: str,
    target_role: str = "Software Developer",
    extracted_skills: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Evaluate resume across all 5 weighted components and return overall score + breakdown."""
    det_components = _score_deterministic(resume_text, target_role, extracted_skills)
    mode = "demo"

    if use_llm:
        prompt = SCORING_PROMPT.format(
            target_role=target_role,
            resume_text=(resume_text or "")[:6500],
        )
        llm_resp = call_llm(prompt=prompt, expect_json=True, task_name="resume_scoring")
        if llm_resp["success"] and isinstance(llm_resp["data"], dict):
            mode = "live"
            ai_scores = llm_resp["data"]
            for key in COMPONENT_WEIGHTS:
                ai_comp = ai_scores.get(key)
                if isinstance(ai_comp, dict) and isinstance(ai_comp.get("score"), (int, float)):
                    bounded = max(0, min(100, int(round(float(ai_comp["score"])))))
                    # Blend 70% LLM rubric with 30% deterministic check to anchor against extreme variance
                    blended = int(round(0.7 * bounded + 0.3 * det_components[key]["score"]))
                    det_components[key]["score"] = max(0, min(100, blended))
                    if ai_comp.get("explanation"):
                        det_components[key]["explanation"] = str(ai_comp["explanation"])
                    if isinstance(ai_comp.get("examples"), list) and ai_comp["examples"]:
                        det_components[key]["examples"] = [str(e) for e in ai_comp["examples"][:3]]

    weighted_sum = 0.0
    components_out: Dict[str, Dict[str, Any]] = {}
    for key, weight in COMPONENT_WEIGHTS.items():
        comp_score = float(det_components[key]["score"])
        contrib = round(comp_score * weight, 2)
        weighted_sum += comp_score * weight
        components_out[key] = {
            "key": key,
            "label": COMPONENT_LABELS[key],
            "score": int(round(comp_score)),
            "weight": weight,
            "weight_pct": int(round(weight * 100)),
            "weighted_contribution": contrib,
            "industry_benchmark": INDUSTRY_BENCHMARKS[key],
            "explanation": det_components[key]["explanation"],
            "examples": det_components[key]["examples"],
        }

    overall_score = round(max(0.0, min(100.0, weighted_sum)), 1)
    classification = classify_resume_score(overall_score)

    return {
        "overall_score": overall_score,
        "classification": classification,
        "target_role": target_role,
        "mode": mode,
        "industry_benchmark": INDUSTRY_BENCHMARKS["overall"],
        "components": components_out,
    }
