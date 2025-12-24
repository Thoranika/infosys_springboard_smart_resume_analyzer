import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

# -------------------------------------------------
# PATHS
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "app.db")

# Email pattern for validation
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# -------------------------------------------------
# CONNECTION
# -------------------------------------------------
def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the SQLite database.
    Row factory returns rows like dictionaries.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    """Current UTC time as string."""
    return datetime.utcnow().isoformat(timespec="seconds")


def _validate_email(email: str):
    if not EMAIL_REGEX.match(email or ""):
        raise ValueError("Invalid email format")


# -------------------------------------------------
# DATABASE INIT
# -------------------------------------------------
def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            resume_path TEXT
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_email
        ON users (email);
    """)

    # RESUME ANALYSIS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resume_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resume_text TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            analyzed_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_resume_user
        ON resume_analysis (user_id);
    """)

    # STRENGTH RESULTS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strengths_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            strengths TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()


# -------------------------------------------------
# USER FUNCTIONS
# -------------------------------------------------
def create_user(name: str, email: str, password_hash: str, resume_path: str = None) -> int:
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name:
        raise ValueError("Name required")

    _validate_email(email)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (name, email, password_hash, registered_at, resume_path)
        VALUES (?, ?, ?, ?, ?)
    """, (name, email, password_hash, _now_iso(), resume_path))

    conn.commit()
    uid = cur.lastrowid
    conn.close()

    return uid


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    email = (email or "").strip().lower()
    _validate_email(email)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(user_id: int, resume_path: str | None = None) -> None:
    fields = []
    values = []

    if resume_path is not None:
        fields.append("resume_path = ?")
        values.append(resume_path)

    if not fields:
        return

    values.append(user_id)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
        tuple(values)
    )
    conn.commit()
    conn.close()


# -------------------------------------------------
# RESUME ANALYSIS FUNCTIONS
# -------------------------------------------------
def save_resume_analysis(user_id: int, resume_text: str, analysis_json: str) -> int:
    resume_text = (resume_text or "").strip()
    analysis_json = (analysis_json or "").strip()

    if not resume_text:
        raise ValueError("resume_text required")

    if not analysis_json:
        raise ValueError("analysis_json required")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO resume_analysis (
            user_id,
            resume_text,
            analysis_json,
            analyzed_at
        )
        VALUES (?, ?, ?, ?)
    """, (user_id, resume_text, analysis_json, _now_iso()))

    conn.commit()
    rid = cur.lastrowid
    conn.close()

    return rid


def get_resume_analysis_for_user(user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM resume_analysis
        WHERE user_id = ?
        ORDER BY analyzed_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]


def get_latest_resume_analysis(user_id: int) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM resume_analysis
        WHERE user_id = ?
        ORDER BY analyzed_at DESC
        LIMIT 1
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


# -------------------------------------------------
# DELETE ANALYSIS
# -------------------------------------------------
def delete_resume_analysis(analysis_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM resume_analysis WHERE id = ?", (analysis_id,))
    conn.commit()
    conn.close()


# -------------------------------------------------
# STRENGTHS RESULT SAVE
# -------------------------------------------------
def save_strengths_result(user_id: int, strengths: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO strengths_results (user_id, strengths, generated_at)
        VALUES (?, ?, ?);
    """, (user_id, strengths, _now_iso()))
    conn.commit()
    conn.close()


def get_job_recommendations_for_user(user_id):
    """Compatibility wrapper used by frontend/dashboard.py."""
    # try existing candidate functions first
    for name in (
        "get_job_recommendations",
        "fetch_job_recommendations_for_user",
        "get_recommended_jobs_for_user",
        "get_jobs_for_user",
        "query_job_recommendations",
    ):
        fn = globals().get(name)
        if callable(fn):
            return fn(user_id)

    # fallback: simple DB query if DB_PATH and sqlite3 are available
    try:
        import sqlite3
        db = globals().get("DB_PATH") or globals().get("DATABASE_PATH") or "app.db"
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT id, title, company, created_at FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (user_id,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        result = [dict(zip(cols, r)) for r in rows]
        conn.close()
        return result
    except Exception:
        return []
