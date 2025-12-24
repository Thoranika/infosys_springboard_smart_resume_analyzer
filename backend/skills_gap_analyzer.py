from backend.llm_analyzer import analyze_skills_gap
from utils.database import get_latest_resume_analysis

def run_skills_gap_analysis(user_id: int, target_role: str = "Software Developer"):

    resume = get_latest_resume_analysis(user_id)
    if not resume:
        return {"error": "No resume found"}

    text = resume["resume_text"]
    return analyze_skills_gap(text, target_role)
