import os
import json
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv
# Removed Gemini dependency; prefer OpenAI fallback

# Optional OpenAI fallbacks
OpenAIChat = None
openai = None
try:
  from langchain.chat_models import ChatOpenAI as OpenAIChat
except Exception:
  OpenAIChat = None
try:
  import openai
except Exception:
  openai = None

# -------------------------------------------------------------
# LOAD API KEY
# -------------------------------------------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
  raise ValueError("❌ OPENAI_API_KEY missing in .env file")
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY


# -------------------------------------------------------------
# MODEL SETUP
# -------------------------------------------------------------
model = None
model_source = None

# Prefer LangChain ChatOpenAI, then raw openai as a last resort.
if OpenAIChat is not None:
  try:
    model = OpenAIChat(temperature=0.3)
    model_source = "langchain_openai"
  except Exception as e:
    try:
      with open(os.path.join(os.path.dirname(__file__), "llm_analyzer_debug.log"), "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.utcnow().isoformat()} - ChatOpenAI init error: {e}\n")
    except Exception:
      pass

if model is None and openai is not None:
  # Final fallback: raw openai client wrapper
  class _OpenAIWrapper:
    def __init__(self):
      # expects OPENAI_API_KEY in env
      pass

    def generate(self, prompts):
      # prompts: list[str]
      try:
        prompt = prompts[0] if isinstance(prompts, (list, tuple)) else prompts
        # Use OpenAI v1 client if available (openai.OpenAI()), otherwise try legacy ChatCompletion
        text = None
        try:
          if hasattr(openai, "OpenAI"):
            client = openai.OpenAI()
            resp = client.chat.completions.create(
              model=os.getenv("OPENAI_MODEL", "gpt-4o"),
              messages=[{"role": "user", "content": prompt}],
              temperature=0.3,
            )
            try:
              # resp.choices[0].message.content
              text = resp.choices[0].message.content
            except Exception:
              try:
                text = resp.choices[0].message["content"]
              except Exception:
                try:
                  text = resp.choices[0]["message"]["content"]
                except Exception:
                  text = str(resp)
          else:
            # legacy fallback
            resp = openai.ChatCompletion.create(
              model=os.getenv("OPENAI_MODEL", "gpt-4o"),
              messages=[{"role": "user", "content": prompt}],
              temperature=0.3,
            )
            try:
              text = resp["choices"][0]["message"]["content"]
            except Exception:
              try:
                text = resp["choices"][0]["text"]
              except Exception:
                text = str(resp)
        except Exception as e:
          return str(e)
        return {"choices": [{"text": text}]}
      except Exception as e:
        return str(e)

    def __call__(self, prompt):
      return self.generate(prompt)

  model = _OpenAIWrapper()
  model_source = "openai_raw"

if model is None:
  try:
    with open(os.path.join(os.path.dirname(__file__), "llm_analyzer_debug.log"), "a", encoding="utf-8") as fh:
      fh.write(f"{datetime.utcnow().isoformat()} - no LLM backend available\n")
  except Exception:
    pass


def ask_gemini(prompt: str) -> str:
    """
    Base LLM interface. Safe response return.
    """
    # Try multiple common LangChain-style invocation methods and return the first usable text.
    methods_to_try = ["invoke", "generate", "predict", "__call__"]
    last_err = None

    def _extract_text_from_res(res) -> str | None:
      """Robustly extract a text string from various possible response shapes."""
      try:
        # direct string
        if isinstance(res, str):
          return res

        # dict-like
        if isinstance(res, dict):
          for key in ("content", "text", "response", "answer"):
            if key in res and isinstance(res[key], str):
              return res[key]

        # objects with attributes
        for attr in ("content", "text", "response", "answer"):
          if hasattr(res, attr):
            val = getattr(res, attr)
            if isinstance(val, str):
              return val

        # langchain-like generate output: try generations -> first -> text
        if hasattr(res, "generations"):
          gens = getattr(res, "generations")
          try:
            # gens can be nested lists
            first = gens[0]
            # if nested list
            if isinstance(first, (list, tuple)):
              cand = first[0]
            else:
              cand = first
            if hasattr(cand, "text"):
              return getattr(cand, "text")
            if isinstance(cand, dict) and "text" in cand:
              return cand["text"]
          except Exception:
            pass

        # choices (OpenAI-like)
        if hasattr(res, "choices"):
          try:
            ch = getattr(res, "choices")
            first = ch[0]
            if isinstance(first, dict) and "text" in first:
              return first["text"]
            if hasattr(first, "text"):
              return getattr(first, "text")
          except Exception:
            pass

        # list: try first element recursively
        if isinstance(res, (list, tuple)) and len(res) > 0:
          return _extract_text_from_res(res[0])

      except Exception:
        return None
      return None

    for method in methods_to_try:
      if hasattr(model, method):
        try:
          fn = getattr(model, method)
          res = fn(prompt) if method != "generate" else fn([prompt])

          text = _extract_text_from_res(res)
          if text:
            return text

          # if extraction failed, log the raw repr for debugging and continue
          with open(os.path.join(os.path.dirname(__file__), "llm_analyzer_debug.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.utcnow().isoformat()} - method={method} raw_response={repr(res)}\n")

        except Exception as e:
          last_err = e
          # log exception
          try:
            with open(os.path.join(os.path.dirname(__file__), "llm_analyzer_debug.log"), "a", encoding="utf-8") as fh:
              fh.write(f"{datetime.utcnow().isoformat()} - method={method} exception={str(e)}\n")
          except Exception:
            pass
          continue

    # If none worked, log and return an error string for visibility upstream.
    err_msg = f"ERROR: no invocation method succeeded. last error: {last_err}"
    try:
      with open(os.path.join(os.path.dirname(__file__), "llm_analyzer_debug.log"), "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.utcnow().isoformat()} - ask_gemini failure: {err_msg}\n")
    except Exception:
      pass
    return err_msg


# -------------------------------------------------------------
# STRENGTH ANALYZER
# -------------------------------------------------------------
def analyze_strengths(text: str) -> Dict[str, Any]:
    prompt = f"""
You are a professional resume analysis AI.

Analyze the resume and extract actionable strengths.

Required Output Format (JSON only):
{{
 "strengths": [
   {{
     "point": "",
     "reason": "",
     "category": "",  // content / skills / experience / formatting
     "confidence": 0  // 0 - 100
   }}
 ]
}}

Rules:
- Return 5 to 7 items.
- Be specific and resume-based.
- No generic or repeated statements.

Resume Text:
{text}
"""

    response = ask_gemini(prompt)

    try:
      return json.loads(response)
    except Exception:
      return {"strengths": [], "_raw": response}



# -------------------------------------------------------------
# WEAKNESS ANALYZER
# -------------------------------------------------------------
def analyze_weaknesses(text: str) -> Dict[str, Any]:
    prompt = f"""
You are a resume correction assistant.

Analyze the resume and list weaknesses + solutions.

Required Output Format (JSON only):
{{
 "weaknesses": [
   {{
     "issue": "",
     "fix": "",
     "category": "",     // formatting / experience / skills / content
     "severity": "",     // minor / moderate / critical
     "confidence": 0     // 0 - 100
   }}
 ]
}}

Rules:
- Return 5 to 7 weaknesses.
- Be specific and refer to resume evidence.
- Suggest improvements clearly.
- No placeholder text.

Resume Text:
{text}
"""

    response = ask_gemini(prompt)

    try:
      return json.loads(response)
    except Exception:
      return {"weaknesses": [], "_raw": response}



# -------------------------------------------------------------
# SKILLS ANALYZER
# -------------------------------------------------------------
def analyze_skills(text: str) -> Dict[str, Any]:
    prompt = f"""
Extract skills from this resume.

Return in JSON format only:
{{
 "skills": [
   {{
     "name": "",
     "category": "",    // technical / soft / tools / language
     "confidence": 0
   }}
 ]
}}

Resume Text:
{text}
"""

    response = ask_gemini(prompt)

    try:
      return json.loads(response)
    except Exception:
      return {"skills": [], "_raw": response}

# -------------------------------------------------------------
# SKILLS GAP + ROLE RECOMMENDATION ANALYZER
# -------------------------------------------------------------
def analyze_skills_gap(text: str, target_role: str = "Software Developer") -> Dict[str, Any]:

    prompt = f"""
You are an AI Resume Skills Gap Analyst.

Analyze the resume and extract skills, then compare with industry skills for the role:
"{target_role}"

Return JSON ONLY using this structure:

{{
 "resume_skills": {{
   "technical_skills": [],
   "soft_skills": [],
   "tools": [],
   "domain_knowledge": [],
   "certifications": []
 }},

 "industry_required_skills": {{
   "must_have": [],
   "nice_to_have": []
 }},

 "missing_skills": {{
   "critical": [],
   "recommended": []
 }},

 "skill_recommendations": [
   {{
     "skill": "",
     "importance": "",          // high / medium / low
     "reason": "",
     "use_cases": "",
     "learning_resources": [
       "resource 1",
       "resource 2"
     ]
   }}
 ],

 "summary": ""
}}

RULES:
- Extract ALL resume skills accurately.
- Categorize correctly.
- Compare skills RESUME vs INDUSTRY role.
- Identify missing CRITICAL job skills.
- Identify missing RECOMMENDED job skills.
- Recommend 5-10 skills to learn.
- Include REALISTIC learning resources (Udemy, Coursera, YouTube, Docs).
- Respond using JSON only.
- No repeated skills.
- No generic output.

Resume Text:
{text}
"""

    response = ask_gemini(prompt)

    try:
      return json.loads(response)
    except Exception:
      return {
        "resume_skills": {},
        "industry_required_skills": {},
        "missing_skills": {},
        "skill_recommendations": [],
        "summary": "AI parsing error",
        "_raw": response
      }


# -------------------------------------------------------------
# SCORE ANALYZER
# -------------------------------------------------------------
def analyze_score(text: str) -> Dict[str, Any]:
    prompt = f"""
Score this resume on ATS standards.

Return ONLY JSON:
{{
 "score": 0,
 "reason": ""
}}

Rules:
- Score between 0 and 100.
- Consider formatting, keywords, skills, and structure.

Resume Text:
{text}
"""

    response = ask_gemini(prompt)

    try:
      return json.loads(response)
    except Exception:
      return {"score": 0, "reason": "Error parsing response", "_raw": response}

# save as scripts/test_llm.py then run: python scripts/test_llm.py
from backend.llm_analyzer import ask_gemini, analyze_score
print(ask_gemini("Say hello in one sentence."))         # raw LLM reply
print(analyze_score("Sample resume text to score."))   # structured JSON or fallback info
