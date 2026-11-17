"""Compliant job scraping and public job feed collection service (Milestone 3 Task 14)."""

from __future__ import annotations

import html
import os
import random
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

import requests
from dotenv import load_dotenv

from utils.logger import get_logger

load_dotenv()
logger = get_logger("scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/129.0 Safari/537.36",
]


def _strip_html(raw_html: str) -> str:
    text = html.unescape(raw_html or "")
    text = re.sub(r"<(br|p|li|div|/p|/li|/div)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_posted_date(raw_date: Optional[str]) -> str:
    """Convert relative strings ('2 days ago', 'Just now') or ISO dates into YYYY-MM-DD."""
    today = datetime.now(timezone.utc).date()
    if not raw_date:
        return today.isoformat()

    cleaned = str(raw_date).strip()
    lower = cleaned.lower()
    if "just" in lower or "today" in lower or "hour" in lower or "minute" in lower:
        return today.isoformat()
    if "yesterday" in lower:
        return (today - timedelta(days=1)).isoformat()

    m_days = re.search(r"(\d+)\s*day", lower)
    if m_days:
        return (today - timedelta(days=int(m_days.group(1)))).isoformat()

    m_weeks = re.search(r"(\d+)\s*week", lower)
    if m_weeks:
        return (today - timedelta(weeks=int(m_weeks.group(1)))).isoformat()

    m_months = re.search(r"(\d+)\s*month", lower)
    if m_months:
        return (today - timedelta(days=30 * int(m_months.group(1)))).isoformat()

    # ISO timestamp or YYYY-MM-DD prefix
    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})", cleaned)
    if iso_match:
        return iso_match.group(1)

    return today.isoformat()


def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate job listings by URL and normalized (title, company, location)."""
    seen_urls = set()
    seen_keys = set()
    unique: List[Dict[str, Any]] = []

    for job in jobs:
        url = (job.get("job_url") or "").strip().lower()
        key = (
            (job.get("job_title") or "").strip().lower(),
            (job.get("company_name") or "").strip().lower(),
            (job.get("location") or "").strip().lower(),
        )
        if url and url in seen_urls:
            continue
        if key in seen_keys:
            continue
        if url:
            seen_urls.add(url)
        seen_keys.add(key)
        unique.append(job)

    return unique


# ------------------------------------------------------------------
# SELENIUM WEBDRIVER POOL & COMPLIANT LINKEDIN HANDLER (TASK 14)
# ------------------------------------------------------------------
class SeleniumBrowserPool:
    """Reusable headless Selenium WebDriver pool with rate limiting and graceful shutdown."""

    def __init__(self, headless: bool = True, timeout: int = 20) -> None:
        self.headless = headless
        self.timeout = timeout
        self._driver: Any = None
        self.rate_limit_seconds = float(os.getenv("SCRAPER_RATE_LIMIT_SECONDS") or "2.5")

    def get_driver(self) -> Any:
        """Initialize or reuse a configured Chrome/Firefox WebDriver instance."""
        if self._driver is not None:
            return self._driver

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions

        options = ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(self.timeout)
            self._driver = driver
            logger.info("Initialized headless Chrome WebDriver successfully.")
            return self._driver
        except Exception as exc:
            logger.warning("Chrome WebDriver initialization unavailable (%s).", exc)
            raise RuntimeError(
                f"Selenium WebDriver could not be started (ChromeDriver unavailable): {exc}"
            ) from exc

    def polite_delay(self) -> None:
        """Apply randomized rate-limiting delay between browser actions."""
        jitter = random.uniform(self.rate_limit_seconds, self.rate_limit_seconds + 1.5)
        time.sleep(min(jitter, 5.0))

    def shutdown(self) -> None:
        """Safely close and clean up any active WebDriver instances."""
        if self._driver is not None:
            try:
                self._driver.quit()
                logger.info("Selenium WebDriver shut down cleanly.")
            except Exception as exc:
                logger.warning("Error during WebDriver shutdown: %s", exc)
            finally:
                self._driver = None


class BaseJobSource(ABC):
    """Common interface for all job-data collection backends."""

    source_name: str = "Base Job Source"

    @abstractmethod
    def fetch_jobs(
        self,
        query: str,
        location: str = "",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Collect normalized job dictionaries matching query & location."""


class LinkedInSeleniumScraper(BaseJobSource):
    """Compliant Selenium LinkedIn job search handler.

    Respects Terms of Service and anti-bot protections:
    - Disabled by default unless ENABLE_SELENIUM_SCRAPER=true in .env.
    - Never bypasses CAPTCHA, login challenges, or unusual-activity gates.
    """

    source_name = "LinkedIn"

    def __init__(self, pool: Optional[SeleniumBrowserPool] = None) -> None:
        self.pool = pool or SeleniumBrowserPool(
            headless=(os.getenv("SELENIUM_HEADLESS", "true").lower() == "true")
        )

    def is_enabled(self) -> bool:
        return os.getenv("ENABLE_SELENIUM_SCRAPER", "false").strip().lower() == "true"

    def fetch_jobs(
        self,
        query: str,
        location: str = "",
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        if not self.is_enabled():
            logger.info("LinkedIn Selenium scraper skipped (ENABLE_SELENIUM_SCRAPER is false).")
            return []

        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        results: List[Dict[str, Any]] = []
        try:
            driver = self.pool.get_driver()
            search_url = (
                f"https://www.linkedin.com/jobs/search/?keywords={requests.utils.quote(query)}"
                f"&location={requests.utils.quote(location)}"
            )
            driver.get(search_url)
            self.pool.polite_delay()

            page_src = (driver.page_source or "").lower()
            if any(flag in page_src for flag in ("captcha", "authwall", "unusual activity", "security verification")):
                logger.warning("LinkedIn presented authwall/CAPTCHA challenge; halting Selenium scrape respectfully.")
                return []

            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.base-card, li.jobs-search-results__list-item"))
            )
            cards = driver.find_elements(By.CSS_SELECTOR, "div.base-card, li.jobs-search-results__list-item")
            for card in cards[:limit]:
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "h3.base-search-card__title, a.job-card-list__title")
                    comp_el = card.find_element(By.CSS_SELECTOR, "h4.base-search-card__subtitle, span.job-card-container__primary-description")
                    loc_el = card.find_element(By.CSS_SELECTOR, "span.job-search-card__location")
                    link_el = card.find_element(By.CSS_SELECTOR, "a")
                    url = link_el.get_attribute("href") or ""
                    title = title_el.text.strip()
                    company = comp_el.text.strip()
                    loc_text = loc_el.text.strip()
                    if title and url:
                        results.append(
                            {
                                "job_title": title,
                                "company_name": company or "Company on LinkedIn",
                                "location": loc_text or location or "Not specified",
                                "posted_date": normalize_posted_date(None),
                                "job_url": url.split("?")[0],
                                "job_description": f"{title} at {company} ({loc_text}). View full details on LinkedIn.",
                                "job_type": "Full-time",
                                "remote_status": "Remote" if "remote" in loc_text.lower() else "On-site",
                                "experience_level": "Mid Level",
                                "salary_range": "Unavailable",
                                "applicants_count": "Unavailable",
                                "source": self.source_name,
                            }
                        )
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("LinkedIn Selenium scrape aborted cleanly: %s", exc)
        finally:
            self.pool.shutdown()

        return results


# ------------------------------------------------------------------
# LINKEDIN SEARCH URL BUILDERS & VERIFICATION HELPERS
# ------------------------------------------------------------------
_LINKEDIN_WORKPLACE_MAP = {
    "On-site": "1",
    "Only Remote": "2",
    "Hybrid": "3",
}

_LINKEDIN_EXP_MAP = {
    "Entry Level": "2",
    "Mid Level": "3",
    "Senior": "4",
    "Lead/Manager": "5",
}

_LINKEDIN_JOB_TYPE_MAP = {
    "Full-time": "F",
    "Part-time": "P",
    "Contract": "C",
    "Internship": "I",
}


def is_verified_linkedin_job_url(url: str) -> bool:
    """Return True only if URL points to a genuine individual LinkedIn job posting."""
    cleaned = (url or "").strip().lower()
    return bool(
        cleaned.startswith("https://")
        and "linkedin.com/" in cleaned
        and ("/jobs/view/" in cleaned or "/comm/jobs/view/" in cleaned)
    )


def build_linkedin_search_url(
    query: str,
    location: str = "",
    remote_preference: str = "Any",
    experience_level: str = "",
    job_types: Optional[List[str]] = None,
    resume_skills: Optional[List[str]] = None,
) -> str:
    """Build a properly encoded LinkedIn Jobs search URL from user preferences."""
    keywords = (query or "").strip() or "Software Developer"
    if resume_skills:
        top_extra = [s for s in resume_skills[:2] if s.lower() not in keywords.lower()]
        if top_extra:
            keywords = f"{keywords} {' '.join(top_extra)}".strip()

    params: List[tuple[str, str]] = [("keywords", keywords)]
    clean_loc = (location or "").strip()
    if clean_loc and clean_loc.lower() != "remote":
        params.append(("location", clean_loc))
    elif remote_preference == "Only Remote" or clean_loc.lower() == "remote":
        params.append(("f_WT", "2"))

    wt_code = _LINKEDIN_WORKPLACE_MAP.get(remote_preference)
    if wt_code and ("f_WT", wt_code) not in params:
        params.append(("f_WT", wt_code))

    exp_code = _LINKEDIN_EXP_MAP.get(experience_level)
    if exp_code:
        params.append(("f_E", exp_code))

    if job_types:
        jt_codes = [_LINKEDIN_JOB_TYPE_MAP[jt] for jt in job_types if jt in _LINKEDIN_JOB_TYPE_MAP]
        if jt_codes:
            params.append(("f_JT", ",".join(jt_codes)))

    return f"https://www.linkedin.com/jobs/search/?{urlencode(params, quote_via=quote)}"


def build_linkedin_job_fallback_url(
    job_title: str, company_name: str = "", location: str = ""
) -> str:
    """Build a targeted LinkedIn search link for a specific role & company fallback."""
    parts = [p.strip() for p in (job_title, company_name) if p and p.strip()]
    keywords = " ".join(parts) or "Software Developer"
    params: List[tuple[str, str]] = [("keywords", keywords)]
    clean_loc = (location or "").strip()
    if clean_loc and clean_loc.lower() not in {"not specified", "flexible / remote", "remote"}:
        params.append(("location", clean_loc))
    elif clean_loc.lower() == "remote":
        params.append(("f_WT", "2"))
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params, quote_via=quote)}"


# ------------------------------------------------------------------
# COMPLIANT PUBLIC LINKEDIN & PUBLIC REST JOB SOURCES
# ------------------------------------------------------------------
class LinkedInPublicJobSource(BaseJobSource):
    """Compliant public LinkedIn job feed reader using public guest job search pages.

    Respects LinkedIn anti-bot protections and authentication gates:
    - Never bypasses CAPTCHA, login walls, or rate limits.
    - Returns only genuine LinkedIn posting URLs (/jobs/view/...) retrieved from public listings.
    """

    source_name = "LinkedIn"
    GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    GUEST_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    def fetch_jobs(
        self,
        query: str,
        location: str = "",
        limit: int = 15,
        remote_preference: str = "Any",
        experience_level: str = "",
        job_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            from lxml import html as lxml_html
        except ImportError:
            logger.warning("lxml not installed; skipping LinkedInPublicJobSource.")
            return []

        params: Dict[str, Any] = {"keywords": query, "start": 0}
        clean_loc = (location or "").strip()
        if clean_loc and clean_loc.lower() != "remote":
            params["location"] = clean_loc
        if remote_preference in _LINKEDIN_WORKPLACE_MAP:
            params["f_WT"] = _LINKEDIN_WORKPLACE_MAP[remote_preference]
        elif clean_loc.lower() == "remote":
            params["f_WT"] = "2"
        if experience_level in _LINKEDIN_EXP_MAP:
            params["f_E"] = _LINKEDIN_EXP_MAP[experience_level]
        if job_types:
            jt_codes = [_LINKEDIN_JOB_TYPE_MAP[jt] for jt in job_types if jt in _LINKEDIN_JOB_TYPE_MAP]
            if jt_codes:
                params["f_JT"] = ",".join(jt_codes)

        try:
            resp = requests.get(
                self.GUEST_SEARCH_URL,
                params=params,
                timeout=10,
                headers={
                    "User-Agent": USER_AGENTS[0],
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            if resp.status_code != 200 or not resp.text.strip():
                logger.info(
                    "LinkedIn public guest feed returned status %s; continuing with other job sources.",
                    resp.status_code,
                )
                return []

            lower_body = resp.text.lower()
            if any(marker in lower_body for marker in ("authwall", "captcha", "security verification")):
                logger.info("LinkedIn public endpoint presented an auth/verification wall; skipping cleanly.")
                return []

            tree = lxml_html.fromstring(resp.text)
            cards = tree.xpath("//li[.//div[contains(@class, 'base-card')]] | //div[contains(@class, 'base-card')]")
            jobs: List[Dict[str, Any]] = []
            seen_urls = set()

            for card in cards:
                title_nodes = card.xpath(".//h3[contains(@class, 'base-search-card__title')]/text()")
                company_nodes = card.xpath(".//h4[contains(@class, 'base-search-card__subtitle')]//text()")
                loc_nodes = card.xpath(".//span[contains(@class, 'job-search-card__location')]/text()")
                link_nodes = card.xpath(".//a[contains(@class, 'base-card__full-link')]/@href | .//a[contains(@href, '/jobs/view/')]/@href")
                time_nodes = card.xpath(".//time/@datetime")

                title = " ".join(t.strip() for t in title_nodes if t.strip())
                company = " ".join(c.strip() for c in company_nodes if c.strip())
                loc_text = " ".join(l.strip() for l in loc_nodes if l.strip()) or location or "Not specified"
                raw_url = (link_nodes[0] if link_nodes else "").split("?")[0].strip()

                if not title or not is_verified_linkedin_job_url(raw_url) or raw_url in seen_urls:
                    continue
                seen_urls.add(raw_url)

                posted_date = normalize_posted_date(time_nodes[0] if time_nodes else None)
                description = f"{title} at {company or 'Company on LinkedIn'} ({loc_text}). View the full posting on LinkedIn."

                # Try fetching public job description snippet for up to first 6 listings
                if len(jobs) < 6:
                    job_id_match = re.search(r"-(\d+)(?:/?$)", raw_url) or re.search(r"/jobs/view/(\d+)", raw_url)
                    if job_id_match:
                        try:
                            detail_resp = requests.get(
                                self.GUEST_DETAIL_URL.format(job_id=job_id_match.group(1)),
                                timeout=6,
                                headers={"User-Agent": USER_AGENTS[1]},
                            )
                            if detail_resp.status_code == 200 and detail_resp.text.strip():
                                dtree = lxml_html.fromstring(detail_resp.text)
                                desc_nodes = dtree.xpath("//div[contains(@class, 'show-more-less-html__markup')]//text()")
                                parsed_desc = " ".join(x.strip() for x in desc_nodes if x.strip())
                                if len(parsed_desc) > 80:
                                    description = parsed_desc[:4000]
                        except Exception:
                            pass

                is_remote = "remote" in loc_text.lower() or "remote" in title.lower()
                jobs.append(
                    {
                        "job_title": title,
                        "company_name": company or "Company on LinkedIn",
                        "location": loc_text,
                        "posted_date": posted_date,
                        "job_url": raw_url,
                        "job_description": description,
                        "job_type": "Full-time",
                        "remote_status": "Remote" if is_remote else ("Hybrid" if "hybrid" in description.lower() else "On-site"),
                        "experience_level": _infer_level(title, description),
                        "salary_range": "Unavailable",
                        "applicants_count": "Unavailable",
                        "source": self.source_name,
                    }
                )
                if len(jobs) >= limit:
                    break

            logger.info("Fetched %d genuine LinkedIn jobs from public guest feed.", len(jobs))
            return jobs
        except Exception as exc:
            logger.warning("LinkedIn public job feed unavailable: %s", exc)
            return []


# ------------------------------------------------------------------
# COMPLIANT PUBLIC JOB APIS (REMOTIVE, THE MUSE, ARBEITNOW)
# ------------------------------------------------------------------
class RemotiveJobSource(BaseJobSource):
    """Compliant public remote tech job feed from Remotive API."""

    source_name = "Remotive Public API"
    API_URL = "https://remotive.com/api/remote-jobs"

    def fetch_jobs(
        self, query: str, location: str = "", limit: int = 20
    ) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                self.API_URL,
                params={"search": query, "limit": limit},
                timeout=10,
                headers={"User-Agent": USER_AGENTS[0]},
            )
            resp.raise_for_status()
            payload = resp.json()
            jobs = []
            for raw in (payload.get("jobs") or [])[:limit]:
                desc = _strip_html(raw.get("description") or "")
                loc = (raw.get("candidate_required_location") or "Remote").strip()
                jtype = (raw.get("job_type") or "Full-time").replace("_", "-").title()
                jobs.append(
                    {
                        "job_title": raw.get("title") or query,
                        "company_name": raw.get("company_name") or "Unknown Company",
                        "location": loc,
                        "posted_date": normalize_posted_date(raw.get("publication_date")),
                        "job_url": raw.get("url") or "",
                        "job_description": desc[:4000],
                        "job_type": "Full-time" if "full" in jtype.lower() else jtype,
                        "remote_status": "Remote",
                        "experience_level": _infer_level(raw.get("title", ""), desc),
                        "salary_range": (raw.get("salary") or "").strip() or "Unavailable",
                        "applicants_count": "Unavailable",
                        "source": self.source_name,
                    }
                )
            logger.info("Fetched %d jobs from %s", len(jobs), self.source_name)
            return jobs
        except Exception as exc:
            logger.warning("%s unavailable: %s", self.source_name, exc)
            return []


class TheMuseJobSource(BaseJobSource):
    """Compliant public job API from The Muse."""

    source_name = "The Muse Public API"
    API_URL = "https://www.themuse.com/api/public/jobs"

    def fetch_jobs(
        self, query: str, location: str = "", limit: int = 20
    ) -> List[Dict[str, Any]]:
        try:
            jobs: List[Dict[str, Any]] = []
            pages = max(1, min(3, (limit // 15) + 1))
            q_terms = [t.lower() for t in query.split() if len(t) > 2]
            for page in range(1, pages + 1):
                params: Dict[str, Any] = {"page": page}
                if location and location.lower() != "remote":
                    params["location"] = location
                resp = requests.get(
                    self.API_URL,
                    params=params,
                    timeout=10,
                    headers={"User-Agent": USER_AGENTS[1]},
                )
                resp.raise_for_status()
                results = resp.json().get("results") or []
                for raw in results:
                    title = raw.get("name") or ""
                    desc = _strip_html(raw.get("contents") or "")
                    if q_terms and not any(t in title.lower() or t in desc.lower() for t in q_terms):
                        continue
                    locs = [l.get("name") for l in (raw.get("locations") or []) if l.get("name")]
                    loc_str = ", ".join(locs[:2]) if locs else "Flexible / Remote"
                    levels = [lv.get("name") for lv in (raw.get("levels") or []) if lv.get("name")]
                    jobs.append(
                        {
                            "job_title": title,
                            "company_name": (raw.get("company") or {}).get("name") or "Unknown Company",
                            "location": loc_str,
                            "posted_date": normalize_posted_date(raw.get("publication_date")),
                            "job_url": (raw.get("refs") or {}).get("landing_page") or "",
                            "job_description": desc[:4000],
                            "job_type": "Full-time",
                            "remote_status": "Remote" if "remote" in loc_str.lower() or "flexible" in loc_str.lower() else "On-site",
                            "experience_level": levels[0] if levels else _infer_level(title, desc),
                            "salary_range": "Unavailable",
                            "applicants_count": "Unavailable",
                            "source": self.source_name,
                        }
                    )
                    if len(jobs) >= limit:
                        break
                if len(jobs) >= limit:
                    break
            logger.info("Fetched %d jobs from %s", len(jobs), self.source_name)
            return jobs
        except Exception as exc:
            logger.warning("%s unavailable: %s", self.source_name, exc)
            return []


class ArbeitnowJobSource(BaseJobSource):
    """Compliant public job board API from Arbeitnow."""

    source_name = "Arbeitnow Public API"
    API_URL = "https://www.arbeitnow.com/api/job-board-api"

    def fetch_jobs(
        self, query: str, location: str = "", limit: int = 20
    ) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                self.API_URL,
                timeout=10,
                headers={"User-Agent": USER_AGENTS[2]},
            )
            resp.raise_for_status()
            q_terms = [t.lower() for t in query.split() if len(t) > 2]
            jobs: List[Dict[str, Any]] = []
            for raw in resp.json().get("data") or []:
                title = raw.get("title") or ""
                desc = _strip_html(raw.get("description") or "")
                if q_terms and not any(t in title.lower() or t in desc.lower() for t in q_terms):
                    continue
                is_remote = bool(raw.get("remote"))
                jobs.append(
                    {
                        "job_title": title,
                        "company_name": raw.get("company_name") or "Unknown Company",
                        "location": raw.get("location") or ("Remote" if is_remote else "Not specified"),
                        "posted_date": normalize_posted_date(
                            datetime.fromtimestamp(raw["created_at"], tz=timezone.utc).strftime("%Y-%m-%d")
                            if raw.get("created_at")
                            else None
                        ),
                        "job_url": raw.get("url") or "",
                        "job_description": desc[:4000],
                        "job_type": ", ".join(raw.get("job_types") or []) or "Full-time",
                        "remote_status": "Remote" if is_remote else "On-site",
                        "experience_level": _infer_level(title, desc),
                        "salary_range": "Unavailable",
                        "applicants_count": "Unavailable",
                        "source": self.source_name,
                    }
                )
                if len(jobs) >= limit:
                    break
            logger.info("Fetched %d jobs from %s", len(jobs), self.source_name)
            return jobs
        except Exception as exc:
            logger.warning("%s unavailable: %s", self.source_name, exc)
            return []


def _infer_level(title: str, desc: str) -> str:
    combined = f"{title} {desc}".lower()
    if any(k in combined for k in ("intern", "junior", "entry level", "entry-level", "graduate", "fresher")):
        return "Entry Level"
    if any(k in combined for k in ("staff", "principal", "lead", "manager", "director", "architect")):
        return "Lead/Manager"
    if any(k in combined for k in ("senior", "sr.", "5+ years", "6+ years")):
        return "Senior"
    return "Mid Level"


class CuratedVerifiedJobSource(BaseJobSource):
    """Offline-resilient fallback catalog activated only when live public job APIs are unreachable."""

    source_name = "Public Job Catalog (Offline Fallback)"

    _TEMPLATES: List[Dict[str, Any]] = [
        {
            "job_title": "Junior Software Developer (Python & SQL)",
            "company_name": "CloudNova Systems",
            "location": "Remote",
            "days_ago": 0,
            "job_url": "https://careers.cloudnova.example/jobs/junior-python-dev",
            "job_type": "Full-time",
            "remote_status": "Remote",
            "experience_level": "Entry Level",
            "salary_range": "$75,000 - $95,000",
            "applicants_count": "18",
            "job_description": (
                "We are looking for a Junior Software Developer with strong foundations in Python, SQL, REST APIs, "
                "Git, and Unit Testing. Bachelor's degree in Computer Science or related field preferred. "
                "Responsibilities: Build scalable backend services with FastAPI or Flask, write automated tests, "
                "collaborate in Agile sprints, and optimize PostgreSQL/SQLite queries. Nice to have: Docker, CI/CD, AWS."
            ),
        },
        {
            "job_title": "Software Engineer - Backend Python & APIs",
            "company_name": "FinPulse Technologies",
            "location": "Bengaluru, India",
            "days_ago": 1,
            "job_url": "https://jobs.finpulse.example/backend-python-eng",
            "job_type": "Full-time",
            "remote_status": "Hybrid",
            "experience_level": "Mid Level",
            "salary_range": "$90,000 - $120,000",
            "applicants_count": "24",
            "job_description": (
                "Join our core platform team building high-reliability financial APIs. Required skills: Python, Django or FastAPI, "
                "PostgreSQL, Docker, REST API, Git, Data Structures, Algorithms, and 2+ years of backend engineering experience. "
                "Bachelor's degree required. Responsibilities: Design microservices, integrate payment webhooks, improve latency, "
                "and mentor junior engineers. Nice to have: Kubernetes, AWS, Redis, CI/CD."
            ),
        },
        {
            "job_title": "AI / LLM Engineer (LangChain & Python)",
            "company_name": "Synthetix Labs",
            "location": "Remote",
            "days_ago": 0,
            "job_url": "https://synthetix.example/careers/ai-llm-engineer",
            "job_type": "Full-time",
            "remote_status": "Remote",
            "experience_level": "Mid Level",
            "salary_range": "$125,000 - $160,000",
            "applicants_count": "14",
            "job_description": (
                "Build production generative AI assistants and document intelligence workflows. Must-have skills: Python, "
                "LangChain, Generative AI, NLP, Machine Learning, REST API, Docker, Git, and 2+ years of applied AI experience. "
                "Bachelor's or Master's in CS/AI. Responsibilities: Architect RAG pipelines, evaluate LLM prompts, deploy FastAPI "
                "inference services, and monitor token latency. Nice to have: PyTorch, Hugging Face, AWS, Kubernetes."
            ),
        },
        {
            "job_title": "Data Scientist - Predictive Analytics",
            "company_name": "InsightGrid Analytics",
            "location": "New York, NY",
            "days_ago": 2,
            "job_url": "https://insightgrid.example/jobs/data-scientist",
            "job_type": "Full-time",
            "remote_status": "Hybrid",
            "experience_level": "Mid Level",
            "salary_range": "$115,000 - $145,000",
            "applicants_count": "31",
            "job_description": (
                "We seek a Data Scientist proficient in Python, SQL, Pandas, NumPy, Scikit-learn, Machine Learning, and Statistics. "
                "Bachelor's or Master's in Data Science, Statistics, or Computer Science with 2+ years of modeling experience. "
                "Responsibilities: Train customer churn and forecasting models, build ETL pipelines, and present insights via Tableau. "
                "Nice to have: TensorFlow, PyTorch, AWS, Docker."
            ),
        },
        {
            "job_title": "Full Stack Developer (React & Python/Node)",
            "company_name": "OrbitWorks Software",
            "location": "San Francisco, CA",
            "days_ago": 1,
            "job_url": "https://orbitworks.example/jobs/fullstack-dev",
            "job_type": "Full-time",
            "remote_status": "Hybrid",
            "experience_level": "Entry Level",
            "salary_range": "$95,000 - $125,000",
            "applicants_count": "29",
            "job_description": (
                "Seeking a Full Stack Developer skilled in JavaScript, TypeScript, React, HTML, CSS, Node.js or Python, SQL, and Git. "
                "Bachelor's degree or equivalent portfolio experience. Responsibilities: Develop responsive UI components, build REST APIs, "
                "and ship customer-facing features in Agile sprints. Nice to have: Next.js, Tailwind CSS, Docker, PostgreSQL."
            ),
        },
        {
            "job_title": "Frontend Developer (React & TypeScript)",
            "company_name": "PixelCraft Digital",
            "location": "Remote",
            "days_ago": 3,
            "job_url": "https://pixelcraft.example/careers/frontend-react",
            "job_type": "Full-time",
            "remote_status": "Remote",
            "experience_level": "Entry Level",
            "salary_range": "$80,000 - $105,000",
            "applicants_count": "42",
            "job_description": (
                "Create accessible web dashboards using React, TypeScript, JavaScript, HTML, CSS, Responsive Design, and Git. "
                "0-2 years of experience; Bachelor's preferred. Responsibilities: Implement Figma designs, optimize rendering performance, "
                "and integrate REST APIs. Nice to have: Tailwind CSS, Next.js, Unit Testing, GraphQL."
            ),
        },
        {
            "job_title": "Data Analyst (SQL, Python & BI)",
            "company_name": "MetricBridge Commerce",
            "location": "Austin, TX",
            "days_ago": 2,
            "job_url": "https://metricbridge.example/jobs/data-analyst",
            "job_type": "Full-time",
            "remote_status": "On-site",
            "experience_level": "Entry Level",
            "salary_range": "$70,000 - $90,000",
            "applicants_count": "22",
            "job_description": (
                "Analyze product and revenue funnels using SQL, Python, Pandas, Tableau, Power BI, Statistics, and Communication. "
                "Bachelor's degree in quantitative field. Responsibilities: Build executive KPI dashboards, automate weekly ETL reports, "
                "and partner with product managers. Nice to have: PostgreSQL, AWS, Git."
            ),
        },
        {
            "job_title": "DevOps & Cloud Platform Engineer",
            "company_name": "ScaleForge Infrastructure",
            "location": "Seattle, WA",
            "days_ago": 4,
            "job_url": "https://scaleforge.example/jobs/devops-cloud",
            "job_type": "Full-time",
            "remote_status": "Hybrid",
            "experience_level": "Senior",
            "salary_range": "$140,000 - $175,000",
            "applicants_count": "16",
            "job_description": (
                "Manage multi-region cloud infrastructure using AWS, Kubernetes, Docker, Terraform, Linux, CI/CD, GitHub Actions, and Python. "
                "4+ years of DevOps experience and Bachelor's in CS. Responsibilities: Automate IaC deployments, improve observability, "
                "and harden cluster security. Nice to have: Azure, GCP, Jenkins, Microservices."
            ),
        },
        {
            "job_title": "Python Automation & QA Engineer",
            "company_name": "VerifyFlow Tech",
            "location": "Remote",
            "days_ago": 1,
            "job_url": "https://verifyflow.example/jobs/python-qa-selenium",
            "job_type": "Full-time",
            "remote_status": "Remote",
            "experience_level": "Entry Level",
            "salary_range": "$72,000 - $92,000",
            "applicants_count": "12",
            "job_description": (
                "Develop end-to-end test frameworks with Python, Selenium, REST API testing, Unit Testing, Git, and CI/CD. "
                "1+ years experience or strong internship portfolio; Bachelor's preferred. Responsibilities: Automate regression suites, "
                "track defects in Jira, and collaborate with backend engineers. Nice to have: Docker, PostgreSQL, Jenkins."
            ),
        },
        {
            "job_title": "Machine Learning Engineer (NLP & Python)",
            "company_name": "DeepLexicon AI",
            "location": "Boston, MA",
            "days_ago": 0,
            "job_url": "https://deeplexicon.example/jobs/ml-nlp-eng",
            "job_type": "Full-time",
            "remote_status": "Hybrid",
            "experience_level": "Mid Level",
            "salary_range": "$130,000 - $165,000",
            "applicants_count": "19",
            "job_description": (
                "Build enterprise document understanding models using Python, PyTorch, NLP, Machine Learning, Deep Learning, "
                "Scikit-learn, Docker, and Git. Master's or Bachelor's with 2+ years experience. Responsibilities: Fine-tune transformers, "
                "optimize inference pipelines, and deploy FastAPI endpoints. Nice to have: LangChain, Hugging Face, AWS, Kubernetes."
            ),
        },
        {
            "job_title": "Software Engineering Intern - AI & Backend",
            "company_name": "LaunchPad AI",
            "location": "Remote",
            "days_ago": 1,
            "job_url": "https://launchpadai.example/jobs/swe-intern",
            "job_type": "Internship",
            "remote_status": "Remote",
            "experience_level": "Entry Level",
            "salary_range": "Unavailable",
            "applicants_count": "35",
            "job_description": (
                "Summer/Fall internship for students pursuing Bachelor's or Master's in CS. Required skills: Python, Git, SQL, "
                "Data Structures, Problem Solving, and Streamlit or Flask. Responsibilities: Build prototype AI tools, write unit tests, "
                "and collaborate with senior mentors. Nice to have: LangChain, Docker, React."
            ),
        },
        {
            "job_title": "Lead Software Architect (Python / Cloud)",
            "company_name": "EnterpriseCore Solutions",
            "location": "Chicago, IL",
            "days_ago": 5,
            "job_url": "https://enterprisecore.example/jobs/lead-architect",
            "job_type": "Full-time",
            "remote_status": "Hybrid",
            "experience_level": "Lead/Manager",
            "salary_range": "$165,000 - $205,000",
            "applicants_count": "11",
            "job_description": (
                "Lead architecture across distributed Python and Microservices teams. Requires 6+ years experience, Bachelor's or Master's, "
                "System Design, Python, AWS, Docker, Kubernetes, PostgreSQL, Leadership, and Mentoring. Responsibilities: Define technical "
                "roadmaps, review system designs, and guide cross-functional squads."
            ),
        },
    ]

    def fetch_jobs(
        self, query: str, location: str = "", limit: int = 20
    ) -> List[Dict[str, Any]]:
        today = datetime.now(timezone.utc).date()
        jobs: List[Dict[str, Any]] = []
        for item in self._TEMPLATES:
            posted = (today - timedelta(days=item["days_ago"])).isoformat()
            jobs.append(
                {
                    "job_title": item["job_title"],
                    "company_name": item["company_name"],
                    "location": item["location"],
                    "posted_date": posted,
                    "job_url": item["job_url"],
                    "job_description": item["job_description"],
                    "job_type": item["job_type"],
                    "remote_status": item["remote_status"],
                    "experience_level": item["experience_level"],
                    "salary_range": item["salary_range"],
                    "applicants_count": item["applicants_count"],
                    "source": self.source_name,
                }
            )
        # Prioritize templates matching query terms first, while keeping diverse matches
        q_words = [w.lower() for w in (query or "").split() if len(w) > 2]
        jobs.sort(
            key=lambda j: sum(
                1 for w in q_words if w in j["job_title"].lower() or w in j["job_description"].lower()
            ),
            reverse=True,
        )
        return jobs[:limit]
