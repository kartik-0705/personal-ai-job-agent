
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    retrieved_at: str = ""
    posting_date: str = ""
    posting_date_verified: bool = False


def normalize_job(raw: dict) -> JobListing:
    """Convert a raw job record into a consistent data model."""

    title = str(raw.get("title") or "").strip()
    url = str(raw.get("url") or "").strip()
    source = str(raw.get("source") or "").strip().lower()

    if not title:
        raise ValueError("Job title is required.")

    if not url:
        raise ValueError("Job URL is required.")

    if not source:
        raise ValueError("Job source is required.")

    parts = urlsplit(url)

    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Job URL must be a valid HTTP or HTTPS URL.")

    # Remove common tracking parameters without removing
    # the meaningful query parameters used by the website.
    clean_query = [
        (key, value)
        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True,
        )
        if key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
        and not key.lower().startswith("utm_")
    ]

    clean_url = urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or "/",
            urlencode(clean_query),
            "",  # Tracking fragments are not part of the job identity.
        )
    )

    retrieved_at = datetime.now(timezone.utc).isoformat()

    return JobListing(
        title=title,
        company=str(raw.get("company") or "").strip(),
        location=str(raw.get("location") or "").strip(),
        url=clean_url,
        source=source,
        description=str(raw.get("description") or "").strip(),
        retrieved_at=retrieved_at,
        posting_date=str(raw.get("posting_date") or "").strip(),
        posting_date_verified=bool(raw.get("posting_date_verified", False)),
        
    )


def deduplicate_jobs(jobs: list[JobListing]) -> list[JobListing]:
    """Keep the first occurrence of each normalized job URL."""

    unique_jobs = []
    seen_urls = set()

    for job in jobs:
        if job.url in seen_urls:
            continue

        seen_urls.add(job.url)
        unique_jobs.append(job)

    return unique_jobs
