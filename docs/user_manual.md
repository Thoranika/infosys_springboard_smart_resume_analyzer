# End-User Manual

Welcome to the **AI-Powered Resume Analysis & Intelligent Job Recommendation System**.

---

## 1. Account Registration & Sign In
1. Launch the app (`streamlit run app.py`) to open the **Sign In** screen.
2. New users click **Create a new account** to open Registration:
   - Enter your **Full Name** (letters only).
   - Enter a valid **Email Address**.
   - Create a strong **Password** (minimum 8 characters, including uppercase, lowercase, number, and special character — a live strength bar guides you).
   - Confirm your password and click **Register Account**.
3. Log in with your registered email and password to enter the **Dashboard**.

## 2. Profile & Dashboard Overview
- **Overview:** Displays your resume upload status, latest score, last analysis date, total matched jobs, next-step action cards, and recent activity feed.
- **My Profile:** Update your Target Job Role, Years of Experience, Highest Education Level, Location, LinkedIn URL, and Career Bio. Having accurate experience and education values significantly improves Milestone 3 job match accuracy. You can also change your password here.

## 3. Uploading & Extracting Your Resume
1. Navigate to **Upload Resume** in the left sidebar.
2. Select a `.pdf` or `.docx` file (up to 5 MB).
3. Click **Upload & Extract Resume**:
   - The app validates file extension, size, and container integrity.
   - Text is extracted across all pages/tables and cleaned.
   - Detected resume sections (Contact, Summary, Experience, Education, Skills, Projects, Certifications) and word count are displayed.
4. You can inspect extracted text, upload a replacement file, or delete your stored resume at any time.

## 4. AI Resume Analysis & PDF Report
1. Navigate to **Resume Analysis**.
2. Confirm or adjust your **Target Job Role** (auto-detected from your resume).
3. Click **Analyze Resume** (or **Re-analyze** to bypass cache).
4. Inspect:
   - **Circular Overall Score Gauge** (`0–100`) & classification tier (`Excellent`, `Good`, `Average`, `Needs Improvement`).
   - **Component Score Bars** for Completeness (`25%`), Content Quality (`30%`), Formatting (`15%`), Keyword Relevance (`20%`), and Experience (`10%`).
   - **Key Strengths** and **Weaknesses** cards with severity tags and resume evidence.
   - **Filterable Skills Tags** and missing skills summary.
5. Click **Download PDF Report** to save a formatted multi-page PDF with embedded Matplotlib charts.

## 5. Skills Gap Analysis & Resume Improvement Coach
- **Skills Gap:** View your 6-category skill inventory, Present vs. Missing bar/category charts, role coverage percentage, and 5–10 prioritized learning recommendations with direct documentation/course links.
- **Improve Resume:** Review High-Impact changes and Quick Wins with estimated score gains, inspect side-by-side **Before vs. After** rewrites of your actual bullets, browse section-by-section tips, and mark suggestions as **Applied** or **Not Relevant** (persisted across sessions).

## 6. Job Search Customization, Recommendations & Tracking
1. Open **Job Preferences** to configure Desired Job Title, Preferred Locations, Remote Preference, Experience Level, Job Types, Minimum Salary, Industries, Company Size, and Advanced Include/Exclude Keywords.
2. Click **Save Preferences** or **Find Jobs Now** to search compliant job feeds and score each job against your resume.
3. Open **Job Recommendations**:
   - Use the **Sidebar Filters** (Match %, Work Mode, Location, Job Type, Seniority, Posted Date, Salary) and **Sort By** dropdown in real time.
   - Browse paginated cards (20 per page), expand **View Full Details, Match Breakdown & Application Tips** for skills alignment, interview questions, and customized cover letters.
   - Compare 2–4 roles side-by-side in the **Compare Jobs** tab.
   - Track jobs using **Save Job**, **Mark Applied**, or manage statuses (`Saved`, `Applied`, `Interviewing`, `Rejected`) and notes in the **Saved & Applied Jobs** tab.
