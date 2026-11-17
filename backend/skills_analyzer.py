"""Technical & soft skill extraction, role inference, and skills gap analysis."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from backend.llm_analyzer import (
    SKILLS_EXTRACTION_PROMPT,
    SKILLS_GAP_PROMPT,
    call_llm,
)
from utils.database import log_activity, save_skills_analysis

# ------------------------------------------------------------------
# CURATED SKILL TAXONOMY & INDUSTRY ROLE STANDARDS
# ------------------------------------------------------------------
SKILL_CATALOG: Dict[str, List[str]] = {
    "programming_languages": [
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Go",
        "Rust", "SQL", "R", "Kotlin", "Swift", "PHP", "Ruby", "Scala", "HTML", "CSS",
    ],
    "frameworks": [
        "React", "Angular", "Vue.js", "Next.js", "Node.js", "Express.js",
        "Django", "Flask", "FastAPI", "Spring Boot", "Streamlit", "LangChain",
        "TensorFlow", "PyTorch", "Scikit-learn", "Keras", "Pandas", "NumPy",
        "Bootstrap", "Tailwind CSS", ".NET", "Hugging Face",
    ],
    "tools": [
        "Git", "GitHub", "Docker", "Kubernetes", "AWS", "Azure", "GCP",
        "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Selenium",
        "Jenkins", "GitHub Actions", "Terraform", "Linux", "Postman", "Jira",
        "Tableau", "Power BI", "VS Code", "PyCharm", "Jupyter", "REST API", "GraphQL",
    ],
    "soft_skills": [
        "Communication", "Leadership", "Problem Solving", "Teamwork",
        "Collaboration", "Agile", "Scrum", "Time Management", "Adaptability",
        "Critical Thinking", "Presentation", "Mentoring", "Analytical Thinking",
        "Project Management", "Stakeholder Management",
    ],
    "domain_knowledge": [
        "Data Structures", "Algorithms", "Object-Oriented Programming", "OOP",
        "System Design", "Microservices", "Machine Learning", "Deep Learning",
        "Natural Language Processing", "NLP", "Computer Vision", "Generative AI",
        "LLM", "RAG", "RESTful APIs", "Database Design", "CI/CD", "Cloud Computing",
        "Unit Testing", "Cybersecurity", "Data Engineering", "ETL", "Statistics",
        "Web Scraping", "Responsive Design", "SDLC",
    ],
    "certifications": [
        "AWS Certified", "Azure Fundamentals", "Google Cloud Certified",
        "PMP", "Scrum Master", "CompTIA Security+", "CEH",
        "TensorFlow Developer", "Oracle Certified", "Microsoft Certified",
        "Coursera Specialization", "NPTEL", "Udemy",
    ],
}

ROLE_STANDARDS: Dict[str, Dict[str, Any]] = {
    "Software Developer": {
        "must_have": ["Python", "Java", "SQL", "Git", "Data Structures", "Algorithms", "REST API", "Unit Testing", "Docker"],
        "nice_to_have": ["TypeScript", "FastAPI", "React", "AWS", "CI/CD", "System Design", "Kubernetes", "PostgreSQL"],
        "keywords": ["python", "java", "c++", "git", "api", "backend", "software", "oop", "algorithms", "database"],
    },
    "Full Stack Developer": {
        "must_have": ["JavaScript", "TypeScript", "React", "Node.js", "HTML", "CSS", "SQL", "Git", "REST API"],
        "nice_to_have": ["Next.js", "Docker", "MongoDB", "PostgreSQL", "AWS", "Tailwind CSS", "CI/CD", "GraphQL"],
        "keywords": ["react", "node", "javascript", "typescript", "html", "css", "frontend", "backend", "full stack"],
    },
    "Frontend Developer": {
        "must_have": ["JavaScript", "TypeScript", "React", "HTML", "CSS", "Git", "Responsive Design", "REST API"],
        "nice_to_have": ["Next.js", "Tailwind CSS", "Vue.js", "Angular", "Unit Testing", "GraphQL", "CI/CD"],
        "keywords": ["react", "angular", "vue", "html", "css", "ui", "ux", "frontend", "javascript", "typescript"],
    },
    "Backend Engineer": {
        "must_have": ["Python", "SQL", "PostgreSQL", "REST API", "Docker", "Git", "Microservices", "Unit Testing"],
        "nice_to_have": ["FastAPI", "Django", "Redis", "Kubernetes", "AWS", "System Design", "CI/CD", "Go"],
        "keywords": ["fastapi", "django", "flask", "spring", "microservices", "database", "sql", "backend", "api"],
    },
    "Data Scientist": {
        "must_have": ["Python", "SQL", "Pandas", "NumPy", "Scikit-learn", "Machine Learning", "Statistics", "Git"],
        "nice_to_have": ["TensorFlow", "PyTorch", "Tableau", "Power BI", "NLP", "AWS", "Docker", "Jupyter"],
        "keywords": ["machine learning", "pandas", "numpy", "scikit-learn", "statistics", "modeling", "data science", "r"],
    },
    "AI/ML Engineer": {
        "must_have": ["Python", "Machine Learning", "Deep Learning", "PyTorch", "TensorFlow", "LangChain", "NLP", "Docker", "Git"],
        "nice_to_have": ["Generative AI", "RAG", "FastAPI", "Hugging Face", "AWS", "Kubernetes", "LLM", "Vector Databases"],
        "keywords": ["llm", "langchain", "pytorch", "tensorflow", "deep learning", "nlp", "ai", "rag", "hugging face"],
    },
    "Data Analyst": {
        "must_have": ["SQL", "Python", "Pandas", "Tableau", "Power BI", "Statistics", "ETL", "Communication"],
        "nice_to_have": ["R", "PostgreSQL", "AWS", "Jupyter", "Git", "Data Engineering"],
        "keywords": ["tableau", "power bi", "sql", "analytics", "dashboard", "excel", "reporting", "kpi", "etl"],
    },
    "DevOps / Cloud Engineer": {
        "must_have": ["Linux", "Docker", "Kubernetes", "AWS", "CI/CD", "Terraform", "Git", "Python"],
        "nice_to_have": ["Azure", "GCP", "Jenkins", "GitHub Actions", "Microservices", "Cybersecurity"],
        "keywords": ["docker", "kubernetes", "aws", "azure", "terraform", "ci/cd", "devops", "jenkins", "linux"],
    },
}

LEARNING_RESOURCE_LIBRARY: Dict[str, Dict[str, Any]] = {
    "Docker": {
        "why_important": "Industry standard for packaging and deploying reproducible backend and ML services.",
        "use_cases": "Containerizing APIs, local multi-service development, cloud deployments.",
        "learning_difficulty": "Beginner",
        "resources": [
            {"name": "Docker Official Get Started Guide", "platform": "Docker Docs", "url": "https://docs.docker.com/get-started/"},
            {"name": "Docker & Kubernetes Practical Course", "platform": "freeCodeCamp", "url": "https://www.freecodecamp.org/news/tag/docker/"},
        ],
    },
    "Kubernetes": {
        "why_important": "Automates container orchestration, scaling, and high-availability in production.",
        "use_cases": "Deploying microservices, auto-scaling API workloads, rolling updates.",
        "learning_difficulty": "Intermediate",
        "resources": [
            {"name": "Kubernetes Basics Tutorial", "platform": "Kubernetes.io", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/"},
        ],
    },
    "AWS": {
        "why_important": "Most widely adopted cloud platform across software, data, and AI teams.",
        "use_cases": "Hosting web apps (EC2/ECS), serverless functions (Lambda), storage (S3), managed DBs (RDS).",
        "learning_difficulty": "Intermediate",
        "resources": [
            {"name": "AWS Skill Builder Cloud Essentials", "platform": "AWS", "url": "https://explore.skillbuilder.aws/"},
        ],
    },
    "TypeScript": {
        "why_important": "Adds static type safety to JavaScript, preventing runtime bugs in large codebases.",
        "use_cases": "Production React/Next.js frontends and typed Node.js services.",
        "learning_difficulty": "Beginner",
        "resources": [
            {"name": "TypeScript Handbook", "platform": "TypeScript Docs", "url": "https://www.typescriptlang.org/docs/handbook/"},
        ],
    },
    "System Design": {
        "why_important": "Essential for mid-to-senior engineering interviews and scalable architecture.",
        "use_cases": "Designing caching layers, queues, distributed storage, and high-throughput APIs.",
        "learning_difficulty": "Advanced",
        "resources": [
            {"name": "System Design Primer", "platform": "GitHub", "url": "https://github.com/donnemartin/system-design-primer"},
        ],
    },
    "CI/CD": {
        "why_important": "Automates testing, linting, and deployments on every code change.",
        "use_cases": "GitHub Actions test pipelines, automated Docker builds, staging deployments.",
        "learning_difficulty": "Beginner",
        "resources": [
            {"name": "GitHub Actions Quickstart", "platform": "GitHub Docs", "url": "https://docs.github.com/en/actions/quickstart"},
        ],
    },
    "Unit Testing": {
        "why_important": "Demonstrates engineering rigor and prevents regressions in production code.",
        "use_cases": "Writing pytest/Jest test suites, mocking external APIs, achieving 80%+ coverage.",
        "learning_difficulty": "Beginner",
        "resources": [
            {"name": "Pytest Documentation & Guide", "platform": "pytest.org", "url": "https://docs.pytest.org/en/stable/getting-started.html"},
        ],
    },
    "FastAPI": {
        "why_important": "Modern high-performance Python API framework with automatic OpenAPI docs and typing.",
        "use_cases": "Serving ML models, building microservices, async backend APIs.",
        "learning_difficulty": "Beginner",
        "resources": [
            {"name": "FastAPI Official Tutorial", "platform": "Tiangolo Docs", "url": "https://fastapi.tiangolo.com/tutorial/"},
        ],
    },
    "PostgreSQL": {
        "why_important": "Leading relational database for scalable production workloads.",
        "use_cases": "Schema design, query indexing, transactions, JSONB semi-structured data.",
        "learning_difficulty": "Beginner",
        "resources": [
            {"name": "PostgreSQL Tutorial", "platform": "PostgreSQL.org", "url": "https://www.postgresql.org/docs/current/tutorial.html"},
        ],
    },
    "LangChain": {
        "why_important": "Core orchestration framework for building LLM applications, agents, and RAG pipelines.",
        "use_cases": "Document Q&A, structured prompt chains, tool-calling AI assistants.",
        "learning_difficulty": "Intermediate",
        "resources": [
            {"name": "LangChain Python Documentation", "platform": "LangChain", "url": "https://python.langchain.com/docs/introduction/"},
        ],
    },
    "PyTorch": {
        "why_important": "Dominant deep learning framework for research and production ML engineering.",
        "use_cases": "Fine-tuning transformers, custom neural architectures, computer vision.",
        "learning_difficulty": "Intermediate",
        "resources": [
            {"name": "Learn the Basics - PyTorch", "platform": "PyTorch.org", "url": "https://pytorch.org/tutorials/beginner/basics/intro.html"},
        ],
    },
}


def _match_skill_in_text(skill: str, text: str) -> bool:
    """Case-insensitive whole-token match supporting symbols like C++, C#, .NET."""
    escaped = re.escape(skill)
    pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    return bool(re.search(pattern, text, re.IGNORECASE))


def _extract_experience_years_per_skill(resume_text: str, all_skills: List[str]) -> Dict[str, str]:
    """Find explicit mentions like '3+ years of Python', 'Python (2 years)', or '3+ years ... Python' on the same line."""
    found: Dict[str, str] = {}
    lines = (resume_text or "").splitlines()
    for skill in all_skills:
        escaped = re.escape(skill)
        p1 = re.search(rf"(\d+\+?\s*(?:years?|yrs?))\s*(?:of\s+)?{escaped}", resume_text, re.IGNORECASE)
        p2 = re.search(rf"{escaped}\s*[\(\-:]*\s*(\d+\+?\s*(?:years?|yrs?))", resume_text, re.IGNORECASE)
        match = p1 or p2
        if match:
            found[skill] = match.group(1).strip()
            continue
        # Clause-level match within a single line/sentence (e.g., "3+ years of experience building Python, FastAPI")
        for ln in lines:
            if re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", ln, re.IGNORECASE):
                yrs = re.search(r"(\d+\+?\s*(?:years?|yrs?))\s*(?:of\s+experience)?", ln, re.IGNORECASE)
                if yrs:
                    found[skill] = yrs.group(1).strip()
                    break
    return found


def extract_skills_deterministic(resume_text: str) -> Dict[str, Any]:
    """Deterministically extract categorized skills and experience durations from resume text."""
    text = resume_text or ""
    categorized: Dict[str, List[str]] = {}
    all_detected: List[str] = []

    for category, candidates in SKILL_CATALOG.items():
        matched = [skill for skill in candidates if _match_skill_in_text(skill, text)]
        categorized[category] = matched
        all_detected.extend(matched)

    technical = list(
        dict.fromkeys(
            categorized["programming_languages"]
            + categorized["frameworks"]
            + categorized["tools"]
            + categorized["domain_knowledge"]
        )
    )
    exp_years = _extract_experience_years_per_skill(text, all_detected)

    return {
        "programming_languages": categorized["programming_languages"],
        "frameworks": categorized["frameworks"],
        "tools": categorized["tools"],
        "soft_skills": categorized["soft_skills"],
        "domain_knowledge": categorized["domain_knowledge"],
        "certifications": categorized["certifications"],
        "technical_skills": technical,
        "skill_experience_years": exp_years,
    }


def extract_resume_skills(resume_text: str, use_llm: bool = True) -> Dict[str, Any]:
    """Extract skills categorized into 6 domains, combining LLM + deterministic verification."""
    det = extract_skills_deterministic(resume_text)
    if not use_llm:
        return det

    prompt = SKILLS_EXTRACTION_PROMPT.format(resume_text=resume_text[:7000])
    resp = call_llm(prompt=prompt, expect_json=True, task_name="skills_extraction")
    if resp["success"] and isinstance(resp["data"], dict):
        ai_data = resp["data"]
        merged: Dict[str, Any] = {}
        for cat in (
            "programming_languages",
            "frameworks",
            "tools",
            "soft_skills",
            "domain_knowledge",
            "certifications",
        ):
            ai_list = [str(s).strip() for s in (ai_data.get(cat) or []) if str(s).strip()]
            combined = list(dict.fromkeys(det[cat] + ai_list))
            merged[cat] = combined

        merged["technical_skills"] = list(
            dict.fromkeys(
                merged["programming_languages"]
                + merged["frameworks"]
                + merged["tools"]
                + merged["domain_knowledge"]
            )
        )
        ai_exp = ai_data.get("skill_experience_years") or {}
        if isinstance(ai_exp, dict):
            merged["skill_experience_years"] = {**det["skill_experience_years"], **ai_exp}
        else:
            merged["skill_experience_years"] = det["skill_experience_years"]
        return merged

    return det


def infer_target_role(resume_text: str) -> str:
    """Infer the best-matching industry role from the user's resume text."""
    lower = (resume_text or "").lower()
    best_role = "Software Developer"
    best_hits = -1
    for role, info in ROLE_STANDARDS.items():
        hits = sum(1 for kw in info["keywords"] if kw in lower)
        if role.lower() in lower:
            hits += 3
        if hits > best_hits:
            best_hits = hits
            best_role = role
    return best_role


def _build_skill_recommendation(
    skill: str,
    priority: str,
    category: str,
    target_role: str,
) -> Dict[str, Any]:
    template = LEARNING_RESOURCE_LIBRARY.get(skill)
    if template:
        return {
            "skill": skill,
            "priority": priority,
            "category": category,
            "why_important": template["why_important"],
            "use_cases": template["use_cases"],
            "learning_difficulty": template["learning_difficulty"],
            "resources": template["resources"],
        }

    search_q = skill.replace(" ", "+")
    return {
        "skill": skill,
        "priority": priority,
        "category": category,
        "why_important": f"Frequently requested skill for {target_role} roles in modern engineering teams.",
        "use_cases": f"Applying {skill} in production {target_role} projects and technical interviews.",
        "learning_difficulty": "Intermediate" if priority == "High" else "Beginner",
        "resources": [
            {
                "name": f"{skill} Official Documentation & Tutorials",
                "platform": "Coursera / Official Docs",
                "url": f"https://www.coursera.org/search?query={search_q}",
            }
        ],
    }


def _skill_category_lookup(skill: str) -> str:
    for cat, items in SKILL_CATALOG.items():
        if any(item.lower() == skill.lower() for item in items):
            return cat.replace("_", " ").title()
    return "Technical"


def analyze_skills_gap_structured(
    resume_text: str,
    target_role: Optional[str] = None,
    user_id: Optional[int] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Compare extracted resume skills against target role standards and build learning roadmap."""
    inferred_role = infer_target_role(resume_text)
    role = (target_role or "").strip() or inferred_role
    extracted = extract_resume_skills(resume_text, use_llm=use_llm)

    all_present = list(
        dict.fromkeys(
            extracted["programming_languages"]
            + extracted["frameworks"]
            + extracted["tools"]
            + extracted["soft_skills"]
            + extracted["domain_knowledge"]
            + extracted["certifications"]
        )
    )
    present_lower = {s.lower() for s in all_present}

    role_spec = ROLE_STANDARDS.get(role)
    if not role_spec:
        # Match closest preset or default to Software Developer baseline
        role_spec = ROLE_STANDARDS["Software Developer"]
        for known_role, spec in ROLE_STANDARDS.items():
            if any(w in role.lower() for w in known_role.lower().split()):
                role_spec = spec
                break

    missing_critical = [s for s in role_spec["must_have"] if s.lower() not in present_lower]
    missing_nice = [s for s in role_spec["nice_to_have"] if s.lower() not in present_lower]

    recommendations: List[Dict[str, Any]] = []
    mode = "demo"

    if use_llm:
        prompt = SKILLS_GAP_PROMPT.format(
            target_role=role,
            extracted_skills=json.dumps(extracted),
            resume_text=resume_text[:4000],
        )
        llm_resp = call_llm(prompt=prompt, expect_json=True, task_name="skills_gap")
        if llm_resp["success"] and isinstance(llm_resp["data"], dict):
            mode = "live"
            ai_data = llm_resp["data"]
            ai_crit = [str(s).strip() for s in (ai_data.get("missing_critical_skills") or []) if str(s).strip()]
            ai_nice = [str(s).strip() for s in (ai_data.get("missing_nice_to_have_skills") or []) if str(s).strip()]
            if ai_crit:
                missing_critical = [s for s in ai_crit if s.lower() not in present_lower][:8]
            if ai_nice:
                missing_nice = [s for s in ai_nice if s.lower() not in present_lower][:8]
            ai_recs = ai_data.get("recommendations") or []
            if isinstance(ai_recs, list) and ai_recs:
                for item in ai_recs[:10]:
                    if isinstance(item, dict) and item.get("skill"):
                        recommendations.append(
                            {
                                "skill": str(item["skill"]),
                                "priority": str(item.get("priority") or "High"),
                                "category": str(item.get("category") or _skill_category_lookup(str(item["skill"]))),
                                "why_important": str(item.get("why_important") or ""),
                                "use_cases": str(item.get("use_cases") or ""),
                                "learning_difficulty": str(item.get("learning_difficulty") or "Intermediate"),
                                "resources": item.get("resources")
                                if isinstance(item.get("resources"), list)
                                else [],
                            }
                        )

    if not recommendations:
        for s in missing_critical:
            recommendations.append(_build_skill_recommendation(s, "High", _skill_category_lookup(s), role))
        for s in missing_nice:
            if len(recommendations) >= 10:
                break
            recommendations.append(_build_skill_recommendation(s, "Medium", _skill_category_lookup(s), role))

    # Ensure at least 5 recommendations when resume is mostly complete by suggesting advanced growth skills
    growth_candidates = ["System Design", "Kubernetes", "AWS", "CI/CD", "LangChain", "FastAPI", "Unit Testing"]
    for gc in growth_candidates:
        if len(recommendations) >= 5:
            break
        if gc.lower() not in {r["skill"].lower() for r in recommendations} and gc.lower() not in present_lower:
            recommendations.append(_build_skill_recommendation(gc, "Medium", _skill_category_lookup(gc), role))

    total_expected = max(1, len(role_spec["must_have"]) + len(role_spec["nice_to_have"]))
    matched_expected = total_expected - (
        len([s for s in role_spec["must_have"] if s.lower() not in present_lower])
        + len([s for s in role_spec["nice_to_have"] if s.lower() not in present_lower])
    )
    coverage_pct = round(max(0.0, min(100.0, (matched_expected / total_expected) * 100.0)), 1)

    chart_data = {
        "present_count": len(all_present),
        "missing_critical_count": len(missing_critical),
        "missing_nice_count": len(missing_nice),
        "coverage_percentage": coverage_pct,
        "category_distribution": {
            "Programming Languages": len(extracted["programming_languages"]),
            "Frameworks": len(extracted["frameworks"]),
            "Tools & Platforms": len(extracted["tools"]),
            "Soft Skills": len(extracted["soft_skills"]),
            "Domain Knowledge": len(extracted["domain_knowledge"]),
            "Certifications": len(extracted["certifications"]),
        },
    }

    result = {
        "target_role": role,
        "inferred_role": inferred_role,
        "mode": mode,
        "extracted_skills": extracted,
        "existing_skills": all_present,
        "missing_critical_skills": missing_critical,
        "missing_nice_to_have_skills": missing_nice,
        "recommended_skills": [r["skill"] for r in recommendations],
        "recommendations": recommendations[:10],
        "chart_data": chart_data,
    }

    if user_id is not None:
        save_skills_analysis(
            user_id=user_id,
            target_role=role,
            extracted_skills=extracted,
            missing_critical=missing_critical,
            missing_nice=missing_nice,
            recommendations=result["recommendations"],
            coverage_pct=coverage_pct,
        )
        log_activity(
            user_id,
            "Skills Gap Analyzed",
            f"Completed skills gap analysis for {role} ({coverage_pct}% role coverage).",
        )

    return result
