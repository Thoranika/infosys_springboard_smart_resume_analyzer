"""Formatted PDF analysis report generator with Matplotlib charts & ReportLab Platypus."""

from __future__ import annotations

import io
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from utils.database import BASE_DIR


def _safe_text(val: Any) -> str:
    """Escape XML special characters for ReportLab Paragraph."""
    text = str(val or "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _create_component_scores_chart(score_data: Dict[str, Any]) -> io.BytesIO:
    """Render horizontal bar chart of component scores vs industry benchmarks."""
    comps = list((score_data.get("components") or {}).values())
    labels = [c["label"] for c in comps]
    scores = [c["score"] for c in comps]
    benchmarks = [c.get("industry_benchmark", 75) for c in comps]

    fig, ax = plt.subplots(figsize=(6.4, 2.8), dpi=150)
    y_pos = list(range(len(labels)))
    bar_colors = [
        "#2563eb" if s >= 90 else ("#16a34a" if s >= 75 else ("#d97706" if s >= 60 else "#dc2626"))
        for s in scores
    ]

    ax.barh(y_pos, scores, height=0.52, color=bar_colors, label="Your Score")
    ax.scatter(benchmarks, y_pos, color="#0f172a", zorder=5, s=36, label="Industry Benchmark")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 108)
    ax.set_xlabel("Score (0 - 100)", fontsize=8.5)
    ax.set_title("Resume Component Scores vs. Industry Benchmark", fontsize=10, fontweight="bold")
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.legend(loc="lower right", fontsize=7.5)

    for idx, val in enumerate(scores):
        ax.text(val + 1.5, idx, f"{val}", va="center", fontsize=8, fontweight="bold", color="#1e293b")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def _create_skills_gap_chart(skills_gap: Dict[str, Any]) -> io.BytesIO:
    """Render bar chart comparing present skills vs missing skills."""
    chart_data = skills_gap.get("chart_data") or {}
    counts = [
        chart_data.get("present_count", 0),
        chart_data.get("missing_critical_count", 0),
        chart_data.get("missing_nice_count", 0),
    ]
    labels = ["Present Skills", "Missing Must-Have", "Missing Nice-to-Have"]
    bar_colors = ["#16a34a", "#dc2626", "#d97706"]

    fig, ax = plt.subplots(figsize=(6.0, 2.4), dpi=150)
    bars = ax.bar(labels, counts, color=bar_colors, width=0.5)
    ax.set_ylabel("Skill Count", fontsize=8.5)
    ax.set_title(
        f"Skills Gap Overview ({skills_gap.get('target_role', 'Target Role')})",
        fontsize=10,
        fontweight="bold",
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2.0, h + 0.2, f"{int(h)}", ha="center", fontsize=8.5, fontweight="bold")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_analysis_pdf_report(
    user_name: str,
    analysis_result: Dict[str, Any],
    save_to_disk: bool = True,
) -> bytes:
    """Create a polished multi-section PDF resume analysis report and return bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=42,
        bottomMargin=42,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=18,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1d4ed8"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyClean",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
    )

    score_data = analysis_result.get("score_data") or {}
    overall = score_data.get("overall_score", analysis_result.get("overall_score", 0))
    classification = score_data.get("classification", analysis_result.get("classification", "N/A"))
    target_role = analysis_result.get("target_role", "Software Developer")
    strengths: List[Dict[str, Any]] = analysis_result.get("strengths") or []
    weaknesses: List[Dict[str, Any]] = analysis_result.get("weaknesses") or []
    skills_gap: Dict[str, Any] = analysis_result.get("skills_gap") or {}

    story: List[Any] = []
    story.append(Paragraph("AI-Powered Resume Analysis Report", title_style))
    story.append(
        Paragraph(
            f"<b>Candidate:</b> {_safe_text(user_name)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Target Role:</b> {_safe_text(target_role)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            body_style,
        )
    )
    story.append(Spacer(1, 10))

    # Overall Score Summary Table
    summary_table = Table(
        [
            ["Overall Resume Score", "Rating Tier", "Industry Benchmark", "Role Skill Coverage"],
            [
                f"{overall} / 100",
                _safe_text(classification),
                f"{score_data.get('industry_benchmark', 77.0)} / 100",
                f"{(skills_gap.get('chart_data') or {}).get('coverage_percentage', 0)}%",
            ],
        ],
        colWidths=[1.65 * inch, 1.75 * inch, 1.65 * inch, 1.65 * inch],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eff6ff")),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 11),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Component Score Breakdown + Chart
    story.append(Paragraph("Weighted Component Score Breakdown", h2_style))
    comp_rows = [["Component", "Weight", "Score", "Evaluation Summary"]]
    for comp in (score_data.get("components") or {}).values():
        comp_rows.append(
            [
                _safe_text(comp["label"]),
                f"{comp['weight_pct']}%",
                f"{comp['score']}/100",
                Paragraph(_safe_text(comp["explanation"]), body_style),
            ]
        )
    if len(comp_rows) > 1:
        comp_table = Table(
            comp_rows,
            colWidths=[1.45 * inch, 0.7 * inch, 0.75 * inch, 3.8 * inch],
        )
        comp_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(comp_table)
        story.append(Spacer(1, 8))
        chart_img = Image(_create_component_scores_chart(score_data), width=6.2 * inch, height=2.6 * inch)
        story.append(chart_img)

    # Strengths
    story.append(Paragraph("Key Resume Strengths", h2_style))
    for idx, s in enumerate(strengths, start=1):
        story.append(
            Paragraph(
                f"<b>{idx}. {_safe_text(s.get('title'))}</b> "
                f"[{_safe_text(s.get('category'))} | Confidence: {s.get('confidence', 85)}%]: "
                f"{_safe_text(s.get('description'))} "
                f"<i>(Evidence: {_safe_text(s.get('evidence'))})</i>",
                body_style,
            )
        )
        story.append(Spacer(1, 4))

    # Weaknesses
    story.append(Paragraph("Areas Requiring Improvement (Weaknesses)", h2_style))
    for idx, w in enumerate(weaknesses, start=1):
        sev = str(w.get("severity") or "moderate").upper()
        story.append(
            Paragraph(
                f"<b>{idx}. [{sev}] {_safe_text(w.get('title'))}</b> "
                f"({_safe_text(w.get('location'))}): {_safe_text(w.get('description'))}",
                body_style,
            )
        )
        story.append(Spacer(1, 4))

    # Skills Gap Analysis
    story.append(Paragraph("Skills Gap & Learning Recommendations", h2_style))
    extracted = skills_gap.get("extracted_skills") or {}
    story.append(
        Paragraph(
            f"<b>Identified Technical Skills:</b> {_safe_text(', '.join(extracted.get('technical_skills') or []) or 'None')}<br/>"
            f"<b>Identified Soft Skills:</b> {_safe_text(', '.join(extracted.get('soft_skills') or []) or 'None')}<br/>"
            f"<b>Missing Must-Have Skills:</b> {_safe_text(', '.join(skills_gap.get('missing_critical_skills') or []) or 'None')}<br/>"
            f"<b>Missing Nice-to-Have Skills:</b> {_safe_text(', '.join(skills_gap.get('missing_nice_to_have_skills') or []) or 'None')}",
            body_style,
        )
    )
    story.append(Spacer(1, 6))
    gap_img = Image(_create_skills_gap_chart(skills_gap), width=5.6 * inch, height=2.2 * inch)
    story.append(gap_img)
    story.append(Spacer(1, 6))

    recs = skills_gap.get("recommendations") or []
    if recs:
        story.append(Paragraph("Prioritized Skill Recommendations:", body_style))
        for rec in recs[:7]:
            story.append(
                Paragraph(
                    f"• <b>{_safe_text(rec.get('skill'))}</b> ({_safe_text(rec.get('priority'))} Priority, "
                    f"{_safe_text(rec.get('learning_difficulty'))}): {_safe_text(rec.get('why_important'))}",
                    body_style,
                )
            )
            story.append(Spacer(1, 2))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    if save_to_disk:
        reports_dir = os.path.join(BASE_DIR, "data", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        out_path = os.path.join(reports_dir, f"resume_report_{int(time.time())}.pdf")
        try:
            with open(out_path, "wb") as f:
                f.write(pdf_bytes)
        except OSError:
            pass

    return pdf_bytes
