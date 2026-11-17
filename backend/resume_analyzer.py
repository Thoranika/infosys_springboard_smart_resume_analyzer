"""Resume strengths & weaknesses analyzer and full Milestone 2 analysis orchestrator."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from backend.llm_analyzer import STRENGTHS_PROMPT, WEAKNESSES_PROMPT, call_llm
from backend.resume_parser import detect_resume_sections
from backend.resume_scorer import ACTION_VERBS, calculate_resume_score
from backend.skills_analyzer import (
    analyze_skills_gap_structured,
    extract_skills_deterministic,
    infer_target_role,
)
from utils.database import (
    get_cached_resume_analysis,
    log_activity,
    save_resume_analysis,
    save_strengths_result,
)
from utils.security import compute_content_hash


def _analyze_strengths_deterministic(
    resume_text: str, target_role: str
) -> List[Dict[str, Any]]:
    text = resume_text or ""
    lower = text.lower()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sections = detect_resume_sections(text)
    skills = extract_skills_deterministic(text)
    strengths: List[Dict[str, Any]] = []

    # 1. Technical skills breadth
    if skills["technical_skills"]:
        sample = ", ".join(skills["technical_skills"][:6])
        strengths.append(
            {
                "title": "Relevant Technical Stack",
                "description": f"Demonstrates {len(skills['technical_skills'])} technical skills aligned with {target_role}.",
                "category": "Skills",
                "evidence": f"Detected skills: {sample}",
                "confidence": 92,
            }
        )

    # 2. Quantifiable achievements
    metrics = [
        ln
        for ln in lines
        if re.search(r"\b\d+(?:\.\d+)?%|\$\d+|\b\d+\+?\s*(?:users|projects|clients|ms|x)\b", ln.lower())
    ]
    if metrics:
        strengths.append(
            {
                "title": "Quantifiable Achievements",
                "description": "Includes measurable impact and numeric outcomes that validate performance.",
                "category": "Content",
                "evidence": metrics[0][:150],
                "confidence": 89,
            }
        )

    # 3. Action verbs
    verb_lines = [
        ln for ln in lines if any(re.search(rf"\b{v}\b", ln.lower()) for v in ACTION_VERBS)
    ]
    if verb_lines:
        strengths.append(
            {
                "title": "Strong Action-Oriented Phrasing",
                "description": "Uses active engineering and leadership verbs to describe contributions.",
                "category": "Content",
                "evidence": verb_lines[0][:150],
                "confidence": 86,
            }
        )

    # 4. Education background
    if sections["education"]:
        edu_line = next(
            (ln for ln in lines if re.search(r"\b(bachelor|master|b\.?tech|m\.?tech|university|college|degree|gpa)\b", ln.lower())),
            "Education section included",
        )
        strengths.append(
            {
                "title": "Solid Educational Foundation",
                "description": "Clearly presents academic credentials relevant to technical roles.",
                "category": "Education",
                "evidence": edu_line[:150],
                "confidence": 90,
            }
        )

    # 5. Clear section formatting
    present_sections = [k.title() for k, v in sections.items() if v]
    if len(present_sections) >= 4:
        strengths.append(
            {
                "title": "Well-Structured Resume Layout",
                "description": f"Organizes content into clear sections ({', '.join(present_sections[:5])}).",
                "category": "Formatting",
                "evidence": f"{len(present_sections)} standard resume sections identified",
                "confidence": 88,
            }
        )

    # 6. Certifications or Projects
    if sections["certifications"]:
        cert_line = next(
            (ln for ln in lines if re.search(r"\b(certif|aws|azure|coursera|nptel|udemy|license)\b", ln.lower())),
            "Certifications listed",
        )
        strengths.append(
            {
                "title": "Verified Certifications & Continuous Learning",
                "description": "Includes industry certifications or specialized coursework.",
                "category": "Certifications",
                "evidence": cert_line[:150],
                "confidence": 85,
            }
        )
    elif sections["projects"]:
        strengths.append(
            {
                "title": "Hands-On Project Portfolio",
                "description": "Showcases applied project work demonstrating practical implementation skills.",
                "category": "Experience",
                "evidence": "Projects section present in resume",
                "confidence": 84,
            }
        )

    # 7. Contact accessibility / Soft skills
    if skills["soft_skills"]:
        strengths.append(
            {
                "title": "Cross-Functional Soft Skills",
                "description": "Highlights interpersonal and collaborative competencies.",
                "category": "Skills",
                "evidence": ", ".join(skills["soft_skills"][:5]),
                "confidence": 82,
            }
        )

    # Guarantee 5-7 items
    fallback_extras = [
        {
            "title": "Readable Resume Length",
            "description": f"Contains {len(text.split())} words, making it scannable for recruiters.",
            "category": "Formatting",
            "evidence": f"{len(lines)} structured lines extracted",
            "confidence": 78,
        },
        {
            "title": "Focused Career Domain",
            "description": f"Resume vocabulary aligns consistently with {target_role} expectations.",
            "category": "Experience",
            "evidence": f"Inferred primary track: {target_role}",
            "confidence": 80,
        },
    ]
    for extra in fallback_extras:
        if len(strengths) >= 5:
            break
        strengths.append(extra)

    return strengths[:7]


def _analyze_weaknesses_deterministic(
    resume_text: str, target_role: str
) -> List[Dict[str, Any]]:
    text = resume_text or ""
    lower = text.lower()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sections = detect_resume_sections(text)
    gap = analyze_skills_gap_structured(text, target_role=target_role, use_llm=False)

    weaknesses: List[Dict[str, Any]] = []

    # 1. Contact information check
    has_email = bool(re.search(r"[\w\.\+\-]+@[\w\-]+\.[\w\.\-]+", text))
    has_linkedin = "linkedin.com" in lower or "github.com" in lower
    if not has_email or not has_linkedin:
        missing_items = []
        if not has_email:
            missing_items.append("email address")
        if not has_linkedin:
            missing_items.append("LinkedIn/GitHub profile link")
        weaknesses.append(
            {
                "title": "Incomplete Contact or Portfolio Links",
                "description": f"Missing {' and '.join(missing_items)} in the header.",
                "category": "Content",
                "severity": "critical" if not has_email else "moderate",
                "location": "Header / Contact Section",
                "evidence": lines[0][:120] if lines else "Header missing links",
                "confidence": 94,
            }
        )

    # 2. Missing summary section
    if not sections["summary"]:
        weaknesses.append(
            {
                "title": "Missing Professional Summary",
                "description": f"No targeted summary or objective statement introducing your {target_role} value proposition.",
                "category": "Formatting",
                "severity": "moderate",
                "location": "Top of Resume",
                "evidence": "No Summary / Objective header found",
                "confidence": 88,
            }
        )

    # 3. Quantifiable metrics check
    metric_lines = [
        ln for ln in lines if re.search(r"\b\d+(?:\.\d+)?%|\$\d+|\b\d+\+?\s*(?:users|clients|ms|x)\b", ln.lower())
    ]
    if len(metric_lines) < 2:
        sample_weak_line = next(
            (ln for ln in lines if len(ln.split()) >= 6 and not re.search(r"\d", ln)),
            "Experience/Project bullets lack numeric metrics",
        )
        weaknesses.append(
            {
                "title": "Limited Quantifiable Achievements",
                "description": "Several bullet points describe duties rather than measurable business or technical results (%, $, latency, scale).",
                "category": "Content",
                "severity": "critical" if len(metric_lines) == 0 else "moderate",
                "location": "Experience / Projects Section",
                "evidence": sample_weak_line[:140],
                "confidence": 91,
            }
        )

    # 4. Passive phrasing / weak bullet openings
    weak_openers = [
        ln for ln in lines
        if re.search(r"\b(responsible for|worked on|helped with|assisted in|duties included)\b", ln.lower())
    ]
    if weak_openers:
        weaknesses.append(
            {
                "title": "Passive Phrasing in Bullet Points",
                "description": "Phrases like 'worked on' or 'responsible for' dilute ownership compared to strong action verbs.",
                "category": "Content",
                "severity": "moderate",
                "location": "Experience / Projects",
                "evidence": weak_openers[0][:140],
                "confidence": 89,
            }
        )

    # 5. Missing critical role skills
    if gap["missing_critical_skills"]:
        missing_str = ", ".join(gap["missing_critical_skills"][:5])
        weaknesses.append(
            {
                "title": f"Missing Key Skills for {target_role}",
                "description": f"Resume does not mention core industry keywords expected for {target_role}: {missing_str}.",
                "category": "Skills",
                "severity": "critical" if len(gap["missing_critical_skills"]) >= 4 else "moderate",
                "location": "Skills & Experience Sections",
                "evidence": f"Missing must-have skills: {missing_str}",
                "confidence": 90,
            }
        )

    # 6. Length or bullet formatting check
    word_count = len(text.split())
    bullet_lines = [ln for ln in lines if ln.startswith(("-", "•", "*", "▪"))]
    if word_count < 200 or len(bullet_lines) < 3:
        weaknesses.append(
            {
                "title": "Sparse Detail or Inconsistent Bullet Formatting",
                "description": "Resume content is brief or lacks structured bullet points, reducing ATS readability.",
                "category": "Formatting",
                "severity": "moderate",
                "location": "Document Body",
                "evidence": f"Word count: {word_count}; formatted bullet lines: {len(bullet_lines)}",
                "confidence": 85,
            }
        )

    # 7. Missing certifications / continuous learning or soft skills
    if not sections["certifications"]:
        weaknesses.append(
            {
                "title": "No Dedicated Certifications or Achievements Section",
                "description": "Adding relevant certifications or notable awards strengthens credibility for technical screening.",
                "category": "Experience",
                "severity": "minor",
                "location": "Lower Resume Section",
                "evidence": "Certifications / Awards section not detected",
                "confidence": 81,
            }
        )

    supplementary_checks = [
        {
            "title": "Nice-to-Have Cloud & Architecture Keywords",
            "description": (
                f"Adding experience or projects with {', '.join((gap.get('missing_nice_to_have_skills') or ['Kubernetes', 'System Design'])[:3])} "
                f"would strengthen competitiveness for senior {target_role} roles."
            ),
            "category": "Skills",
            "severity": "minor",
            "location": "Skills & Projects",
            "evidence": f"Missing nice-to-have skills: {', '.join((gap.get('missing_nice_to_have_skills') or ['None'])[:3])}",
            "confidence": 80,
        },
        {
            "title": "Skills Categorization & Proficiency Clarity",
            "description": "Explicitly indicate proficiency or years used per core technology to assist technical screeners.",
            "category": "Formatting",
            "severity": "minor",
            "location": "Skills Section",
            "evidence": f"{len(gap['existing_skills'])} total skills extracted; clarify depth per category",
            "confidence": 79,
        },
        {
            "title": "Tailoring Keywords to Specific Job Descriptions",
            "description": f"Mirror exact terminology and business outcomes expected for {target_role} postings.",
            "category": "Skills",
            "severity": "minor",
            "location": "Summary & Experience",
            "evidence": f"Evaluated against {target_role} industry benchmark",
            "confidence": 78,
        },
        {
            "title": "Expand Business Impact & Scale Context",
            "description": "Where technical achievements are listed, pair latency/efficiency gains with user or revenue impact.",
            "category": "Content",
            "severity": "minor",
            "location": "Experience Bullets",
            "evidence": f"Analyzed {len(lines)} lines across {word_count} words",
            "confidence": 76,
        },
        {
            "title": "Add Live Project Links or Architecture Notes",
            "description": "Include direct repository or live deployment links next to flagship projects to validate execution.",
            "category": "Experience",
            "severity": "minor",
            "location": "Projects Section",
            "evidence": "Include direct demo/repo URLs per featured project",
            "confidence": 75,
        },
    ]

    for extra in supplementary_checks:
        if len(weaknesses) >= 5:
            break
        weaknesses.append(extra)

    return weaknesses[:7]


def analyze_strengths_and_weaknesses(
    resume_text: str,
    target_role: Optional[str] = None,
    user_id: Optional[int] = None,
    force_refresh: bool = False,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Identify 5-7 strengths and 5-7 weaknesses with evidence, severity, and confidence."""
    role = (target_role or "").strip() or infer_target_role(resume_text)
    content_hash = compute_content_hash(resume_text, role)

    if user_id is not None and not force_refresh:
        cached = get_cached_resume_analysis(user_id, content_hash)
        if cached and cached.get("strengths") and cached.get("weaknesses"):
            try:
                return {
                    "strengths": json.loads(cached["strengths"]),
                    "weaknesses": json.loads(cached["weaknesses"]),
                    "target_role": role,
                    "mode": "cached",
                    "content_hash": content_hash,
                }
            except Exception:
                pass

    strengths: List[Dict[str, Any]] = []
    weaknesses: List[Dict[str, Any]] = []
    mode = "demo"

    if use_llm:
        s_prompt = STRENGTHS_PROMPT.format(target_role=role, resume_text=resume_text[:7000])
        w_prompt = WEAKNESSES_PROMPT.format(target_role=role, resume_text=resume_text[:7000])

        s_resp = call_llm(prompt=s_prompt, expect_json=True, task_name="strengths_analysis")
        w_resp = call_llm(prompt=w_prompt, expect_json=True, task_name="weaknesses_analysis")

        if s_resp["success"] and isinstance(s_resp["data"], dict):
            raw_s = s_resp["data"].get("strengths") or []
            if isinstance(raw_s, list) and raw_s:
                mode = "live"
                for item in raw_s[:7]:
                    if isinstance(item, dict):
                        strengths.append(
                            {
                                "title": str(item.get("title") or "Key Strength"),
                                "description": str(item.get("description") or ""),
                                "category": str(item.get("category") or "Content"),
                                "evidence": str(item.get("evidence") or "Found in resume"),
                                "confidence": max(0, min(100, int(item.get("confidence") or 85))),
                            }
                        )

        if w_resp["success"] and isinstance(w_resp["data"], dict):
            raw_w = w_resp["data"].get("weaknesses") or []
            if isinstance(raw_w, list) and raw_w:
                mode = "live"
                for item in raw_w[:7]:
                    if isinstance(item, dict):
                        sev = str(item.get("severity") or "moderate").lower()
                        if sev not in {"minor", "moderate", "critical"}:
                            sev = "moderate"
                        weaknesses.append(
                            {
                                "title": str(item.get("title") or "Area for Improvement"),
                                "description": str(item.get("description") or ""),
                                "category": str(item.get("category") or "Content"),
                                "severity": sev,
                                "location": str(item.get("location") or "Resume body"),
                                "evidence": str(item.get("evidence") or ""),
                                "confidence": max(0, min(100, int(item.get("confidence") or 85))),
                            }
                        )

    if len(strengths) < 5:
        strengths = _analyze_strengths_deterministic(resume_text, role)
    if len(weaknesses) < 5:
        weaknesses = _analyze_weaknesses_deterministic(resume_text, role)

    return {
        "strengths": strengths[:7],
        "weaknesses": weaknesses[:7],
        "target_role": role,
        "mode": mode,
        "content_hash": content_hash,
    }


def run_full_resume_analysis(
    user_id: int,
    resume_text: str,
    target_role: Optional[str] = None,
    force_refresh: bool = False,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Run complete Milestone 2 pipeline (scoring, strengths/weaknesses, skills gap) with DB caching."""
    role = (target_role or "").strip() or infer_target_role(resume_text)
    content_hash = compute_content_hash(resume_text, role)

    if not force_refresh:
        cached = get_cached_resume_analysis(user_id, content_hash)
        if cached and cached.get("analysis_json"):
            try:
                payload = json.loads(cached["analysis_json"])
                if (
                    isinstance(payload, dict)
                    and payload.get("score_data")
                    and payload.get("strengths")
                    and payload.get("skills_gap")
                ):
                    payload["analysis_id"] = cached["id"]
                    payload["analyzed_at"] = cached["analyzed_at"]
                    payload["from_cache"] = True
                    return payload
            except Exception:
                pass

    skills_gap = analyze_skills_gap_structured(
        resume_text, target_role=role, user_id=user_id, use_llm=use_llm
    )
    score_data = calculate_resume_score(
        resume_text,
        target_role=role,
        extracted_skills=skills_gap["extracted_skills"],
        use_llm=use_llm,
    )
    sw_data = analyze_strengths_and_weaknesses(
        resume_text,
        target_role=role,
        user_id=None,
        force_refresh=True,
        use_llm=use_llm,
    )

    mode = "live" if any(m == "live" for m in (skills_gap["mode"], score_data["mode"], sw_data["mode"])) else "demo"
    full_payload = {
        "target_role": role,
        "mode": mode,
        "from_cache": False,
        "overall_score": score_data["overall_score"],
        "classification": score_data["classification"],
        "score_data": score_data,
        "strengths": sw_data["strengths"],
        "weaknesses": sw_data["weaknesses"],
        "skills_gap": skills_gap,
        "content_hash": content_hash,
    }

    analysis_id = save_resume_analysis(
        user_id=user_id,
        resume_text=resume_text,
        analysis_json=json.dumps(full_payload),
        analysis_scores=json.dumps(score_data),
        strengths=json.dumps(sw_data["strengths"]),
        weaknesses=json.dumps(sw_data["weaknesses"]),
        identified_skills=json.dumps(skills_gap["extracted_skills"]),
        recommended_skills=json.dumps(skills_gap["recommendations"]),
        overall_score=score_data["overall_score"],
        classification=score_data["classification"],
        target_role=role,
        content_hash=content_hash,
    )
    save_strengths_result(user_id, json.dumps(sw_data["strengths"]))
    log_activity(
        user_id,
        "Resume Analyzed",
        f"Score {score_data['overall_score']}/100 ({score_data['classification']}) for {role}.",
    )

    full_payload["analysis_id"] = analysis_id
    return full_payload
