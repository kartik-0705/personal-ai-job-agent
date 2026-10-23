
import re


# Canonical skill names and common ways they appear in resumes
# and job descriptions.
SKILL_KEYWORDS = {
    "Python": ["python"],
    "Pytest": ["pytest", "py.test"],
    "API Testing": ["api testing", "api test", "rest api testing"],
    "REST API": ["rest api", "restful api"],
    "Manual Testing": ["manual testing", "manual tester"],
    "Test Automation": ["test automation", "automation testing"],
    "Selenium": ["selenium"],
    "Playwright": ["playwright"],
    "Appium": ["appium"],
    "SQL": ["sql", "structured query language"],
    "Git": ["git", "github", "gitlab"],
    "CI/CD": ["ci/cd", "continuous integration", "continuous delivery"],
    "Java": ["java"],
    "JavaScript": ["javascript"],
    "Postman": ["postman"],
    "BDD": ["bdd", "behavior driven development"],
    "LLM": ["llm", "large language model", "large language models"],
    "RAG": ["rag", "retrieval augmented generation"],
    "Prompt Engineering": ["prompt engineering", "prompt design"],
    "LangChain": ["langchain"],
    "Pydantic": ["pydantic"],
    "Streamlit": ["streamlit"],
    "Ollama": ["ollama"],
    "Machine Learning": ["machine learning"],
    "Natural Language Processing": [
        "natural language processing",
        "nlp",
    ],
}


def _contains_keyword(text: str, keyword: str) -> bool:
    """Check for a keyword without matching it inside unrelated words."""
    pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def extract_skills(text: str) -> list[str]:
    """Return recognized skills found in the supplied text."""
    if not isinstance(text, str):
        raise TypeError("Text must be a string.")

    found_skills = []

    for skill, keywords in SKILL_KEYWORDS.items():
        if any(_contains_keyword(text, keyword) for keyword in keywords):
            found_skills.append(skill)

    return found_skills


def match_resume_to_job(
    resume_text: str,
    job_description: str,
) -> dict:
    """
    Compare recognized skills in a resume and job description.

    The score is the percentage of recognized job-description skills
    also found in the resume. It is a keyword-based estimate, not a
    prediction of hiring success or proof of practical proficiency.
    """
    if not isinstance(resume_text, str):
        raise TypeError("Resume text must be a string.")

    if not isinstance(job_description, str):
        raise TypeError("Job description must be a string.")

    if not resume_text.strip():
        raise ValueError("Resume text cannot be empty.")

    if not job_description.strip():
        raise ValueError("Job description cannot be empty.")

    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_description)

    matched_skills = [
        skill for skill in job_skills if skill in resume_skills
    ]
    missing_skills = [
        skill for skill in job_skills if skill not in resume_skills
    ]

    if job_skills:
        match_score = round(
            len(matched_skills) / len(job_skills) * 100
        )
    else:
        match_score = 0

    return {
        "match_score": match_score,
        "resume_skills": resume_skills,
        "job_skills": job_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "job_skills_found": bool(job_skills),
    }
