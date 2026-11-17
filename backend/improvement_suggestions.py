"""Personalized resume improvement suggestions generator (Milestone 2 Task 13)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.llm_analyzer import IMPROVEMENT_PROMPT, call_llm
from backend.resume_analyzer import analyze_strengths_and_weaknesses
from backend.skills_analyzer import analyze_skills_gap_structured, infer_target_role
from utils.database import (
    get_latest_improvement_suggestions,
    log_activity,
    save_improvement_suggestions,
    update_improvement_status_map,
)


def _extract_candidate_bullets(resume_text: str) -> List[str]:
    """Find actual experience/project lines from the user's resume for before/after rewriting."""
    lines = [ln.strip() for ln in (resume_text or "").splitlines() if ln.strip()]
    bullets = []
    for ln in lines:
        cleaned = ln.lstrip("-•*▪– ").strip()
        words = cleaned.split()
        if 5 <= len(words) <= 28 and not re.search(r"@|http|linkedin|github|\+\d", cleaned.lower()):
            bullets.append(cleaned)
    return bullets


def _rewrite_bullet_deterministic(original: str, target_role: str) -> Dict[str, str]:
    """Produce a concrete improved statement preserving context while adding action verbs & metrics."""
    lower = original.lower()
    if re.search(r"^(worked on|helped with|assisted in|responsible for)\b", lower):
        core = re.sub(
            r"^(worked on|helped with|assisted in|responsible for)\s+",
            "",
            original,
            flags=re.IGNORECASE,
        ).strip()
        improved = f"Engineered and delivered {core}, improving system throughput by [X]% and reducing manual effort by [Y] hours/week."
        expl = "Replaces passive phrasing ('worked on' / 'responsible for') with a strong ownership verb and measurable outcome."
    elif not re.search(r"\d", original):
        improved = f"Architected and implemented {original[0].lower() + original[1:] if len(original) > 1 else original}, achieving [X]% faster execution for [N]+ users."
        expl = "Adds an active technical verb and concrete quantifiable impact placeholders so recruiters can immediately see scale."
    else:
        improved = f"Spearheaded {original[0].lower() + original[1:] if len(original) > 1 else original} — documented architecture and automated test coverage to ensure 99.9% reliability."
        expl = "Elevates leadership framing and highlights engineering quality and reliability outcomes."

    return {
        "section": "Experience / Projects",
        "original": original,
        "improved": improved,
        "explanation": expl,
    }


def _build_weakness_actions(weaknesses: List[Dict[str, Any]], target_role: str) -> List[Dict[str, Any]]:
    actions_list: List[Dict[str, Any]] = []
    for idx, w in enumerate(weaknesses, start=1):
        title = w.get("title") or f"Weakness #{idx}"
        category = (w.get("category") or "Content").lower()
        if "contact" in title.lower():
            items = [
                "Place full name, professional email, phone number, city/state, and LinkedIn URL in a clean single-line header.",
                "Add a clickable GitHub or portfolio link showcasing live projects.",
            ]
        elif "summary" in title.lower():
            items = [
                f"Write a 2–3 sentence Professional Summary tailored to {target_role} highlighting years of experience and top 3 tools.",
                "Include one flagship measurable achievement in your opening summary.",
            ]
        elif "quantifiable" in title.lower() or "metric" in title.lower():
            items = [
                "Audit each experience/project bullet and attach at least one metric (%, $, latency, users served, or dataset size).",
                "Use the Google XYZ formula: 'Accomplished [X] as measured by [Y], by doing [Z]'.",
            ]
        elif "passive" in title.lower() or "verb" in title.lower():
            items = [
                "Replace passive openers ('worked on', 'responsible for') with strong action verbs (Engineered, Automated, Led, Optimized).",
                "Start every bullet point with a past-tense action verb (or present-tense for current role).",
            ]
        elif "skill" in category:
            items = [
                f"Review missing must-have skills for {target_role} and integrate authentic hands-on technologies you know into a categorized Skills block.",
                "Build a focused mini-project using 1–2 missing critical skills and add it to your Projects section.",
            ]
        else:
            items = [
                "Standardize bullet punctuation, tense consistency, and 10–11pt readable typography.",
                "Group technical skills under clear labels (Languages, Frameworks, Tools, Cloud/Databases).",
                "Eliminate redundant filler phrases so each bullet fits cleanly in 1–2 lines.",
            ]
        actions_list.append(
            {
                "weakness_title": title,
                "severity": w.get("severity") or "moderate",
                "actions": items[:3],
            }
        )
    return actions_list


def generate_improvement_suggestions(
    resume_text: str,
    weaknesses: Optional[List[Dict[str, Any]]] = None,
    skills_gap: Optional[Dict[str, Any]] = None,
    score_data: Optional[Dict[str, Any]] = None,
    target_role: Optional[str] = None,
    user_id: Optional[int] = None,
    analysis_id: Optional[int] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Generate prioritized, section-wise, and before/after resume improvement suggestions."""
    role = (target_role or "").strip() or infer_target_role(resume_text)
    if weaknesses is None:
        sw = analyze_strengths_and_weaknesses(resume_text, target_role=role, use_llm=False)
        weaknesses = sw["weaknesses"]
    if skills_gap is None:
        skills_gap = analyze_skills_gap_structured(resume_text, target_role=role, use_llm=False)

    weakness_actions = _build_weakness_actions(weaknesses, role)
    candidate_bullets = _extract_candidate_bullets(resume_text)
    if candidate_bullets:
        before_after = [
            _rewrite_bullet_deterministic(b, role) for b in candidate_bullets[:3]
        ]
    else:
        before_after = [
            {
                "section": "Experience / Projects",
                "original": "Worked on a web application using Python and SQL for managing user tasks.",
                "improved": "Engineered a full-stack Python & SQL web application supporting 500+ active users, cutting task lookup latency by 40%.",
                "explanation": "Replaces generic wording with specific scale, technology impact, and quantifiable performance gain.",
            },
            {
                "section": "Summary",
                "original": "Looking for a challenging software role to utilize my skills.",
                "improved": f"{role} specializing in Python, API architecture, and automated testing, with hands-on delivery of scalable cloud applications.",
                "explanation": "Replaces a vague objective with a role-targeted, value-driven summary.",
            },
        ]

    missing_crit = skills_gap.get("missing_critical_skills") or []
    section_recs = {
        "Professional Summary": [
            f"Lead with a 3-line tailored summary targeting {role} roles.",
            "Highlight your strongest technical stack and top quantified achievement upfront.",
        ],
        "Experience": [
            "Follow Action Verb + Task + Measurable Result in every bullet point.",
            "Emphasize production ownership, API/system metrics, and cross-team collaboration.",
        ],
        "Skills": [
            "Organize skills into explicit rows: Programming Languages, Frameworks, Tools & Cloud, Databases.",
            f"Incorporate missing priority keywords once proficient: {', '.join(missing_crit[:4]) or 'Docker, CI/CD, Testing'}.",
        ],
        "Education": [
            "Include degree name, institution, graduation year, and GPA (if >= 3.3/4.0 or 7.5/10).",
            "List 3–5 relevant upper-level courses (e.g., Algorithms, Databases, Machine Learning).",
        ],
        "Formatting": [
            "Maintain consistent margins, bold job titles, aligned dates, and single-column ATS-safe formatting.",
            "Keep total length to 1 page (entry/mid-level) or 2 pages (senior).",
        ],
        "Achievements": [
            "Add a dedicated Awards, Hackathons, or Certifications section with dates and issuing organizations.",
            "Quantify rankings or outcomes (e.g., 'Top 5% out of 300 teams', 'Reduced bug rate by 30%').",
        ],
    }

    high_impact = [
        {
            "id": "hi_1",
            "title": "Quantify Project & Work Outcomes",
            "category": "Content Quality",
            "priority": "High Impact",
            "estimated_score_gain": "+6.5 pts",
            "action_steps": [
                "Add numeric metrics (%, $, latency, user count) to at least 4 experience/project bullets.",
                "Include before-and-after performance improvements where applicable.",
            ],
        },
        {
            "id": "hi_2",
            "title": f"Bridge Critical Skill Keywords for {role}",
            "category": "Keyword Relevance",
            "priority": "High Impact",
            "estimated_score_gain": "+5.0 pts",
            "action_steps": [
                f"Add verifiable projects or experience covering: {', '.join(missing_crit[:4]) or 'Testing, Docker, REST APIs'}.",
                "Mirror terminology used in target job descriptions naturally across Experience and Skills.",
            ],
        },
        {
            "id": "hi_3",
            "title": "Strengthen Action Verbs & Ownership",
            "category": "Content Quality",
            "priority": "High Impact",
            "estimated_score_gain": "+4.0 pts",
            "action_steps": [
                "Eliminate 'Worked on' and 'Responsible for' across all bullets.",
                "Begin every statement with high-impact verbs (Architected, Engineered, Automated, Scaled).",
            ],
        },
    ]

    quick_wins = [
        {
            "id": "qw_1",
            "title": "Add Targeted 3-Line Professional Summary",
            "category": "Completeness",
            "priority": "Quick Win",
            "estimated_score_gain": "+3.5 pts",
            "action_steps": [
                f"Place a concise summary directly under your header tailored to {role}.",
            ],
        },
        {
            "id": "qw_2",
            "title": "Categorize Technical Skills Section",
            "category": "Formatting",
            "priority": "Quick Win",
            "estimated_score_gain": "+2.5 pts",
            "action_steps": [
                "Group skills into Languages, Frameworks, Tools, and Databases for instant recruiter scanning.",
            ],
        },
        {
            "id": "qw_3",
            "title": "Verify Header Links & Contact Info",
            "category": "Completeness",
            "priority": "Quick Win",
            "estimated_score_gain": "+2.0 pts",
            "action_steps": [
                "Include clickable LinkedIn, GitHub, email, and phone number in the top header.",
            ],
        },
    ]

    mode = "demo"
    if use_llm:
        prompt = IMPROVEMENT_PROMPT.format(
            target_role=role,
            weaknesses=str([w.get("title") for w in weaknesses]),
            resume_text=(resume_text or "")[:6000],
        )
        llm_resp = call_llm(prompt=prompt, expect_json=True, task_name="improvement_suggestions")
        if llm_resp["success"] and isinstance(llm_resp["data"], dict):
            mode = "live"
            ai = llm_resp["data"]
            if isinstance(ai.get("weakness_actions"), list) and ai["weakness_actions"]:
                weakness_actions = ai["weakness_actions"]
            if isinstance(ai.get("before_after_examples"), list) and ai["before_after_examples"]:
                before_after = ai["before_after_examples"]
            if isinstance(ai.get("section_recommendations"), dict) and ai["section_recommendations"]:
                section_recs.update(ai["section_recommendations"])
            if isinstance(ai.get("high_impact"), list) and ai["high_impact"]:
                high_impact = ai["high_impact"]
            if isinstance(ai.get("quick_wins"), list) and ai["quick_wins"]:
                quick_wins = ai["quick_wins"]

    learning_resources = {
        "skill_resources": [
            {
                "skill": rec["skill"],
                "resources": rec.get("resources") or [],
            }
            for rec in (skills_gap.get("recommendations") or [])[:5]
        ],
        "formatting_guides": [
            {
                "title": "Harvard OCS Resume & Action Verb Guide",
                "url": "https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/",
            },
            {
                "title": "Jake's ATS-Friendly LaTeX Resume Template",
                "url": "https://www.overleaf.com/latex/templates/jakes-resume/syzfjbzwjncs",
            },
            {
                "title": "Tech Interview Handbook - Resume Preparation",
                "url": "https://www.techinterviewhandbook.org/resume/",
            },
        ],
    }

    plan = {
        "target_role": role,
        "mode": mode,
        "weakness_actions": weakness_actions,
        "before_after_examples": before_after,
        "section_recommendations": section_recs,
        "high_impact": high_impact,
        "quick_wins": quick_wins,
        "learning_resources": learning_resources,
        "estimated_total_potential_gain": "+15 to +23 pts",
    }

    if user_id is not None:
        suggestion_id = save_improvement_suggestions(
            user_id=user_id,
            suggestions=plan,
            analysis_id=analysis_id,
            status_map={},
        )
        plan["suggestion_id"] = suggestion_id
        plan["status_map"] = {}
        log_activity(user_id, "Improvements Generated", f"Generated personalized improvement plan for {role}.")

    return plan


def update_improvement_item_status(
    user_id: int, item_id: str, status: str
) -> Dict[str, str]:
    """Persist 'Applied' / 'Not Relevant' / 'Pending' status for a suggestion item."""
    latest = get_latest_improvement_suggestions(user_id)
    if not latest:
        return {}
    status_map = dict(latest.get("status_map") or {})
    status_map[item_id] = status
    update_improvement_status_map(latest["id"], status_map)
    return status_map
