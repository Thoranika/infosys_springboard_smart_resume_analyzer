"""SQLite database connection, non-destructive migrations, and CRUD utilities."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "resumes"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "reports"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "database"), exist_ok=True)

DB_PATH = os.getenv("DB_PATH") or os.path.join(DATA_DIR, "app.db")
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, DB_PATH)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a SQLite connection with Row factory and foreign keys enabled."""
    target = db_path or DB_PATH
    parent = os.path.dirname(os.path.abspath(target))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(target, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _validate_email(email: str) -> None:
    if not EMAIL_REGEX.match(email or ""):
        raise ValueError("Invalid email format")


def _ensure_column(
    cur: sqlite3.Cursor, table_name: str, column_name: str, column_def: str
) -> None:
    """Safely add a column to an existing SQLite table if missing."""
    cur.execute(f"PRAGMA table_info({table_name});")
    existing_cols = {row["name"] for row in cur.fetchall()}
    if column_name not in existing_cols:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def};")


def _safe_json_loads(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


# ------------------------------------------------------------------
# SCHEMA INITIALIZATION & NON-DESTRUCTIVE MIGRATION
# ------------------------------------------------------------------
def init_db(db_path: Optional[str] = None) -> None:
    """Create all required tables, run additive migrations, and create indexes."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    # 1. USERS
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            resume_path TEXT
        );
        """
    )
    for col, col_def in [
        ("phone", "TEXT"),
        ("location", "TEXT"),
        ("linkedin_url", "TEXT"),
        ("target_role", "TEXT"),
        ("experience_years", "REAL DEFAULT 0"),
        ("education_level", "TEXT"),
        ("bio", "TEXT"),
        ("updated_at", "TEXT"),
    ]:
        _ensure_column(cur, "users", col, col_def)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")

    # 2. RESUME ANALYSIS
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resume_text TEXT NOT NULL,
            analysis_scores TEXT,
            strengths TEXT,
            weaknesses TEXT,
            identified_skills TEXT,
            recommended_skills TEXT,
            analyzed_at TEXT NOT NULL,
            analysis_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    for col, col_def in [
        ("analysis_scores", "TEXT"),
        ("strengths", "TEXT"),
        ("weaknesses", "TEXT"),
        ("identified_skills", "TEXT"),
        ("recommended_skills", "TEXT"),
        ("analysis_json", "TEXT"),
        ("overall_score", "REAL DEFAULT 0"),
        ("classification", "TEXT"),
        ("target_role", "TEXT"),
        ("content_hash", "TEXT"),
    ]:
        _ensure_column(cur, "resume_analysis", col, col_def)

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_resume_user ON resume_analysis (user_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_resume_hash ON resume_analysis (user_id, content_hash);"
    )

    # 3. STRENGTHS RESULTS (preserved legacy table)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS strengths_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            strengths TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    # 4. SKILLS ANALYSIS HISTORY
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS skills_analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            target_role TEXT NOT NULL,
            extracted_skills_json TEXT NOT NULL,
            missing_critical_json TEXT,
            missing_nice_json TEXT,
            recommendations_json TEXT,
            coverage_pct REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_skills_hist_user ON skills_analysis_history (user_id, created_at);"
    )

    # 5. IMPROVEMENT SUGGESTIONS
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS improvement_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            analysis_id INTEGER,
            suggestions_json TEXT NOT NULL,
            status_map_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_impr_user ON improvement_suggestions (user_id, updated_at);"
    )

    # 6. JOB RECOMMENDATIONS
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS job_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_title TEXT NOT NULL,
            company_name TEXT,
            location TEXT,
            job_description TEXT,
            job_url TEXT,
            match_percentage REAL DEFAULT 0,
            scraped_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    for col, col_def in [
        ("posted_date", "TEXT"),
        ("job_type", "TEXT"),
        ("remote_status", "TEXT"),
        ("experience_level", "TEXT"),
        ("salary_range", "TEXT"),
        ("applicants_count", "TEXT"),
        ("required_skills", "TEXT"),
        ("nice_to_have_skills", "TEXT"),
        ("qualifications", "TEXT"),
        ("responsibilities", "TEXT"),
        ("match_breakdown_json", "TEXT"),
        ("match_explanation", "TEXT"),
        ("application_tips_json", "TEXT"),
        ("source", "TEXT"),
        ("is_active", "INTEGER DEFAULT 1"),
    ]:
        _ensure_column(cur, "job_recommendations", col, col_def)

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_user ON job_recommendations (user_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_user_url ON job_recommendations (user_id, job_url);"
    )

    # 7. JOB PREFERENCES
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS job_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            desired_title TEXT,
            preferred_locations_json TEXT,
            remote_preference TEXT DEFAULT 'Any',
            experience_level TEXT DEFAULT 'Entry Level',
            job_types_json TEXT,
            min_salary INTEGER DEFAULT 0,
            industries_json TEXT,
            company_size TEXT DEFAULT 'Any',
            include_keywords_json TEXT,
            exclude_keywords_json TEXT,
            max_commute_mins INTEGER DEFAULT 60,
            visa_sponsorship INTEGER DEFAULT 0,
            preferred_companies TEXT,
            min_match_threshold REAL DEFAULT 60.0,
            schedule_frequency TEXT DEFAULT 'Disabled',
            email_notifications INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    # 8. JOB APPLICATIONS TRACKER
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS job_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            applied_date TEXT,
            updated_at TEXT NOT NULL,
            status_history_json TEXT,
            UNIQUE(user_id, job_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES job_recommendations(id) ON DELETE CASCADE
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_apps_user ON job_applications (user_id, status);"
    )

    # 9. SEARCH HISTORY
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query_title TEXT NOT NULL,
            locations TEXT,
            filters_json TEXT,
            jobs_found_count INTEGER DEFAULT 0,
            new_jobs_count INTEGER DEFAULT 0,
            searched_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_hist_user ON search_history (user_id, searched_at);"
    )

    # 10. USER ACTIVITY LOG & FEEDBACK
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            description TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity_log (user_id, created_at);"
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            comments TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# USER CRUD
# ------------------------------------------------------------------
def create_user(
    name: str, email: str, password_hash: str, resume_path: Optional[str] = None
) -> int:
    """Create a new user account and return its user_id."""
    init_db()
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name:
        raise ValueError("Name required")
    if not password_hash:
        raise ValueError("Password hash required")
    _validate_email(email)

    conn = get_connection()
    cur = conn.cursor()
    try:
        now = _now_iso()
        cur.execute(
            """
            INSERT INTO users (name, email, password_hash, registered_at, resume_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email, password_hash, now, resume_path, now),
        )
        conn.commit()
        uid = cur.lastrowid
        return int(uid)
    except sqlite3.IntegrityError as exc:
        raise ValueError("Email already registered") from exc
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a user record by integer ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user record by normalized email."""
    email = (email or "").strip().lower()
    _validate_email(email)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(
    user_id: int,
    resume_path: Optional[str] = None,
    clear_resume: bool = False,
    **profile_fields: Any,
) -> None:
    """Update user resume path and/or profile fields."""
    allowed_fields = {
        "name",
        "password_hash",
        "phone",
        "location",
        "linkedin_url",
        "target_role",
        "experience_years",
        "education_level",
        "bio",
    }
    fields: List[str] = []
    values: List[Any] = []

    if clear_resume:
        fields.append("resume_path = NULL")
    elif resume_path is not None:
        fields.append("resume_path = ?")
        values.append(resume_path)

    for key, val in profile_fields.items():
        if key in allowed_fields:
            fields.append(f"{key} = ?")
            values.append(val)

    if not fields:
        return

    fields.append("updated_at = ?")
    values.append(_now_iso())
    values.append(user_id)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
        tuple(values),
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# RESUME ANALYSIS CRUD
# ------------------------------------------------------------------
def save_resume_analysis(
    user_id: int,
    resume_text: str,
    analysis_json: str,
    analysis_scores: Optional[str] = None,
    strengths: Optional[str] = None,
    weaknesses: Optional[str] = None,
    identified_skills: Optional[str] = None,
    recommended_skills: Optional[str] = None,
    overall_score: float = 0.0,
    classification: Optional[str] = None,
    target_role: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> int:
    """Persist a resume analysis snapshot and return its ID."""
    init_db()
    resume_text = (resume_text or "").strip()
    analysis_json = (analysis_json or "").strip()
    if not resume_text:
        raise ValueError("resume_text required")
    if not analysis_json:
        raise ValueError("analysis_json required")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO resume_analysis (
            user_id, resume_text, analysis_scores, strengths, weaknesses,
            identified_skills, recommended_skills, analyzed_at, analysis_json,
            overall_score, classification, target_role, content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            resume_text,
            analysis_scores,
            strengths,
            weaknesses,
            identified_skills,
            recommended_skills,
            _now_iso(),
            analysis_json,
            float(overall_score or 0.0),
            classification,
            target_role,
            content_hash,
        ),
    )
    conn.commit()
    rid = int(cur.lastrowid)
    conn.close()
    return rid


def get_resume_analysis_for_user(user_id: int) -> List[Dict[str, Any]]:
    """Return all resume analysis records for a user ordered newest first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM resume_analysis
        WHERE user_id = ?
        ORDER BY analyzed_at DESC, id DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_resume_analysis(user_id: int) -> Optional[Dict[str, Any]]:
    """Return the newest resume analysis record for a user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM resume_analysis
        WHERE user_id = ?
        ORDER BY analyzed_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_cached_resume_analysis(
    user_id: int, content_hash: str
) -> Optional[Dict[str, Any]]:
    """Return a cached analysis matching user_id and content_hash where score > 0."""
    if not content_hash:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM resume_analysis
        WHERE user_id = ? AND content_hash = ? AND overall_score > 0
        ORDER BY analyzed_at DESC, id DESC
        LIMIT 1
        """,
        (user_id, content_hash),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_resume_analysis(analysis_id: int) -> None:
    """Delete a resume analysis record by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM resume_analysis WHERE id = ?", (analysis_id,))
    conn.commit()
    conn.close()


def delete_all_resumes_for_user(user_id: int) -> None:
    """Clear user's resume path and remove stored resume analyses."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET resume_path = NULL, updated_at = ? WHERE id = ?", (_now_iso(), user_id))
    cur.execute("DELETE FROM resume_analysis WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def save_strengths_result(user_id: int, strengths: str) -> None:
    """Legacy helper preserving strengths_results compatibility."""
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO strengths_results (user_id, strengths, generated_at)
        VALUES (?, ?, ?);
        """,
        (user_id, strengths, _now_iso()),
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# SKILLS HISTORY & IMPROVEMENT SUGGESTIONS CRUD
# ------------------------------------------------------------------
def save_skills_analysis(
    user_id: int,
    target_role: str,
    extracted_skills: Dict[str, Any],
    missing_critical: List[str],
    missing_nice: List[str],
    recommendations: List[Dict[str, Any]],
    coverage_pct: float,
) -> int:
    """Save a skills gap analysis snapshot for progress tracking."""
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO skills_analysis_history (
            user_id, target_role, extracted_skills_json, missing_critical_json,
            missing_nice_json, recommendations_json, coverage_pct, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            target_role,
            json.dumps(extracted_skills),
            json.dumps(missing_critical),
            json.dumps(missing_nice),
            json.dumps(recommendations),
            float(coverage_pct or 0.0),
            _now_iso(),
        ),
    )
    conn.commit()
    sid = int(cur.lastrowid)
    conn.close()
    return sid


def get_skills_analysis_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch user's past skills gap analyses."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM skills_analysis_history
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        item = dict(r)
        item["extracted_skills"] = _safe_json_loads(item.get("extracted_skills_json"), {})
        item["missing_critical"] = _safe_json_loads(item.get("missing_critical_json"), [])
        item["missing_nice"] = _safe_json_loads(item.get("missing_nice_json"), [])
        item["recommendations"] = _safe_json_loads(item.get("recommendations_json"), [])
        results.append(item)
    return results


def save_improvement_suggestions(
    user_id: int,
    suggestions: Dict[str, Any],
    analysis_id: Optional[int] = None,
    status_map: Optional[Dict[str, str]] = None,
) -> int:
    """Store generated improvement suggestions and interactive statuses."""
    init_db()
    now = _now_iso()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO improvement_suggestions (
            user_id, analysis_id, suggestions_json, status_map_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            analysis_id,
            json.dumps(suggestions),
            json.dumps(status_map or {}),
            now,
            now,
        ),
    )
    conn.commit()
    iid = int(cur.lastrowid)
    conn.close()
    return iid


def get_latest_improvement_suggestions(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch the most recent improvement plan for a user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM improvement_suggestions
        WHERE user_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["suggestions"] = _safe_json_loads(data.get("suggestions_json"), {})
    data["status_map"] = _safe_json_loads(data.get("status_map_json"), {})
    return data


def update_improvement_status_map(suggestion_id: int, status_map: Dict[str, str]) -> None:
    """Update the Applied / Not Relevant status map for an improvement plan."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE improvement_suggestions
        SET status_map_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (json.dumps(status_map), _now_iso(), suggestion_id),
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# JOB RECOMMENDATIONS CRUD
# ------------------------------------------------------------------
def upsert_job_recommendation(user_id: int, job: Dict[str, Any]) -> tuple[int, bool]:
    """Insert or update a job recommendation by (user_id, job_url) or title+company.

    Returns (job_id, is_new).
    """
    init_db()
    title = (job.get("job_title") or "Untitled Role").strip()
    company = (job.get("company_name") or "Unknown Company").strip()
    job_url = (job.get("job_url") or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    existing = None
    if job_url:
        cur.execute(
            "SELECT id FROM job_recommendations WHERE user_id = ? AND job_url = ?",
            (user_id, job_url),
        )
        existing = cur.fetchone()
    if not existing:
        cur.execute(
            """
            SELECT id FROM job_recommendations
            WHERE user_id = ? AND LOWER(job_title) = LOWER(?) AND LOWER(company_name) = LOWER(?)
            """,
            (user_id, title, company),
        )
        existing = cur.fetchone()

    now = _now_iso()
    breakdown_json = json.dumps(job.get("match_breakdown") or {})
    tips_json = json.dumps(job.get("application_tips") or {})
    req_skills = json.dumps(job.get("required_skills") or [])
    nice_skills = json.dumps(job.get("nice_to_have_skills") or [])
    quals = json.dumps(job.get("qualifications") or [])
    resps = json.dumps(job.get("responsibilities") or [])

    if existing:
        jid = int(existing["id"])
        cur.execute(
            """
            UPDATE job_recommendations
            SET location = ?, job_description = ?, match_percentage = ?, posted_date = ?,
                job_type = ?, remote_status = ?, experience_level = ?, salary_range = ?,
                applicants_count = ?, required_skills = ?, nice_to_have_skills = ?,
                qualifications = ?, responsibilities = ?, match_breakdown_json = ?,
                match_explanation = ?, application_tips_json = ?, source = ?,
                scraped_at = ?, is_active = 1
            WHERE id = ?
            """,
            (
                job.get("location") or "Not specified",
                job.get("job_description") or "",
                float(job.get("match_percentage") or 0.0),
                job.get("posted_date") or now[:10],
                job.get("job_type") or "Full-time",
                job.get("remote_status") or "On-site",
                job.get("experience_level") or "Mid Level",
                job.get("salary_range") or "Unavailable",
                str(job.get("applicants_count") or "Unavailable"),
                req_skills,
                nice_skills,
                quals,
                resps,
                breakdown_json,
                job.get("match_explanation") or "",
                tips_json,
                job.get("source") or "Public Job Feed",
                now,
                jid,
            ),
        )
        conn.commit()
        conn.close()
        return jid, False

    cur.execute(
        """
        INSERT INTO job_recommendations (
            user_id, job_title, company_name, location, job_description, job_url,
            match_percentage, scraped_at, posted_date, job_type, remote_status,
            experience_level, salary_range, applicants_count, required_skills,
            nice_to_have_skills, qualifications, responsibilities,
            match_breakdown_json, match_explanation, application_tips_json, source, is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            user_id,
            title,
            company,
            job.get("location") or "Not specified",
            job.get("job_description") or "",
            job_url,
            float(job.get("match_percentage") or 0.0),
            now,
            job.get("posted_date") or now[:10],
            job.get("job_type") or "Full-time",
            job.get("remote_status") or "On-site",
            job.get("experience_level") or "Mid Level",
            job.get("salary_range") or "Unavailable",
            str(job.get("applicants_count") or "Unavailable"),
            req_skills,
            nice_skills,
            quals,
            resps,
            breakdown_json,
            job.get("match_explanation") or "",
            tips_json,
            job.get("source") or "Public Job Feed",
        ),
    )
    conn.commit()
    jid = int(cur.lastrowid)
    conn.close()
    return jid, True


def _hydrate_job_row(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    item["required_skills"] = _safe_json_loads(item.get("required_skills"), [])
    item["nice_to_have_skills"] = _safe_json_loads(item.get("nice_to_have_skills"), [])
    item["qualifications"] = _safe_json_loads(item.get("qualifications"), [])
    item["responsibilities"] = _safe_json_loads(item.get("responsibilities"), [])
    item["match_breakdown"] = _safe_json_loads(item.get("match_breakdown_json"), {})
    item["application_tips"] = _safe_json_loads(item.get("application_tips_json"), {})
    return item


def get_job_recommendations_for_user(
    user_id: int, include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """Retrieve stored job recommendations for a user ordered by match score."""
    conn = get_connection()
    cur = conn.cursor()
    where_clause = "WHERE user_id = ?" if include_inactive else "WHERE user_id = ? AND is_active = 1"
    cur.execute(
        f"""
        SELECT * FROM job_recommendations
        {where_clause}
        ORDER BY match_percentage DESC, posted_date DESC, id DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [_hydrate_job_row(r) for r in rows]


def get_job_by_id(job_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single job recommendation by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM job_recommendations WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    return _hydrate_job_row(row) if row else None


def update_job_match_details(
    job_id: int,
    match_percentage: float,
    match_breakdown: Dict[str, Any],
    match_explanation: str,
    application_tips: Optional[Dict[str, Any]] = None,
) -> None:
    """Update computed match score, breakdown, explanation, and tips for a job."""
    conn = get_connection()
    cur = conn.cursor()
    if application_tips is not None:
        cur.execute(
            """
            UPDATE job_recommendations
            SET match_percentage = ?, match_breakdown_json = ?, match_explanation = ?,
                application_tips_json = ?
            WHERE id = ?
            """,
            (
                float(match_percentage),
                json.dumps(match_breakdown),
                match_explanation,
                json.dumps(application_tips),
                job_id,
            ),
        )
    else:
        cur.execute(
            """
            UPDATE job_recommendations
            SET match_percentage = ?, match_breakdown_json = ?, match_explanation = ?
            WHERE id = ?
            """,
            (float(match_percentage), json.dumps(match_breakdown), match_explanation, job_id),
        )
    conn.commit()
    conn.close()


def deactivate_job_for_user(user_id: int, job_id: int) -> None:
    """Mark a job as Not Interested (hidden from active recommendations)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE job_recommendations SET is_active = 0 WHERE id = ? AND user_id = ?",
        (job_id, user_id),
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# JOB PREFERENCES CRUD
# ------------------------------------------------------------------
DEFAULT_JOB_PREFERENCES: Dict[str, Any] = {
    "desired_title": "Software Developer",
    "preferred_locations": ["Remote", "Bengaluru", "New York"],
    "remote_preference": "Any",
    "experience_level": "Entry Level",
    "job_types": ["Full-time"],
    "min_salary": 0,
    "industries": ["Technology", "Software & AI"],
    "company_size": "Any",
    "include_keywords": [],
    "exclude_keywords": [],
    "max_commute_mins": 60,
    "visa_sponsorship": False,
    "preferred_companies": "",
    "min_match_threshold": 60.0,
    "schedule_frequency": "Disabled",
    "email_notifications": False,
}


def save_job_preferences(user_id: int, prefs: Dict[str, Any]) -> None:
    """Upsert job search preferences for a user."""
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        """
        INSERT INTO job_preferences (
            user_id, desired_title, preferred_locations_json, remote_preference,
            experience_level, job_types_json, min_salary, industries_json, company_size,
            include_keywords_json, exclude_keywords_json, max_commute_mins,
            visa_sponsorship, preferred_companies, min_match_threshold,
            schedule_frequency, email_notifications, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            desired_title = excluded.desired_title,
            preferred_locations_json = excluded.preferred_locations_json,
            remote_preference = excluded.remote_preference,
            experience_level = excluded.experience_level,
            job_types_json = excluded.job_types_json,
            min_salary = excluded.min_salary,
            industries_json = excluded.industries_json,
            company_size = excluded.company_size,
            include_keywords_json = excluded.include_keywords_json,
            exclude_keywords_json = excluded.exclude_keywords_json,
            max_commute_mins = excluded.max_commute_mins,
            visa_sponsorship = excluded.visa_sponsorship,
            preferred_companies = excluded.preferred_companies,
            min_match_threshold = excluded.min_match_threshold,
            schedule_frequency = excluded.schedule_frequency,
            email_notifications = excluded.email_notifications,
            updated_at = excluded.updated_at
        """,
        (
            user_id,
            (prefs.get("desired_title") or "Software Developer").strip(),
            json.dumps(prefs.get("preferred_locations") or []),
            prefs.get("remote_preference") or "Any",
            prefs.get("experience_level") or "Entry Level",
            json.dumps(prefs.get("job_types") or ["Full-time"]),
            int(prefs.get("min_salary") or 0),
            json.dumps(prefs.get("industries") or []),
            prefs.get("company_size") or "Any",
            json.dumps(prefs.get("include_keywords") or []),
            json.dumps(prefs.get("exclude_keywords") or []),
            int(prefs.get("max_commute_mins") or 60),
            1 if prefs.get("visa_sponsorship") else 0,
            prefs.get("preferred_companies") or "",
            float(prefs.get("min_match_threshold") if prefs.get("min_match_threshold") is not None else 60.0),
            prefs.get("schedule_frequency") or "Disabled",
            1 if prefs.get("email_notifications") else 0,
            now,
        ),
    )
    conn.commit()
    conn.close()


def get_job_preferences(user_id: int) -> Dict[str, Any]:
    """Return user's saved job preferences or defaults."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM job_preferences WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return dict(DEFAULT_JOB_PREFERENCES)

    data = dict(row)
    return {
        "desired_title": data.get("desired_title") or DEFAULT_JOB_PREFERENCES["desired_title"],
        "preferred_locations": _safe_json_loads(data.get("preferred_locations_json"), []),
        "remote_preference": data.get("remote_preference") or "Any",
        "experience_level": data.get("experience_level") or "Entry Level",
        "job_types": _safe_json_loads(data.get("job_types_json"), ["Full-time"]),
        "min_salary": int(data.get("min_salary") or 0),
        "industries": _safe_json_loads(data.get("industries_json"), []),
        "company_size": data.get("company_size") or "Any",
        "include_keywords": _safe_json_loads(data.get("include_keywords_json"), []),
        "exclude_keywords": _safe_json_loads(data.get("exclude_keywords_json"), []),
        "max_commute_mins": int(data.get("max_commute_mins") or 60),
        "visa_sponsorship": bool(data.get("visa_sponsorship")),
        "preferred_companies": data.get("preferred_companies") or "",
        "min_match_threshold": float(data.get("min_match_threshold") if data.get("min_match_threshold") is not None else 60.0),
        "schedule_frequency": data.get("schedule_frequency") or "Disabled",
        "email_notifications": bool(data.get("email_notifications")),
        "updated_at": data.get("updated_at"),
    }


def reset_job_preferences(user_id: int) -> Dict[str, Any]:
    """Reset user's job preferences to defaults and persist."""
    defaults = dict(DEFAULT_JOB_PREFERENCES)
    save_job_preferences(user_id, defaults)
    return defaults


# ------------------------------------------------------------------
# JOB APPLICATIONS & SEARCH HISTORY & ACTIVITY LOG
# ------------------------------------------------------------------
def upsert_job_application(
    user_id: int, job_id: int, status: str, notes: str = ""
) -> None:
    """Save or update application status ('Saved', 'Applied', 'Interviewing', 'Rejected')."""
    init_db()
    now = _now_iso()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM job_applications WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    )
    existing = cur.fetchone()
    history = []
    applied_date = now if status == "Applied" else None

    if existing:
        history = _safe_json_loads(existing["status_history_json"], [])
        applied_date = existing["applied_date"] or (now if status == "Applied" else None)

    history.append({"status": status, "timestamp": now, "notes": notes})

    cur.execute(
        """
        INSERT INTO job_applications (
            user_id, job_id, status, notes, applied_date, updated_at, status_history_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, job_id) DO UPDATE SET
            status = excluded.status,
            notes = excluded.notes,
            applied_date = COALESCE(job_applications.applied_date, excluded.applied_date),
            updated_at = excluded.updated_at,
            status_history_json = excluded.status_history_json
        """,
        (user_id, job_id, status, notes, applied_date, now, json.dumps(history)),
    )
    conn.commit()
    conn.close()


def get_job_applications_for_user(user_id: int) -> List[Dict[str, Any]]:
    """Return tracked job applications joined with job details."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id AS app_id, a.status, a.notes, a.applied_date, a.updated_at AS app_updated_at,
               a.status_history_json, j.*
        FROM job_applications a
        JOIN job_recommendations j ON a.job_id = j.id
        WHERE a.user_id = ?
        ORDER BY a.updated_at DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    items = []
    for r in rows:
        item = _hydrate_job_row(r)
        item["status_history"] = _safe_json_loads(item.get("status_history_json"), [])
        items.append(item)
    return items


def delete_job_application(user_id: int, job_id: int) -> None:
    """Remove a job from Saved / Tracked list."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM job_applications WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    )
    conn.commit()
    conn.close()


def save_search_history(
    user_id: int,
    query_title: str,
    locations: str,
    filters: Dict[str, Any],
    jobs_found_count: int,
    new_jobs_count: int,
) -> int:
    """Record a job search execution in search_history."""
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO search_history (
            user_id, query_title, locations, filters_json,
            jobs_found_count, new_jobs_count, searched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            query_title,
            locations,
            json.dumps(filters),
            int(jobs_found_count),
            int(new_jobs_count),
            _now_iso(),
        ),
    )
    conn.commit()
    sid = int(cur.lastrowid)
    conn.close()
    return sid


def get_search_history_for_user(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve recent job search history for quick re-run."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM search_history
        WHERE user_id = ?
        ORDER BY searched_at DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        item = dict(r)
        item["filters"] = _safe_json_loads(item.get("filters_json"), {})
        results.append(item)
    return results


def log_activity(
    user_id: int,
    activity_type: str,
    description: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a user activity item for the dashboard Recent Activity feed."""
    try:
        init_db()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_activity_log (
                user_id, activity_type, description, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                activity_type,
                description,
                json.dumps(metadata or {}),
                _now_iso(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_recent_activities(user_id: int, limit: int = 8) -> List[Dict[str, Any]]:
    """Fetch recent activity entries for the user dashboard."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM user_activity_log
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_user_feedback(
    user_id: Optional[int], category: str, rating: int, comments: str
) -> int:
    """Save user feedback submission."""
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO user_feedback (user_id, category, rating, comments, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, category, int(rating), comments.strip(), _now_iso()),
    )
    conn.commit()
    fid = int(cur.lastrowid)
    conn.close()
    return fid


def get_dashboard_stats(user_id: int) -> Dict[str, Any]:
    """Compute summary metrics for the user dashboard."""
    user = get_user_by_id(user_id)
    latest_analysis = get_latest_resume_analysis(user_id)
    jobs = get_job_recommendations_for_user(user_id)
    apps = get_job_applications_for_user(user_id)

    has_resume = bool(
        (user and user.get("resume_path")) or latest_analysis
    )
    last_score = None
    last_analysis_date = None
    if latest_analysis:
        last_analysis_date = latest_analysis.get("analyzed_at")
        score_val = latest_analysis.get("overall_score") or 0
        if score_val > 0:
            last_score = round(float(score_val), 1)
        else:
            parsed = _safe_json_loads(latest_analysis.get("analysis_json"), {})
            if isinstance(parsed, dict) and parsed.get("score"):
                try:
                    last_score = float(parsed["score"])
                except Exception:
                    last_score = None

    return {
        "has_resume": has_resume,
        "resume_path": user.get("resume_path") if user else None,
        "last_analysis_date": last_analysis_date,
        "last_score": last_score,
        "total_jobs": len(jobs),
        "saved_jobs_count": len(apps),
        "applied_jobs_count": sum(1 for a in apps if a.get("status") == "Applied"),
    }
