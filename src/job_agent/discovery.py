from datetime import datetime, timedelta, timezone
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit

from ddgs import DDGS

from src.job_agent.core import JobListing, deduplicate_jobs, normalize_job


SOURCE_DOMAINS = {
    "linkedin": "linkedin.com",
    "naukri": "naukri.com",
    "indeed": "indeed.com",
}

ROLE_ALIASES = {
    "qa analyst": [
        "QA Analyst",
        "Quality Analyst",
        "QA Engineer",
        "Manual Tester",
        "Software Test Engineer",
    ],
    "sdet": [
        "SDET",
        "SDET 1",
        "QA Automation Engineer",
        "Automation Test Engineer",
        "Software Development Engineer in Test",
    ],
    "ai developer": [
        "AI Developer",
        "AI Engineer",
        "Generative AI Engineer",
        "LLM Engineer",
        "Machine Learning Engineer",
    ],
}



class JobDiscoveryError(Exception):
    """Raised when a job discovery search cannot be completed."""


def build_search_query(
    role: str,
    location: str,
    source: str,
) -> str:
    """Build a domain-restricted public job search query."""
    normalized_source = source.strip().lower()

    if normalized_source not in SOURCE_DOMAINS:
        raise ValueError(
            f"Unsupported source: {source}. "
            f"Choose from {', '.join(SOURCE_DOMAINS)}."
        )

    if not role.strip():
        raise ValueError("Job role cannot be empty.")

    domain = SOURCE_DOMAINS[normalized_source]
    query = f'site:{domain} "{role.strip()}" jobs'

    if location.strip():
        query += f' "{location.strip()}"'

    return query


def build_freshness_url(
    role: str,
    location: str = "",
    freshness: str = "past_week",
) -> str:
    """Build a LinkedIn search URL with a posting-date filter."""
    freshness_seconds = {
        "past_24_hours": 86400,
        "past_3_days": 259200,
        "past_week": 604800,
    }

    if freshness not in freshness_seconds:
        raise ValueError("Unsupported freshness filter.")

    if not role.strip():
        raise ValueError("Job role cannot be empty.")

    params = {
        "keywords": role.strip(),
        "f_TPR": f"r{freshness_seconds[freshness]}",
        "sortBy": "DD",
    }

    if location.strip():
        params["location"] = location.strip()

    return (
        "https://www.linkedin.com/jobs/search/?"
        + urlencode(params)
    )


def is_individual_job_page(url: str, source: str) -> bool:
    """Check whether a URL resembles an individual job listing."""
    parts = urlsplit(url)
    path = parts.path.lower()
    query = parts.query.lower()
    normalized_source = source.strip().lower()

    if normalized_source == "linkedin":
        return "/jobs/view/" in path

    if normalized_source == "naukri":
        return "job-listings-" in path or "/job-listing/" in path

    if normalized_source == "indeed":
        return (
            path.rstrip("/") == "/viewjob" and "jk=" in query
        ) or (
            "/rc/clk" in path and "jk=" in query
        )

    return False

FRESHNESS_WINDOWS = {
    "past_24_hours": timedelta(hours=24),
    "past_3_days": timedelta(days=3),
    "past_week": timedelta(days=7),
}


def extract_verified_posting_date(result: dict) -> str:
    """
    Read an explicit structured posting-date field.

    Do not use generic search-result dates or retrieved_at as
    evidence of when the employer published the job.
    """
    raw_date = (
        result.get("datePosted")
        or result.get("date_posted")
        or result.get("posting_date")
    )

    if not isinstance(raw_date, str) or not raw_date.strip():
        return ""

    try:
        parsed = datetime.fromisoformat(
            raw_date.strip().replace("Z", "+00:00")
        )
    except ValueError:
        return ""

    # A date without a time and timezone is not precise enough
    # to verify a rolling 24-hour window.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return ""

    return parsed.astimezone(timezone.utc).isoformat()

def extract_estimated_posting_date(
    result: dict,
    now: datetime | None = None,
) -> str:
    """Convert a search provider's relative date into an estimate.

    This is not a verified employer publication timestamp.
    """
    raw_date = result.get("date")

    if not isinstance(raw_date, str) or not raw_date.strip():
        return ""

    value = raw_date.strip().lower()
    current_time = now or datetime.now(timezone.utc)

    # Normalize to UTC for consistent comparisons.
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must include timezone information.")

    current_time = current_time.astimezone(timezone.utc)

    if value in {"today", "just now", "just posted"}:
        return current_time.isoformat()

    if value == "yesterday":
        return (current_time - timedelta(days=1)).isoformat()

    import re

    match = re.search(
        r"(\d+)\s+(minute|minutes|min|hour|hours|hr|hrs|day|days|week|weeks|month|months)\s+ago",
        value,
    )

    if not match:
        return ""

    amount = int(match.group(1))
    unit = match.group(2)

    if unit in {"minute", "minutes", "min"}:
        delta = timedelta(minutes=amount)
    elif unit in {"hour", "hours", "hr", "hrs"}:
        delta = timedelta(hours=amount)
    elif unit in {"day", "days"}:
        delta = timedelta(days=amount)
    elif unit in {"week", "weeks"}:
        delta = timedelta(weeks=amount)
    else:
        # "Month ago" is too imprecise for reliable rolling filters.
        return ""

    return (current_time - delta).isoformat()



def classify_jobs_by_freshness(
    jobs: list[JobListing],
    freshness: str,
    now: datetime | None = None,
) -> tuple[list[JobListing], list[JobListing], list[JobListing]]:
    """
    Return (recent_candidates, undated_candidates, older_candidates).

    Recent candidates can have either a verified posting timestamp
    or an estimated date supplied by the search provider.
    The posting_date_verified flag distinguishes the two.
    """
    if freshness not in FRESHNESS_WINDOWS:
        raise ValueError("Unsupported freshness filter.")

    current_time = now or datetime.now(timezone.utc)

    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must include timezone information.")

    current_time = current_time.astimezone(timezone.utc)
    cutoff = current_time - FRESHNESS_WINDOWS[freshness]

    recent = []
    unverified = []
    older = []

    for job in jobs:
        if not job.posting_date:
            unverified.append(job)
            continue

        try:
            posted_at = datetime.fromisoformat(
                job.posting_date.replace("Z", "+00:00")
            )
        except ValueError:
            unverified.append(job)
            continue

        if posted_at.tzinfo is None or posted_at.utcoffset() is None:
            unverified.append(job)
            continue

        posted_at = posted_at.astimezone(timezone.utc)

        if posted_at > current_time:
            unverified.append(job)
        elif posted_at >= cutoff:
            # Includes estimated dates, which remain explicitly
            # marked as unverified in the JobListing object.
            recent.append(job)
        else:
            older.append(job)

    return recent, unverified, older

def title_matches_role(selected_role: str, job_title: str) -> bool:
    """Reject job titles outside the selected role family."""

    title = " ".join(job_title.lower().replace("-", " ").split())
    role = " ".join(selected_role.lower().replace("-", " ").split())

    role_terms = {
        "sdet": (
            "sdet",
            "software development engineer in test",
        ),
        "qa analyst": (
            "qa analyst",
            "quality analyst",
        ),
        "ai developer": (
            "ai developer",
            "ai engineer",
            "generative ai engineer",
        ),
    }

    accepted_terms = role_terms.get(role, (role,))

    return any(term in title for term in accepted_terms)




def search_jobs(
    role: str,
    location: str = "",
    source: str = "linkedin",
    max_results: int = 10,
    search_callable: Callable | None = None,
    freshness: str = "past_week",
) -> list[JobListing]:
    """Discover and deduplicate publicly indexed individual job pages."""
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be between 1 and 50.")
    if freshness not in FRESHNESS_WINDOWS:
        raise ValueError("Unsupported freshness filter.")
    normalized_source = source.strip().lower()
    query = build_search_query(role, location, normalized_source)
    expected_domain = SOURCE_DOMAINS[normalized_source]

    if search_callable is None:
        search_callable = DDGS(timeout=20).text

    domain = SOURCE_DOMAINS[normalized_source]
    
    role_key = role.strip().lower()
    role_variants = ROLE_ALIASES.get(
        role_key,
        [role.strip()],
    )

    location_text = location.strip()

    queries = []

    for role_variant in role_variants:
        query_parts = [
            f"site:{domain}",
            f'"{role_variant}"',
            "jobs",
        ]

        if location_text:
            query_parts.append(location_text)

        queries.append(" ".join(query_parts))

    # Also try a less restrictive query for the original role.
    broad_query_parts = [
        f"site:{domain}",
        role.strip(),
        "jobs",
    ]

    if location_text:
        broad_query_parts.append(location_text)

    queries.append(" ".join(broad_query_parts))

    # Avoid sending duplicate searches.
    queries = list(dict.fromkeys(queries))


    results = []

    for candidate_query in queries:
        try:
                        # DDGS supports day/week/month/year limits, not an
            # exact three-day window. Apply the exact window below.
            timelimit = (
                "d"
                if freshness == "past_24_hours"
                else "w"
            )
            candidate_results = search_callable(
                candidate_query,
                region="in-en",
                max_results=max_results,
                timelimit=timelimit,
            )

            if candidate_results:
                results.extend(candidate_results)

        except Exception as exc:
            message = str(exc).lower()

            if "no results found" in message:
                continue

            if "timed out" in message or "timeout" in message:
                continue

            raise JobDiscoveryError(
                 f"Public search failed for {normalized_source}: {exc}"
            ) from exc

    jobs = []

    for result in results:
        raw_url = str(result.get("href") or "").strip()
        result_title = str(result.get("title") or "").strip()

        if not title_matches_role(role, result_title):
             continue
        parts = urlsplit(raw_url)
        hostname = (parts.hostname or "").lower()

        if not (
            hostname == expected_domain
            or hostname.endswith("." + expected_domain)
        ):
            continue

        if not is_individual_job_page(raw_url, normalized_source):
            continue
        verified_date = extract_verified_posting_date(result)
        estimated_date = (
            ""
            if verified_date
            else extract_estimated_posting_date(result)
        )
        posting_date = verified_date or estimated_date
        try:
            job = normalize_job(
                {
                    "title": result.get("title", ""),
                    "company": "",
                    "location": location,
                    "url": raw_url,
                    "source": normalized_source,
                    "description": result.get("body", ""),
                    "posting_date": posting_date,
                    "posting_date_verified":  bool(verified_date),
                     
                }
            )
        except ValueError:
            continue

        jobs.append(job)

    return deduplicate_jobs(jobs)
