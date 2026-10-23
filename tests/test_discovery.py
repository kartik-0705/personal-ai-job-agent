from datetime import datetime, timedelta, timezone

from src.job_agent.core import normalize_job
from src.job_agent.discovery import classify_jobs_by_freshness
import pytest

from src.job_agent.discovery import (
    JobDiscoveryError,
    build_search_query,
    search_jobs,
)


def fake_search(query, region, max_results,**kwargs):
    return [
        {
            "title": "QA Automation Engineer",
            "href": (
                "https://www.linkedin.com/jobs/view/12345"
                "?utm_source=search"
            ),
            "body": "Python, API testing, and automation.",
        },
        {
            "title": "Unrelated result",
            "href": "https://example.com/jobs/123",
            "body": "This result should be filtered out.",
        },
    ]


def test_build_linkedin_query_includes_role_and_location():
    query = build_search_query(
        "LLM QA Engineer",
        "Gurugram",
        "linkedin",
    )

    assert "linkedin.com" in query
    assert "LLM QA Engineer" in query
    assert "Gurugram" in query


def test_build_query_rejects_unsupported_source():
    with pytest.raises(ValueError, match="Unsupported source"):
        build_search_query("QA Engineer", "India", "unknown")


def test_search_jobs_normalizes_and_filters_results():
    jobs = search_jobs(
        role="QA Automation Engineer",
        location="Gurugram",
        source="linkedin",
        search_callable=fake_search,
    )

    assert len(jobs) == 1
    assert jobs[0].title == "QA Automation Engineer"
    assert jobs[0].source == "linkedin"
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/12345"
    assert "Python" in jobs[0].description


def test_search_jobs_rejects_invalid_result_limit():
    with pytest.raises(ValueError, match="max_results"):
        search_jobs(
            role="QA Engineer",
            source="linkedin",
            max_results=100,
            search_callable=fake_search,
        )


def test_search_jobs_reports_provider_failure():
    def broken_search(query, region, max_results):
        raise RuntimeError("Provider unavailable")

    with pytest.raises(JobDiscoveryError, match="Public search failed"):
        search_jobs(
            role="QA Engineer",
            source="linkedin",
            search_callable=broken_search,
        )


def test_search_jobs_handles_empty_results():
    jobs = search_jobs(
        role="QA Engineer",
        source="linkedin",
        search_callable=lambda *args, **kwargs: [],
    )

    assert jobs == []

def test_search_jobs_retries_when_provider_reports_no_results():
    calls = []

    def search_with_fallback(query, region, max_results,**kwargs):
        calls.append(query)

        if len(calls) == 1:
            raise RuntimeError("No results found.")

        return [
            {
                "title": "LLM QA Engineer",
                "href": "https://www.linkedin.com/jobs/view/98765",
                "body": "LLM evaluation and Python testing.",
            }
        ]

    jobs = search_jobs(
        role="LLM QA Engineer",
        location="Gurugram",
        source="linkedin",
        search_callable=search_with_fallback,
    )

    assert len(calls) == 2
    assert len(jobs) == 1
    assert jobs[0].title == "LLM QA Engineer"
    
def test_search_jobs_filters_generic_linkedin_search_pages():
    def search_with_generic_pages(query, region, max_results,**kwargs):
        return [
            {
                "title": "1,000+ LLM Jobs in Gurugram",
                "href": "https://www.linkedin.com/jobs/llm-jobs-gurugram",
                "body": "Browse LLM jobs.",
            },
            {
                "title": "LLM QA Engineer",
                "href": "https://www.linkedin.com/jobs/view/98765",
                "body": "Python and LLM evaluation.",
            },
        ]

    jobs = search_jobs(
        role="LLM QA Engineer",
        location="Gurugram",
        source="linkedin",
        search_callable=search_with_generic_pages,
    )

    assert len(jobs) == 1
    assert jobs[0].title == "LLM QA Engineer"
    assert "/jobs/view/" in jobs[0].url

def test_freshness_filter_separates_recent_old_and_undated_jobs():
    now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

    recent = normalize_job({
        "title": "Recent AI QA Engineer",
        "url": "https://example.com/jobs/recent",
        "source": "linkedin",
        "posting_date": (now - timedelta(hours=5)).isoformat(),
        "posting_date_verified": True,
    })

    old = normalize_job({
        "title": "Old AI QA Engineer",
        "url": "https://example.com/jobs/old",
        "source": "linkedin",
        "posting_date": (now - timedelta(days=14)).isoformat(),
        "posting_date_verified": True,
    })

    undated = normalize_job({
        "title": "Undated AI QA Engineer",
        "url": "https://example.com/jobs/undated",
        "source": "linkedin",
    })

    fresh, unverified, older = classify_jobs_by_freshness(
        [recent, old, undated],
        freshness="past_24_hours",
        now=now,
    )

    assert [job.title for job in fresh] == ["Recent AI QA Engineer"]
    assert [job.title for job in unverified] == ["Undated AI QA Engineer"]
    assert [job.title for job in older] == ["Old AI QA Engineer"]


