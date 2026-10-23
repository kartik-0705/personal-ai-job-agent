
from src.job_agent.core import normalize_job
from src.job_agent.database import get_saved_jobs, save_jobs


def test_save_and_retrieve_job(tmp_path):
    db_path = tmp_path / "test_jobs.db"
    job = normalize_job(
        {
            "title": "AI QA Engineer",
            "company": "Example Company",
            "location": "Gurugram",
            "url": "https://example.com/jobs/123",
            "source": "example",
            "description": "Test AI applications.",
        }
    )

    inserted = save_jobs([job], db_path)
    saved_jobs = get_saved_jobs(db_path)

    assert inserted == 1
    assert len(saved_jobs) == 1
    assert saved_jobs[0]["title"] == "AI QA Engineer"
    assert saved_jobs[0]["status"] == "Discovered"


def test_duplicate_job_is_not_inserted_twice(tmp_path):
    db_path = tmp_path / "test_jobs.db"
    job = normalize_job(
        {
            "title": "AI QA Engineer",
            "url": "https://example.com/jobs/123",
            "source": "example",
        }
    )

    assert save_jobs([job], db_path) == 1
    assert save_jobs([job], db_path) == 0
    assert len(get_saved_jobs(db_path)) == 1
