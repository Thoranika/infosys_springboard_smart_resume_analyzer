"""Multi-provider LLM integration with LangChain prompt templates, retries, JSON parsing, and cost tracking."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from utils.logger import get_logger, log_api_call

load_dotenv()

logger = get_logger("llm_analyzer")

MAX_CHARS = 7500

# ------------------------------------------------------------------
# PLACEHOLDER / KEY VALIDATION
# ------------------------------------------------------------------
_PLACEHOLDER_PREFIXES = (
    "your_",
    "sk-...",
    "sk-xxx",
    "placeholder",
    "test",
    "demo",
    "changeme",
)


def _is_real_key(key: Optional[str]) -> bool:
    cleaned = (key or "").strip()
    if len(cleaned) < 20:
        return False
    lower = cleaned.lower()
    if any(lower.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES):
        return False
    if "..." in cleaned:
        return False
    return True


def get_llm_config() -> Dict[str, Any]:
    """Return active LLM configuration without exposing secret key values."""
    load_dotenv(override=False)
    preferred = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    gemini_key = os.getenv("GEMINI_API_KEY") or ""
    openai_key = os.getenv("OPENAI_API_KEY") or ""
    ollama_url = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    model = (os.getenv("LLM_MODEL") or "gemini-2.5-flash").strip()

    has_gemini = _is_real_key(gemini_key)
    has_openai = _is_real_key(openai_key)

    active_provider = "demo"
    if preferred == "gemini" and has_gemini:
        active_provider = "gemini"
    elif preferred == "openai" and has_openai:
        active_provider = "openai"
    elif preferred == "ollama" and ollama_url:
        active_provider = "ollama"
    elif has_gemini:
        active_provider = "gemini"
    elif has_openai:
        active_provider = "openai"

    return {
        "preferred_provider": preferred,
        "active_provider": active_provider,
        "model": model,
        "has_gemini_key": has_gemini,
        "has_openai_key": has_openai,
        "ollama_url": ollama_url,
        "is_live": active_provider in {"gemini", "openai", "ollama"},
    }


def is_live_llm_available() -> bool:
    """True when valid non-placeholder API credentials or Ollama are configured."""
    return bool(get_llm_config()["is_live"])


# ------------------------------------------------------------------
# TOKEN USAGE & COST TRACKING
# ------------------------------------------------------------------
TOKEN_USAGE_STATS: Dict[str, Any] = {
    "total_calls": 0,
    "live_calls": 0,
    "failed_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "estimated_cost_usd": 0.0,
}

# Approximate blended cost per 1M tokens (USD)
_COST_PER_1M_TOKENS = {
    "gemini": 0.35,
    "openai": 1.50,
    "ollama": 0.0,
    "demo": 0.0,
}


def estimate_tokens(text: str) -> int:
    """Roughly estimate token count (~4 characters per token)."""
    return max(1, len(text or "") // 4)


def _record_usage(provider: str, prompt_text: str, output_text: str, live: bool = True) -> Dict[str, Any]:
    in_tok = estimate_tokens(prompt_text)
    out_tok = estimate_tokens(output_text)
    total = in_tok + out_tok
    rate = _COST_PER_1M_TOKENS.get(provider, 0.5)
    cost = (total / 1_000_000.0) * rate

    TOKEN_USAGE_STATS["total_calls"] += 1
    if live:
        TOKEN_USAGE_STATS["live_calls"] += 1
    TOKEN_USAGE_STATS["prompt_tokens"] += in_tok
    TOKEN_USAGE_STATS["completion_tokens"] += out_tok
    TOKEN_USAGE_STATS["total_tokens"] += total
    TOKEN_USAGE_STATS["estimated_cost_usd"] += cost

    return {
        "provider": provider,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
        "total_tokens": total,
        "estimated_cost_usd": round(cost, 6),
    }


def get_token_usage_summary() -> Dict[str, Any]:
    """Return cumulative token and estimated cost stats for the current process."""
    return dict(TOKEN_USAGE_STATS)


# ------------------------------------------------------------------
# LANGCHAIN PROMPT TEMPLATES (TASK 8)
# ------------------------------------------------------------------
STRENGTHS_PROMPT = PromptTemplate(
    input_variables=["target_role", "resume_text"],
    template=(
        "You are an expert technical recruiter evaluating a candidate for the role of {target_role}.\n"
        "Analyze the resume below and identify 5 to 7 concrete strengths in order of importance.\n"
        "Cover: formatting, relevant experience, quantifiable achievements, action verbs, certifications, education, technical skills.\n"
        "Return STRICT JSON ONLY as an object with key 'strengths', where each item has:\n"
        "  title (str), description (str), category (str), evidence (exact quote/excerpt from resume), confidence (int 0-100).\n\n"
        "Resume:\n{resume_text}"
    ),
)

WEAKNESSES_PROMPT = PromptTemplate(
    input_variables=["target_role", "resume_text"],
    template=(
        "You are an expert resume reviewer evaluating a candidate for {target_role}.\n"
        "Identify 5 to 7 specific weaknesses in the resume below.\n"
        "Check: missing contact info, grammar/spelling, lack of measurable metrics, irrelevant info, formatting issues, missing role skills, gaps.\n"
        "Return STRICT JSON ONLY as an object with key 'weaknesses', where each item has:\n"
        "  title (str), description (str), category (str), severity ('minor'|'moderate'|'critical'), "
        "location (section/line reference), evidence (excerpt or missing note), confidence (int 0-100).\n\n"
        "Resume:\n{resume_text}"
    ),
)

SKILLS_EXTRACTION_PROMPT = PromptTemplate(
    input_variables=["resume_text"],
    template=(
        "Extract every skill mentioned in the resume and classify them into exact JSON keys:\n"
        "programming_languages (list[str]), frameworks (list[str]), tools (list[str]), "
        "soft_skills (list[str]), domain_knowledge (list[str]), certifications (list[str]), "
        "skill_experience_years (dict mapping skill->years string if explicitly stated).\n"
        "Return STRICT JSON ONLY.\n\nResume:\n{resume_text}"
    ),
)

SKILLS_GAP_PROMPT = PromptTemplate(
    input_variables=["target_role", "extracted_skills", "resume_text"],
    template=(
        "Compare the candidate's extracted skills against industry expectations for {target_role}.\n"
        "Extracted skills JSON: {extracted_skills}\n"
        "Return STRICT JSON ONLY with keys:\n"
        "  missing_critical_skills (list[str]), missing_nice_to_have_skills (list[str]),\n"
        "  recommendations (list of 5-10 objects with: skill, priority ('High'|'Medium'), category, "
        "why_important, use_cases, learning_difficulty ('Beginner'|'Intermediate'|'Advanced'), "
        "resources (list of {{name, platform, url}})).\n\n"
        "Resume snippet:\n{resume_text}"
    ),
)

SCORING_PROMPT = PromptTemplate(
    input_variables=["target_role", "resume_text"],
    template=(
        "Evaluate the resume for {target_role} across 5 components from 0 to 100 based solely on evidence:\n"
        "1. completeness (25%): contact info, summary, experience, education, skills\n"
        "2. content_quality (30%): action verbs, quantifiable metrics, relevance\n"
        "3. formatting (15%): consistency, readability, structure, length\n"
        "4. keyword_relevance (20%): industry keywords and role-specific skills\n"
        "5. experience (10%): years/duration, progression, alignment\n"
        "Return STRICT JSON ONLY with keys matching the 5 component names; each value must be an object "
        "{{score: int, explanation: str, examples: list[str]}}.\n\nResume:\n{resume_text}"
    ),
)

IMPROVEMENT_PROMPT = PromptTemplate(
    input_variables=["target_role", "weaknesses", "resume_text"],
    template=(
        "You are a career coach. Based on the resume and weaknesses below for {target_role}, generate actionable improvements.\n"
        "Weaknesses: {weaknesses}\n"
        "Return STRICT JSON ONLY with keys:\n"
        "  weakness_actions (list of {{weakness_title, actions: list[str]}}),\n"
        "  before_after_examples (list of 3 {{section, original, improved, explanation}} using actual resume text),\n"
        "  section_recommendations (dict for 'Professional Summary', 'Experience', 'Skills', 'Education', 'Formatting', 'Achievements'),\n"
        "  high_impact (list of {{id, title, category, estimated_score_gain, action_steps}}),\n"
        "  quick_wins (list of {{id, title, category, estimated_score_gain, action_steps}}).\n\n"
        "Resume:\n{resume_text}"
    ),
)

JOB_REQUIREMENTS_PROMPT = PromptTemplate(
    input_variables=["job_description"],
    template=(
        "Parse the job description and return STRICT JSON ONLY with keys:\n"
        "must_have_skills (list[str]), nice_to_have_skills (list[str]), required_experience_years (float), "
        "seniority_level ('Entry Level'|'Mid Level'|'Senior'|'Lead/Manager'), required_education (str), "
        "responsibilities (list[str]).\n\nJob Description:\n{job_description}"
    ),
)

JOB_MATCH_EXPLANATION_PROMPT = PromptTemplate(
    input_variables=["job_title", "company_name", "match_score", "matching_skills", "missing_skills"],
    template=(
        "Write a concise 2-3 sentence explanation of why this candidate scored {match_score}% match for "
        "{job_title} at {company_name}. Matching skills: {matching_skills}. Missing skills: {missing_skills}."
    ),
)

APPLICATION_TIPS_PROMPT = PromptTemplate(
    input_variables=["job_title", "company_name", "matching_skills", "missing_skills", "resume_text"],
    template=(
        "Generate tailored application coaching as STRICT JSON ONLY for {job_title} at {company_name}.\n"
        "Matching skills: {matching_skills}. Missing skills: {missing_skills}.\n"
        "Keys: skills_to_highlight (list[str]), how_to_address_gaps (list[str]), "
        "interview_talking_points (list[str]), company_research_tips (list[str]), "
        "common_interview_questions (list[str]), customized_cover_letter (str), "
        "resume_keyword_tweaks (list[str]).\n\nResume excerpt:\n{resume_text}"
    ),
)

PROMPT_TEMPLATES = {
    "strengths": STRENGTHS_PROMPT,
    "weaknesses": WEAKNESSES_PROMPT,
    "skills_extraction": SKILLS_EXTRACTION_PROMPT,
    "skills_gap": SKILLS_GAP_PROMPT,
    "scoring": SCORING_PROMPT,
    "improvements": IMPROVEMENT_PROMPT,
    "job_requirements": JOB_REQUIREMENTS_PROMPT,
    "job_match_explanation": JOB_MATCH_EXPLANATION_PROMPT,
    "application_tips": APPLICATION_TIPS_PROMPT,
}


# ------------------------------------------------------------------
# RESPONSE JSON PARSING
# ------------------------------------------------------------------
def parse_json_response(raw_text: str) -> Optional[Any]:
    """Parse JSON from an LLM output string, stripping markdown code fences if present."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = cleaned.find(start_char)
        end_idx = cleaned.rfind(end_char)
        if start_idx != -1 and end_idx > start_idx:
            candidate = cleaned[start_idx : end_idx + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


# ------------------------------------------------------------------
# PROVIDER INVOCATION WITH RETRY & TIMEOUT
# ------------------------------------------------------------------
class TransientLLMError(RuntimeError):
    """Error eligible for exponential backoff retry."""


@retry(
    retry=retry_if_exception_type(TransientLLMError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    reraise=True,
)
def _invoke_provider(
    provider: str,
    model: str,
    prompt_text: str,
    temperature: float,
    max_tokens: int,
    timeout: int = 30,
) -> str:
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        try:
            # Prefer LangChain integration when available
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_key,
                temperature=temperature,
                max_output_tokens=max_tokens,
                timeout=timeout,
            )
            msg = llm.invoke(prompt_text)
            return str(getattr(msg, "content", msg)).strip()
        except Exception as lc_exc:
            logger.debug("LangChain Gemini invocation fell back to google-genai SDK: %s", lc_exc)
            try:
                from google import genai

                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model=model if model.startswith("models/") else f"models/{model}",
                    contents=prompt_text,
                )
                return (resp.text or "").strip()
            except Exception as sdk_exc:
                err_str = str(sdk_exc).lower()
                if any(tok in err_str for tok in ("429", "rate", "timeout", "unavailable", "503")):
                    raise TransientLLMError(str(sdk_exc)) from sdk_exc
                raise

    if provider == "openai":
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        openai_model = model if "gpt" in model.lower() else "gpt-4o-mini"
        client = OpenAI(api_key=api_key, timeout=timeout)
        try:
            resp = client.chat.completions.create(
                model=openai_model,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            err_str = str(exc).lower()
            if any(tok in err_str for tok in ("429", "rate", "timeout", "503", "502")):
                raise TransientLLMError(str(exc)) from exc
            raise

    if provider == "ollama":
        base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        ollama_model = model if "llama" in model.lower() or "mistral" in model.lower() else "llama3"
        try:
            resp = requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt_text,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return (resp.json().get("response") or "").strip()
        except requests.RequestException as exc:
            raise TransientLLMError(str(exc)) from exc

    raise RuntimeError("No live LLM provider configured.")


def call_llm(
    prompt: str,
    resume_text: str = "",
    temperature: float = 0.2,
    max_tokens: int = 2500,
    expect_json: bool = False,
    task_name: str = "analysis",
    timeout: int = 30,
) -> Dict[str, Any]:
    """Unified LLM call with error handling, retries, token/cost tracking, and JSON parsing.

    Returns dict:
        {
            "success": bool,
            "mode": "live" | "demo",
            "provider": str,
            "text": str,
            "data": Any (parsed JSON if expect_json=True),
            "usage": dict,
            "error": str | None,
        }
    """
    cfg = get_llm_config()
    combined_prompt = prompt
    if resume_text:
        trimmed = resume_text[:MAX_CHARS]
        if "{resume_text}" in combined_prompt:
            combined_prompt = combined_prompt.replace("{resume_text}", trimmed)
        elif trimmed not in combined_prompt:
            combined_prompt = f"{combined_prompt}\n\nResume:\n{trimmed}"

    if not cfg["is_live"]:
        log_api_call("demo", task_name, "skipped_no_key", details="API key not configured")
        return {
            "success": False,
            "mode": "demo",
            "provider": "demo",
            "text": "",
            "data": None,
            "usage": {"provider": "demo", "total_tokens": 0, "estimated_cost_usd": 0.0},
            "error": "No valid LLM API key configured in .env; using deterministic evidence-based analysis mode.",
        }

    provider = cfg["active_provider"]
    model = cfg["model"]
    try:
        raw_text = _invoke_provider(
            provider=provider,
            model=model,
            prompt_text=combined_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        usage = _record_usage(provider, combined_prompt, raw_text, live=True)
        parsed = parse_json_response(raw_text) if expect_json else None
        if expect_json and parsed is None:
            log_api_call(provider, task_name, "json_parse_failed", tokens=usage["total_tokens"], cost_usd=usage["estimated_cost_usd"])
            return {
                "success": False,
                "mode": "live",
                "provider": provider,
                "text": raw_text,
                "data": None,
                "usage": usage,
                "error": "LLM returned non-JSON response.",
            }

        log_api_call(
            provider,
            task_name,
            "success",
            tokens=usage["total_tokens"],
            cost_usd=usage["estimated_cost_usd"],
        )
        return {
            "success": True,
            "mode": "live",
            "provider": provider,
            "text": raw_text,
            "data": parsed,
            "usage": usage,
            "error": None,
        }
    except Exception as exc:
        TOKEN_USAGE_STATS["failed_calls"] += 1
        log_api_call(provider, task_name, "error", details=str(exc))
        logger.warning("LLM call failed (%s/%s): %s", provider, task_name, exc)
        return {
            "success": False,
            "mode": "live",
            "provider": provider,
            "text": "",
            "data": None,
            "usage": {"provider": provider, "total_tokens": 0, "estimated_cost_usd": 0.0},
            "error": str(exc),
        }


def test_api_connection() -> Tuple[bool, str, str]:
    """Test configured LLM API connectivity using a minimal prompt."""
    cfg = get_llm_config()
    if not cfg["is_live"]:
        return (
            False,
            "demo",
            "No valid GEMINI_API_KEY or OPENAI_API_KEY found in .env. Running in Evidence-Based Demo Mode.",
        )

    res = call_llm(
        prompt="Respond with the single word OK.",
        temperature=0.0,
        max_tokens=16,
        expect_json=False,
        task_name="connectivity_test",
        timeout=15,
    )
    if res["success"] and res["text"]:
        return True, res["provider"], f"Connected to {res['provider']} ({cfg['model']}) successfully."
    return False, res["provider"], f"API test failed: {res['error']}"


# ------------------------------------------------------------------
# BACKWARDS-COMPATIBLE LEGACY FUNCTIONS
# ------------------------------------------------------------------
def ask_gemini(prompt: str) -> str:
    """Backwards-compatible plain-text prompt helper."""
    res = call_llm(prompt=prompt, expect_json=False, task_name="legacy_prompt")
    if res["success"]:
        return res["text"]
    return f"Demo Mode / API Unavailable: {res['error']}"


def analyze_score(text: str) -> str:
    """Legacy wrapper returning formatted score summary."""
    from backend.resume_scorer import calculate_resume_score

    scored = calculate_resume_score(text)
    return (
        f"Overall Score: {scored['overall_score']}/100 ({scored['classification']})\n"
        + "\n".join(
            f"- {comp['label']}: {comp['score']}/100 ({comp['weight_pct']}% weight)"
            for comp in scored["components"].values()
        )
    )


def analyze_strengths(text: str) -> str:
    """Legacy wrapper returning bulleted strengths."""
    from backend.resume_analyzer import analyze_strengths_and_weaknesses

    res = analyze_strengths_and_weaknesses(text)
    return "\n".join(f"• {s['title']}: {s['description']}" for s in res["strengths"])


def analyze_weaknesses(text: str) -> str:
    """Legacy wrapper returning bulleted weaknesses."""
    from backend.resume_analyzer import analyze_strengths_and_weaknesses

    res = analyze_strengths_and_weaknesses(text)
    return "\n".join(f"• [{w['severity'].upper()}] {w['title']}: {w['description']}" for w in res["weaknesses"])


def analyze_skills(text: str) -> str:
    """Legacy wrapper returning formatted skills."""
    from backend.skills_analyzer import extract_resume_skills

    sk = extract_resume_skills(text)
    return (
        f"Technical: {', '.join(sk['technical_skills'])}\n"
        f"Soft Skills: {', '.join(sk['soft_skills'])}\n"
        f"Tools: {', '.join(sk['tools'])}"
    )


def analyze_skills_gap(text: str, role: str = "Software Developer") -> str:
    """Legacy wrapper returning formatted skills gap."""
    from backend.skills_analyzer import analyze_skills_gap_structured

    gap = analyze_skills_gap_structured(text, role)
    return (
        f"Missing Critical Skills ({role}): {', '.join(gap['missing_critical_skills'])}\n"
        f"Recommended Skills: {', '.join(r['skill'] for r in gap['recommendations'][:5])}"
    )
