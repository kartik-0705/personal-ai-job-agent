
import pytest

from src.job_agent.core import (
    JobListing,
    deduplicate_jobs,
    normalize_job,
)


def test_normalize_job_cleans_text_and_url():
    job = normalize_job(
        {
            "title": "  QA Engineer  ",
            "company": "  Example Ltd  ",
            "location": " Gurugram ",
            "url": (
                "https://example.com/jobs/qa"
                "?utm_source=linkedin"
            ),
            "source": " LinkedIn ",
            "description": "  Python testing  ",
        }
    )

    assert job.title == "QA Engineer"
    assert job.company == "Example Ltd"
    assert job.location == "Gurugram"
    assert job.source == "linkedin"
    assert job.description == "Python testing"
    assert job.url == "https://example.com/jobs/qa"
    assert job.retrieved_at != ""


def test_normalize_job_rejects_missing_title():
    with pytest.raises(ValueError, match="title is required"):
        normalize_job(
            {
                "url": "https://example.com/jobs/qa",
                "source": "linkedin",
            }
        )


def test_normalize_job_rejects_invalid_url():
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        normalize_job(
            {
                "title": "QA Engineer",
                "url": "not-a-valid-url",
                "source": "linkedin",
            }
        )


def test_deduplicate_jobs_keeps_first_occurrence():
    first = normalize_job(
        {
            "title": "QA Engineer",
            "url": (
                "https://example.com/jobs/qa"
                "?utm_source=linkedin"
            ),
            "source": "linkedin",
        }
    )

    duplicate = normalize_job(
        {
            "title": "QA Engineer",
            "url": "https://example.com/jobs/qa",
            "source": "indeed",
        }
    )

    unique_jobs = deduplicate_jobs([first, duplicate])

    assert len(unique_jobs) == 1
    assert unique_jobs[0].source == "linkedin"


def test_deduplicate_jobs_preserves_different_jobs():
    first = normalize_job(
        {
            "title": "QA Engineer",
            "url": "https://example.com/jobs/qa",
            "source": "linkedin",
        }
    )

    second = normalize_job(
        {
            "title": "SDET",
            "url": "https://example.com/jobs/sdet",
            "source": "indeed",
        }
    )

    assert len(deduplicate_jobs([first, second])) == 2


def test_job_listing_has_optional_fields():
    job = JobListing(
        title="QA Engineer",
        company="Example Ltd",
        location="India",
        url="https://example.com/jobs/qa",
        source="linkedin",
    )

    assert job.description == ""
    assert job.retrieved_at == ""
