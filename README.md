# AI-Powered Resume Analysis & Intelligent Job Recommendation System

A full-stack Python & Streamlit career intelligence platform delivering secure user management, PDF/DOCX resume parsing, multi-provider AI resume scoring & strengths/weaknesses diagnostics, 6-category skills gap analysis, personalized before/after resume coaching, PDF report export, compliant multi-source job discovery, weighted resume–job matching, and application tracking.

---

## Key Features

### Milestone 1 – Foundation, Authentication & Resume Management
- **User Registration & Authentication:** Bcrypt password hashing, strict input/password complexity validation (`8+ chars`, uppercase, lowercase, digit, special character), duplicate email prevention, session persistence, profile editing, and password change.
- **SQLite Persistence & Non-Destructive Migrations:** 10 structured tables with foreign keys, unique constraints, and indexes (`users`, `resume_analysis`, `strengths_results`, `skills_analysis_history`, `improvement_suggestions`, `job_recommendations`, `job_preferences`, `job_applications`, `search_history`, `user_activity_log`, `user_feedback`).
- **Resume Upload & Extraction:** Accepts `.pdf` and `.docx` up to 5 MB with magic-byte validation, corrupted/encrypted file detection, multi-page `pdfplumber`/`PyPDF2` extraction, DOCX paragraph + table extraction, optional OCR fallback guard, section detection, and replace/delete support.
- **User Dashboard:** Personalized welcome banner, KPI summary cards, Recent Activity feed, next-step guidance, and unified sidebar navigation.

### Milestone 2 – AI-Powered Resume Analysis & Coaching
- **Multi-Provider LLM Service:** Supports Google Gemini (`langchain-google-genai` / `google-genai`), OpenAI, and local Ollama via `.env` with LangChain `PromptTemplate`s, `tenacity` retries, JSON response parsing, token/cost tracking, and an automatic **Evidence-Based Demo Mode** when no live API key is configured.
- **Weighted Resume Scoring System:** Evaluates resumes on five weighted criteria:
  - Completeness (`25%`)
  - Content Quality (`30%`)
  - Formatting & Structure (`15%`)
  - Keyword Relevance (`20%`)
  - Experience Depth (`10%`)
  - Classifications: **Excellent** (`90–100`), **Good** (`75–89`), **Average** (`60–74`), **Needs Improvement** (`< 60`).
- **Strengths & Weaknesses Analyzer:** Extracts 5–7 strengths and 5–7 weaknesses with category tags, severity levels (`minor`, `moderate`, `critical`), resume evidence/location, confidence scores (`0–100%`), and hash-based caching.
- **Skills Gap Analysis:** Classifies skills across 6 categories (Programming Languages, Frameworks, Tools, Soft Skills, Domain Knowledge, Certifications), detects experience years, compares against target-role standards, visualizes gaps with charts, and recommends 5–10 prioritized learning resources.
- **Interactive Analysis Results & PDF Export:** Circular SVG score gauge, component score bars, filterable skill chips, and downloadable multi-page PDF reports (ReportLab + Matplotlib charts).
- **Improvement Coach:** High-impact vs. quick-win suggestions with estimated score boost, before/after bullet rewrites from actual resume lines, section-by-section tips, and persistent `Applied` / `Not Relevant` tracking.

### Milestone 3 – Job Discovery, Matching & Application Tracking
- **Compliant Multi-Source Job Collection:** Supports Remotive, The Muse, and Arbeitnow public REST APIs, optional Terms-of-Service-compliant Selenium WebDriver pooling (`ENABLE_SELENIUM_SCRAPER=true`), and an offline-resilient fallback catalog when network access is restricted.
- **Exact Weighted Resume–Job Matching:**
  - Skills Match (`50%`)
  - Experience Match (`25%`)
  - Education Match (`15%`)
  - Responsibilities Match (`10%`)
- **Job Search Customization:** Save/load/reset desired title, multi-location, remote mode, seniority, job types, minimum salary, industries, include/exclude keywords, visa sponsorship, and search history quick re-runs.
- **Recommendations Dashboard & Tracker:** Real-time sidebar filters, multi-criteria sorting, 20-per-page pagination, side-by-side Job Comparison, AI Application Tips & Customized Cover Letters, and `Saved` / `Applied` / `Interviewing` / `Rejected` status tracking.

---

## Technology Stack
- **Frontend:** Streamlit, Custom CSS, Matplotlib, Pandas
- **Backend & AI:** Python 3.13 (3.9+ compatible), LangChain (`langchain`, `langchain-core`, `langchain-google-genai`), `google-genai`, `openai`, `tenacity`
- **Document & PDF Processing:** `pdfplumber`, `PyPDF2`, `python-docx`, `pypdfium2`, `reportlab`, `Pillow`
- **Security & Database:** `bcrypt`, `sqlite3` (with `pymongo` dependency ready for optional cloud MongoDB extensions)
- **Job Sources & Scraping:** `requests`, `selenium`

---

## Project Architecture

```text
infosysproject/
├── app.py                          # Primary Streamlit entry point
├── requirements.txt                # Clean UTF-8 Python dependencies
├── .env.example                    # Environment configuration template
├── .gitignore
├── .streamlit/config.toml          # Light/clean UI theme configuration
├── PROJECT_AUDIT.md                # Pre- & post-implementation milestone audit
├── IMPLEMENTATION_PROGRESS.md      # Task-by-task execution tracker
├── README.md
├── backend/
│   ├── auth.py                     # Registration, login, bcrypt, session & profile helpers
│   ├── resume_parser.py            # PDF/DOCX extraction, cleaning, metadata & OCR guard
│   ├── resume_extractor.py         # Backwards-compatible parser wrapper
│   ├── llm_analyzer.py             # Multi-provider LLM service, prompts, retries & cost tracking
│   ├── resume_analyzer.py          # Strengths/weaknesses & full analysis orchestrator
│   ├── skills_analyzer.py          # 6-category skill extraction & skills gap roadmap
│   ├── skills_gap_analyzer.py      # Compatibility wrapper
│   ├── resume_scorer.py            # Weighted 5-component resume scoring engine
│   ├── improvement_suggestions.py  # Actionable suggestions, before/after rewrites & DB tracking
│   ├── improvement_analyzer.py     # Compatibility wrapper
│   ├── scraper.py                  # Selenium pool + compliant public API job sources
│   ├── job_search.py               # Multi-source job search pipeline & deduplication
│   ├── job_matcher.py              # Requirement extraction & 50/25/15/10 weighted matching
│   ├── job_filter.py               # Multi-criteria filtering & threshold enforcement
│   └── job_recommendations.py      # Ranking, tips, cover letter drafts, comparison & tracking
├── frontend/
│   ├── app.py                      # Frontend router
│   ├── login.py                    # Sign-in UI
│   ├── registration.py             # Registration UI with live password strength indicator
│   ├── dashboard.py                # Main sidebar navigation & Overview cockpit
│   ├── profile.py                  # Profile editing & password management
│   ├── upload_resume.py            # Resume upload, validation, preview & extraction UI
│   ├── resume_upload.py            # Compatibility wrapper
│   ├── analysis.py                 # Gauge, component bars, cards, skill filters & PDF export
│   ├── analysis_page.py            # Compatibility wrapper
│   ├── skills_gap_page.py          # Skills gap charts & prioritized learning cards
│   ├── improvement.py              # Before/after diffs, section tabs & status tracking UI
│   ├── improvement_page.py         # Compatibility wrapper
│   ├── job_preferences.py          # Search customization, progress bar & search history
│   ├── job_recommendations.py      # Job cards, filters, comparison & application tracker
│   └── settings.py                 # LLM status/tester, FAQ, tutorial & user feedback
├── utils/
│   ├── database.py                 # SQLite schema, migrations & full CRUD helpers
│   ├── validators.py               # Regex, password complexity & file signature validators
│   ├── security.py                 # Bcrypt hashing, content hashing & secret masking
│   ├── helpers.py                  # Custom CSS, circular SVG gauge & HTML chip helpers
│   ├── logger.py                   # Rotating file & console logging
│   └── pdf_generator.py            # ReportLab + Matplotlib PDF report generator
├── data/
│   ├── app.db                      # SQLite database (auto-initialized)
│   ├── resumes/                    # Uploaded user resumes
│   └── reports/                    # Generated PDF reports
├── tests/
│   ├── test_auth.py
│   ├── test_database.py
│   ├── test_resume_parser.py
│   ├── test_resume_analysis.py
│   ├── test_job_matching.py
│   ├── test_integration.py
│   └── test_ui_app.py
└── docs/
    ├── architecture.md
    ├── database_schema.md
    ├── user_manual.md
    └── testing_report.md
```

---

## Installation & Setup

### 1. Prerequisites
- Python **3.9 or higher** (verified on Python 3.13.1)
- Git (optional, for version control)

### 2. Create & Activate Virtual Environment
```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your credentials (never commit `.env`):
```powershell
Copy-Item .env.example .env
```
Key variables in `.env`:
- `LLM_PROVIDER`: `gemini`, `openai`, `ollama`, or `demo`
- `GEMINI_API_KEY`: Your Google Gemini API key (if using Gemini)
- `OPENAI_API_KEY`: Your OpenAI API key (if using OpenAI)
- `LLM_MODEL`: e.g. `gemini-2.5-flash` or `gpt-4o-mini`
- `ENABLE_SELENIUM_SCRAPER`: `false` by default (uses compliant public job APIs; set `true` only if Chrome/ChromeDriver is installed locally)

> **Note:** If no live LLM API key is configured, the platform automatically runs in **Evidence-Based Demo Mode**, calculating all scores, strengths, weaknesses, skills gaps, and job match metrics deterministically from your actual resume text.

### 5. Initialize Database & Run Application
```powershell
streamlit run app.py
```
The SQLite database (`data/app.db`) is automatically initialized and migrated on startup.

---

## Running Automated Tests
Run the full unit, integration, and Streamlit UI smoke test suite:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

---

## Troubleshooting
- **Image-Based / Scanned PDF Warning:** Scanned PDFs contain images rather than selectable text. Upload a text-based PDF exported from Word/Google Docs/LaTeX or a `.docx` file.
- **API Rate Limits / Missing Key:** Check **Settings → Test LLM API Connection** inside the app. When API quotas are exceeded or keys are absent, the platform cleanly falls back to Evidence-Based Demo Mode without crashing.
- **Job Search Offline Behavior:** If public APIs (Remotive, The Muse, Arbeitnow) are unreachable due to firewall/offline conditions, the system seamlessly provides clearly labeled fallback job listings so matching and application tracking continue uninterrupted.

---

## Deployment (Streamlit Community Cloud)
1. Push the repository (excluding `.env`, `.venv/`, and `data/app.db`) to GitHub.
2. Connect the repository in [Streamlit Community Cloud](https://share.streamlit.io/), setting main file path to `app.py`.
3. Add your secrets (`GEMINI_API_KEY`, `LLM_PROVIDER`, etc.) in the Streamlit Cloud **App Settings → Secrets** panel.
4. For persistent multi-user cloud storage beyond ephemeral SQLite files, configure a managed database URL via environment secrets.
