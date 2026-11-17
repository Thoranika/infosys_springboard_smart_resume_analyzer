"""Compatibility wrapper delegating improvement suggestions to backend.improvement_suggestions."""

from backend.improvement_suggestions import (
    generate_improvement_suggestions,
    update_improvement_item_status,
)


def analyze_improvements(resume_text: str, target_role: str = "Software Developer") -> str:
    """Legacy plain-text summary wrapper for backward compatibility."""
    plan = generate_improvement_suggestions(resume_text, target_role=target_role)
    lines = ["HIGH IMPACT IMPROVEMENTS:"]
    for item in plan["high_impact"]:
        lines.append(f"- {item['title']} ({item['estimated_score_gain']})")
    lines.append("\nQUICK WINS:")
    for item in plan["quick_wins"]:
        lines.append(f"- {item['title']} ({item['estimated_score_gain']})")
    return "\n".join(lines)


__all__ = [
    "analyze_improvements",
    "generate_improvement_suggestions",
    "update_improvement_item_status",
]
