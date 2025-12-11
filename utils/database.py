import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # project root
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)  # create "data" folder if missing

DB_PATH = os.path.join(DATA_DIR, "app.db")

# Email pattern for validation
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ============================================================
# 2. BASIC HELPERS
# ============================================================

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


def _validate_email(email: str) -> None:
    """Raise ValueError if email format is wrong."""
    if not EMAIL_REGEX.match(email or ""):
        raise ValueError(f"Invalid email format: {email!r}")


# ============================================================
# 3. CREATE TABLES + INDEXES
# ============================================================

def init_db() -> None:
    """
    Create all tables and indexes if they do not exist.
    Call this once (for example in main.py).
    """
    conn = get_connection()
    cur = conn.cursor()

    # ---------- USERS TABLE ----------
    # Fields: id, name, email, password_hash, registered_at, resume_path
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

    # Index on email for fast search
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_users_email
        ON users (email);
        """
    )

    # ---------- RESUME ANALYSIS TABLE ----------
    # Fields: id, user_id, resume_text, analysis_scores, strengths,
    # weaknesses, identified_skills, recommended_skills, analyzed_at
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
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )

    # Index on user_id
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resume_user
        ON resume_analysis (user_id);
        """
    )

    # ---------- JOB RECOMMENDATIONS TABLE ----------
    # Fields: id, user_id, job_title, company_name, location,
    # job_description, job_url, match_percentage, scraped_at
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
            match_percentage REAL,
            scraped_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )

    # Index on user_id
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_jobs_user
        ON job_recommendations (user_id);
        """
    )

    conn.commit()
    conn.close()


# ============================================================
# 4. CRUD FUNCTIONS – USERS
# ============================================================

def create_user(
    name: str,
    email: str,
    password_hash: str,
    resume_path: Optional[str] = None,
) -> int:
    """
    CREATE: insert a new user.
    Returns: new user id.
    Validation:
      - name not empty
      - email format correct
      - email unique (db unique + error handling)
    """
    name = (name or "").strip()
    email = (email or "").strip().lower()

    if not name:
        raise ValueError("Name cannot be empty.")

    _validate_email(email)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (name, email, password_hash, registered_at, resume_path)
            VALUES (?, ?, ?, ?, ?);
            """,
            (name, email, password_hash, _now_iso(), resume_path),
        )
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        # raised when email is not unique
        conn.rollback()
        raise ValueError(f"User with email {email!r} already exists.") from e
    finally:
        conn.close()

    return user_id


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """READ: get one user by id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """READ: get one user by email (validated)."""
    email = (email or "").strip().lower()
    _validate_email(email)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?;", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(
    user_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    resume_path: Optional[str] = None,
) -> None:
    """
    UPDATE: change user fields.
    Any parameter that is None will not be updated.
    """
    fields = []
    values: List[Any] = []

    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("Name cannot be empty.")
        fields.append("name = ?")
        values.append(name)

    if email is not None:
        email = email.strip().lower()
        _validate_email(email)
        fields.append("email = ?")
        values.append(email)

    if resume_path is not None:
        fields.append("resume_path = ?")
        values.append(resume_path)

    if not fields:
        return  # nothing to update

    values.append(user_id)
    sql = "UPDATE users SET " + ", ".join(fields) + " WHERE id = ?;"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, tuple(values))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        # email unique constraint
        raise ValueError("Email already used by another user.") from e
    finally:
        conn.close()


def delete_user(user_id: int) -> None:
    """
    DELETE: remove a user.
    Note: related resume_analysis and job_recommendations
    are NOT deleted automatically here (no CASCADE).
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()
    conn.close()


# ============================================================
# 5. CRUD FUNCTIONS – RESUME ANALYSIS
# ============================================================

def create_resume_analysis(
    user_id: int,
    resume_text: str,
    analysis_scores: Optional[str] = None,
    strengths: Optional[str] = None,
    weaknesses: Optional[str] = None,
    identified_skills: Optional[str] = None,
    recommended_skills: Optional[str] = None,
) -> int:
    """
    CREATE: insert new resume analysis.
    resume_text must not be empty.
    Complex fields can be JSON or text (your choice).
    """
    resume_text = (resume_text or "").strip()
    if not resume_text:
        raise ValueError("resume_text cannot be empty.")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO resume_analysis (
            user_id,
            resume_text,
            analysis_scores,
            strengths,
            weaknesses,
            identified_skills,
            recommended_skills,
            analyzed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
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
        ),
    )
    conn.commit()
    analysis_id = cur.lastrowid
    conn.close()
    return analysis_id


def get_resume_analysis_for_user(user_id: int) -> List[Dict[str, Any]]:
    """READ: list all analyses for one user (latest first)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM resume_analysis
        WHERE user_id = ?
        ORDER BY analyzed_at DESC;
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_resume_analysis(analysis_id: int) -> None:
    """DELETE: remove one analysis row."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM resume_analysis WHERE id = ?;", (analysis_id,))
    conn.commit()
    conn.close()


# ============================================================
# 6. CRUD FUNCTIONS – JOB RECOMMENDATIONS
# ============================================================

def create_job_recommendation(
    user_id: int,
    job_title: str,
    company_name: Optional[str] = None,
    location: Optional[str] = None,
    job_description: Optional[str] = None,
    job_url: Optional[str] = None,
    match_percentage: Optional[float] = None,
) -> int:
    """
    CREATE: insert job recommendation.
    job_title must not be empty.
    """
    job_title = (job_title or "").strip()
    if not job_title:
        raise ValueError("job_title cannot be empty.")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO job_recommendations (
            user_id,
            job_title,
            company_name,
            location,
            job_description,
            job_url,
            match_percentage,
            scraped_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            user_id,
            job_title,
            company_name,
            location,
            job_description,
            job_url,
            match_percentage,
            _now_iso(),
        ),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def get_job_recommendations_for_user(
    user_id: int,
    min_match: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    READ: list all jobs for a user.
    If min_match is given, only jobs with that match% or higher are returned.
    """
    conn = get_connection()
    cur = conn.cursor()

    if min_match is not None:
        cur.execute(
            """
            SELECT * FROM job_recommendations
            WHERE user_id = ? AND (match_percentage IS NULL OR match_percentage >= ?)
            ORDER BY match_percentage DESC, scraped_at DESC;
            """,
            (user_id, min_match),
        )
    else:
        cur.execute(
            """
            SELECT * FROM job_recommendations
            WHERE user_id = ?
            ORDER BY scraped_at DESC;
            """,
            (user_id,),
        )

    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_job_recommendation(job_id: int) -> None:
    """DELETE: remove one job recommendation."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM job_recommendations WHERE id = ?;", (job_id,))
    conn.commit()
    conn.close()
