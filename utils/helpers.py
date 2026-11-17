"""Shared UI helpers, dark theme styling, SVG gauges, and formatting utilities."""

from __future__ import annotations

import html
from typing import Iterable, Optional
import streamlit as st


def inject_custom_css() -> None:
    """Inject consistent dark charcoal & navy-blue theme styling across all Streamlit pages."""
    st.markdown(
        """
        <style>
        /* Core Dark Theme Surfaces */
        .stApp {
            background-color: #101116 !important;
            color: #F5F6FA !important;
        }
        [data-testid="stAppViewContainer"] {
            background-color: #101116 !important;
            color: #F5F6FA !important;
        }
        [data-testid="stHeader"] {
            background-color: #101116 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #252630 !important;
            border-right: 1px solid #343640;
        }
        [data-testid="stSidebar"] * {
            color: #F5F6FA;
        }
        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
            max-width: 1200px;
            color: #F5F6FA;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #F5F6FA !important;
        }
        p, li, label, span {
            color: #F5F6FA;
        }
        .stCaption, [data-testid="stCaptionContainer"] {
            color: #A8ACBA !important;
        }

        /* Native Inputs, Selectboxes, Expanders, File Uploader & Tabs */
        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div,
        [data-baseweb="select"] > div {
            background-color: #15171F !important;
            border-color: #343640 !important;
            color: #F5F6FA !important;
        }
        input, textarea {
            color: #F5F6FA !important;
        }
        [data-testid="stFileUploaderDropzone"] {
            background-color: #15171F !important;
            border: 1px dashed #3498F5 !important;
            color: #F5F6FA !important;
        }
        [data-testid="stExpander"] {
            background-color: #15171F !important;
            border: 1px solid #343640 !important;
            border-radius: 12px;
        }
        [data-testid="stMetric"] {
            background-color: #15171F !important;
            border: 1px solid #343640;
            border-radius: 12px;
            padding: 0.75rem 1rem;
        }
        [data-testid="stMetricLabel"] p {
            color: #A8ACBA !important;
        }
        [data-testid="stMetricValue"] {
            color: #F5F6FA !important;
        }

        /* Consistent Dark & Blue-Accent Buttons */
        .stButton > button, .stDownloadButton > button, .stLinkButton > a {
            background-color: #15171F !important;
            color: #F5F6FA !important;
            border: 1px solid #343640 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            transition: border-color 0.15s ease, background-color 0.15s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {
            border-color: #3498F5 !important;
            color: #3498F5 !important;
        }
        .stButton > button[kind="primary"] {
            background-color: #3498F5 !important;
            border-color: #3498F5 !important;
            color: #FFFFFF !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #2584df !important;
            color: #FFFFFF !important;
        }

        /* Alerts (Success / Info / Warning / Error) */
        div[data-testid="stAlert"] {
            border-radius: 10px !important;
            border: 1px solid #343640 !important;
        }
        div[data-testid="stNotificationContentSuccess"],
        .stSuccess {
            background-color: #174331 !important;
            color: #4ADE80 !important;
        }
        div[data-testid="stNotificationContentWarning"],
        .stWarning {
            background-color: #49391B !important;
            color: #FCD34D !important;
        }
        div[data-testid="stNotificationContentError"],
        .stError {
            background-color: #4B2429 !important;
            color: #FCA5A5 !important;
        }
        div[data-testid="stNotificationContentInfo"],
        .stInfo {
            background-color: #192F46 !important;
            color: #F5F6FA !important;
        }

        /* Hero Header Banner */
        .hero-banner {
            background: linear-gradient(135deg, #192F46 0%, #15171F 100%);
            border: 1px solid #343640;
            border-radius: 16px;
            padding: 1.5rem 1.75rem;
            margin-bottom: 1.25rem;
            color: #F5F6FA;
        }
        .hero-banner h1, .hero-banner h2, .hero-banner h3 {
            color: #F5F6FA !important;
            margin: 0 0 0.35rem 0;
        }
        .hero-banner p {
            color: #A8ACBA !important;
            margin: 0;
            font-size: 0.98rem;
        }

        /* Navy-Blue Main Content Cards & Secondary Cards */
        .soft-card {
            background: #192F46;
            border: 1px solid #343640;
            border-radius: 14px;
            padding: 1.15rem 1.25rem;
            margin-bottom: 0.9rem;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
            color: #F5F6FA;
        }
        .soft-card h4, .soft-card h5 {
            color: #F5F6FA !important;
            margin-top: 0;
            margin-bottom: 0.45rem;
        }
        .soft-card p, .soft-card li {
            color: #A8ACBA;
        }
        .metric-card {
            background: #15171F;
            border: 1px solid #343640;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            text-align: left;
            box-shadow: 0 1px 6px rgba(0, 0, 0, 0.2);
        }
        .metric-label {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #A8ACBA;
            margin-bottom: 0.3rem;
        }
        .metric-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #F5F6FA;
            line-height: 1.2;
        }
        .metric-sub {
            font-size: 0.82rem;
            color: #A8ACBA;
            margin-top: 0.25rem;
        }

        /* Strength & Weakness Cards */
        .strength-card {
            background: #192F46;
            border: 1px solid #343640;
            border-left: 5px solid #3498F5;
            border-radius: 12px;
            padding: 0.95rem 1.1rem;
            margin-bottom: 0.75rem;
            color: #F5F6FA;
        }
        .strength-card strong {
            color: #F5F6FA;
        }
        .strength-card p {
            color: #A8ACBA;
        }
        .weakness-critical {
            background: #4B2429;
            border: 1px solid #343640;
            border-left: 5px solid #ef4444;
            border-radius: 12px;
            padding: 0.95rem 1.1rem;
            margin-bottom: 0.75rem;
            color: #F5F6FA;
        }
        .weakness-moderate {
            background: #49391B;
            border: 1px solid #343640;
            border-left: 5px solid #f59e0b;
            border-radius: 12px;
            padding: 0.95rem 1.1rem;
            margin-bottom: 0.75rem;
            color: #F5F6FA;
        }
        .weakness-minor {
            background: #15171F;
            border: 1px solid #343640;
            border-left: 5px solid #3498F5;
            border-radius: 12px;
            padding: 0.95rem 1.1rem;
            margin-bottom: 0.75rem;
            color: #F5F6FA;
        }

        /* Chips / Tags */
        .chip-container {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 0.35rem;
            margin-bottom: 0.5rem;
        }
        .chip {
            display: inline-block;
            padding: 0.25rem 0.65rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            border: 1px solid transparent;
        }
        .chip-blue { background: #192F46; color: #3498F5; border-color: #3498F5; }
        .chip-green { background: #174331; color: #4ADE80; border-color: #22c55e; }
        .chip-red { background: #4B2429; color: #FCA5A5; border-color: #ef4444; }
        .chip-amber { background: #49391B; color: #FCD34D; border-color: #f59e0b; }
        .chip-purple { background: #261b47; color: #C4B5FD; border-color: #7c3aed; }
        .chip-slate { background: #252630; color: #F5F6FA; border-color: #343640; }

        /* Job Cards */
        .job-card {
            background: #192F46;
            border: 1px solid #343640;
            border-radius: 14px;
            padding: 1.15rem 1.3rem;
            margin-bottom: 0.85rem;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.22);
            color: #F5F6FA;
        }
        .badge-excellent { background: #174331; color: #4ADE80; border: 1px solid #22c55e; padding: 4px 10px; border-radius: 999px; font-weight: 700; font-size: 0.82rem; }
        .badge-good { background: #15171F; color: #3498F5; border: 1px solid #3498F5; padding: 4px 10px; border-radius: 999px; font-weight: 700; font-size: 0.82rem; }
        .badge-fair { background: #49391B; color: #FCD34D; border: 1px solid #f59e0b; padding: 4px 10px; border-radius: 999px; font-weight: 700; font-size: 0.82rem; }
        .badge-low { background: #4B2429; color: #FCA5A5; border: 1px solid #ef4444; padding: 4px 10px; border-radius: 999px; font-weight: 700; font-size: 0.82rem; }
        .badge-featured { background: #15171F; color: #60A5FA; border: 1px solid #3498F5; padding: 3px 9px; border-radius: 999px; font-weight: 600; font-size: 0.76rem; margin-left: 6px; }
        .badge-urgent { background: #49391B; color: #FCD34D; border: 1px solid #f59e0b; padding: 3px 9px; border-radius: 999px; font-weight: 600; font-size: 0.76rem; margin-left: 6px; }

        /* Compact Bottom-Right Logout Alignment */
        .bottom-logout-wrap {
            margin-top: 2rem;
            padding-top: 0.75rem;
            border-top: 1px solid #343640;
            display: flex;
            justify-content: flex-end;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def score_color_hex(score: float) -> str:
    """Return Milestone 2 color coding for resume score gauge."""
    if score >= 90:
        return "#3498F5"  # Accent Blue: Excellent (90+)
    if score >= 75:
        return "#4ADE80"  # Success Green: Good (75-89)
    if score >= 60:
        return "#FBBF24"  # Amber: Average (60-74)
    return "#F87171"      # Coral Red: Needs Improvement (<60)


def render_circular_gauge_html(score: float, label: str, subtitle: str = "Overall Resume Score") -> str:
    """Generate clean dark-theme SVG circular progress gauge HTML for Streamlit."""
    clamped = max(0.0, min(100.0, float(score or 0.0)))
    color = score_color_hex(clamped)
    radius = 58
    circumference = 2 * 3.14159265 * radius
    offset = circumference * (1.0 - clamped / 100.0)
    safe_label = html.escape(label)
    safe_sub = html.escape(subtitle)
    return f"""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center;
                background:#192F46; border:1px solid #343640; border-radius:16px; padding:1.25rem;">
        <svg width="150" height="150" viewBox="0 0 150 150">
            <circle cx="75" cy="75" r="{radius}" fill="none" stroke="#252630" stroke-width="12" />
            <circle cx="75" cy="75" r="{radius}" fill="none" stroke="{color}" stroke-width="12"
                    stroke-linecap="round"
                    stroke-dasharray="{circumference:.2f}"
                    stroke-dashoffset="{offset:.2f}"
                    transform="rotate(-90 75 75)" />
            <text x="75" y="72" text-anchor="middle" font-size="28" font-weight="700" fill="#F5F6FA">
                {clamped:.0f}
            </text>
            <text x="75" y="94" text-anchor="middle" font-size="12" font-weight="600" fill="#A8ACBA">
                / 100
            </text>
        </svg>
        <div style="margin-top:0.4rem; padding:4px 14px; border-radius:999px;
                    background:{color}26; color:{color}; font-weight:700; font-size:0.92rem; border:1px solid {color};">
            {safe_label}
        </div>
        <div style="margin-top:0.3rem; font-size:0.8rem; color:#A8ACBA;">{safe_sub}</div>
    </div>
    """


def render_chips_html(items: Iterable[str], variant: str = "blue", empty_text: str = "None detected") -> str:
    """Render a flex-wrapped set of HTML badge chips."""
    clean_items = [str(i).strip() for i in (items or []) if str(i).strip()]
    if not clean_items:
        return f"<span style='color:#A8ACBA; font-size:0.85rem;'>{html.escape(empty_text)}</span>"
    spans = "".join(
        f"<span class='chip chip-{html.escape(variant)}'>{html.escape(item)}</span>"
        for item in clean_items
    )
    return f"<div class='chip-container'>{spans}</div>"


def match_badge_class(match_pct: float) -> str:
    """Return CSS class name for match score badge."""
    if match_pct >= 85:
        return "badge-excellent"
    if match_pct >= 70:
        return "badge-good"
    if match_pct >= 60:
        return "badge-fair"
    return "badge-low"


def format_file_size(num_bytes: Optional[int]) -> str:
    """Format byte count into human-readable KB/MB."""
    if not num_bytes or num_bytes <= 0:
        return "0 KB"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"
