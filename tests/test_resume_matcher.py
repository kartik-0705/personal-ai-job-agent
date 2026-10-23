
import pytest

from src.job_agent.resume_matcher import (
    extract_skills,
    match_resume_to_job,
)


def test_extract_skills_finds_known_skills():
    text = "I use Python, pytest, SQL and REST API testing."

    skills = extract_skills(text)

    assert "Python" in skills
    assert "Pytest" in skills
    assert "SQL" in skills
    assert "API Testing" in skills


def test_extract_skills_ignores_case():
    skills = extract_skills("PYTHON and Selenium")

    assert "Python" in skills
    assert "Selenium" in skills


def test_match_resume_to_job_calculates_score():
    resume = "Python, Pytest and SQL"
    job = "Python, Pytest, SQL and Selenium"

    result = match_resume_to_job(resume, job)

    assert result["match_score"] == 75
    assert result["matched_skills"] == [
        "Python",
        "Pytest",
        "SQL",
    ]
    assert result["missing_skills"] == ["Selenium"]


def test_no_recognized_job_skills_returns_zero():
    result = match_resume_to_job(
        "I have software testing experience.",
        "Excellent communication and teamwork skills.",
    )

    assert result["match_score"] == 0
    assert result["job_skills_found"] is False


def test_empty_resume_is_rejected():
    with pytest.raises(ValueError, match="Resume text cannot be empty"):
        match_resume_to_job(
            "",
            "Python and Pytest are required.",
        )


def test_empty_job_description_is_rejected():
    with pytest.raises(
        ValueError,
        match="Job description cannot be empty",
    ):
        match_resume_to_job(
            "I use Python.",
            "",
        )


def test_non_string_resume_is_rejected():
    with pytest.raises(TypeError, match="Resume text must be a string"):
        match_resume_to_job(
            None,
            "Python is required.",
        )
