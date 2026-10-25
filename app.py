
import streamlit as st
from src.job_agent.database import save_jobs, get_saved_jobs
from src.job_agent.document_reader import extract_text_from_file
from src.job_agent.resume_matcher import match_resume_to_job
from src.job_agent.discovery import (
    SOURCE_DOMAINS,
    JobDiscoveryError,
    search_jobs,
    build_freshness_url,
    classify_jobs_by_freshness,
)
st.set_page_config(
    page_title="Personal AI Job Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Personal AI Job Application Agent")
st.write(
    "Discover jobs, analyze requirements, and manage "
    "your job applications in one place."
)

if "saved_job_preferences" not in st.session_state:
    st.session_state["saved_job_preferences"] = None

if "discovered_jobs" not in st.session_state:
    st.session_state["discovered_jobs"] = []

if "unverified_jobs" not in st.session_state:
    st.session_state["unverified_jobs"] = []

if "older_job_count" not in st.session_state:
    st.session_state["older_job_count"] = 0

st.header("Job Discovery")

with st.form("job_search_form"):
    target_role = st.text_input(
        "Target job role",
        value="LLM QA Engineer",
        placeholder="e.g. AI Evaluation Engineer",
    )

    location = st.text_input(
        "Preferred location",
        value="Gurugram",
        placeholder="e.g. Bengaluru or Remote",
    )
    freshness = st.selectbox(
    "Jobs posted within",
    options=["past_24_hours", "past_3_days", "past_week"],
    format_func=lambda value: {
        "past_24_hours": "Last 24 hours",
        "past_3_days": "Last 3 days",
        "past_week": "Last 7 days",
    }[value],
    index=2,
)

    source = st.selectbox(
        "Job platform",
        options=list(SOURCE_DOMAINS.keys()),
        format_func=lambda value: {
            "linkedin": "LinkedIn",
            "naukri": "Naukri",
            "indeed": "Indeed",
        }[value],
    )

    experience_level = st.selectbox(
        "Experience level",
        [
            "Fresher",
            "0–2 years",
            "2–4 years",
            "4–6 years",
            "6+ years",
        ],
        index=1,
    )

    remote_only = st.checkbox("Remote jobs only")

    submitted = st.form_submit_button(
        "Search jobs",
        type="primary",
    )

if submitted:
    if not target_role.strip():
        st.error("Please enter a target job role.")
    else:
        preferences = {
            "target_role": target_role.strip(),
            "location": location.strip(),
            "source": source,
            "experience_level": experience_level,
            "remote_only": remote_only,
            "freshness": freshness,
        }

        st.session_state["saved_job_preferences"] = preferences

        with st.spinner("Searching public job pages..."):
            try:
                jobs = search_jobs(
                    role=preferences["target_role"],
                    location=preferences["location"],
                    source=preferences["source"],
                    max_results=10,
                    freshness=preferences["freshness"],
                )
                recent_jobs, unverified_jobs, older_jobs = classify_jobs_by_freshness(
                    jobs,
                    freshness=preferences["freshness"],
                )

                newly_saved = save_jobs(jobs)

                
                verified_count = sum(
                   1 for job in recent_jobs if job.posting_date_verified
                )
                estimated_count = sum(
                    1 for job in recent_jobs
                    if job.posting_date and not job.posting_date_verified
                )

                st.success(
                    f"Found {len(jobs)} candidate(s). "
                    f"{verified_count} have verified posting dates within your "
                    f"selected range; {estimated_count} have estimated recent dates; "
                    f"{len(unverified_jobs)} have no usable posting date; "
                    f"{len(older_jobs)} are older than the selected range. "
                    f"Saved {newly_saved} new job(s)."
                )


                def job_to_row(job):
                    if not job.posting_date:
                        date_status = "Unverified"
                    elif job.posting_date_verified:
                        date_status = "Verified posting date"
                    else:
                        date_status = "Estimated from search result"

                    return {
                        "title": job.title,
                        "source": job.source,
                        "url": job.url,
                        "search_snippet": job.description,
                        "posting_date": job.posting_date or "Not Provided",
                        "date_status": date_status,
                        "retrieved_at": job.retrieved_at,
                    }

                st.session_state["discovered_jobs"] = [
                     job_to_row(job) for job in jobs
                ]
                st.session_state["unverified_jobs"] = [
                      job_to_row(job) for job in unverified_jobs
                ]
                st.session_state["older_job_count"] = len(older_jobs)
                st.session_state["last_search_error"] = None
                
            except JobDiscoveryError as exc:
                st.session_state["last_search_error"] = str(exc)



if st.session_state.get("last_search_error"):
    st.error(
        "Job search failed: "
        + st.session_state["last_search_error"]
    )

preferences = st.session_state["saved_job_preferences"]

if preferences:
    st.subheader("Search preferences")
    col1, col2, col3 = st.columns(3)

    col1.metric("Target role", preferences["target_role"])
    col2.metric("Location", preferences["location"] or "Any")
    col3.metric("Experience", preferences["experience_level"])

jobs = st.session_state["discovered_jobs"]

st.divider()
st.header("Discovered Job Pages")
unverified_jobs = st.session_state.get("unverified_jobs", [])

if unverified_jobs:
    st.caption(
        "These jobs were discovered, but their original posting dates "
        "could not be verified. Open each link to check the vacancy."
    )

    st.dataframe(
        unverified_jobs,
        column_config={
            "title": st.column_config.TextColumn("Job title"),
            "source": st.column_config.TextColumn("Platform"),
            "url": st.column_config.LinkColumn(
                "Job link",
                display_text="Open job",
            ),
            "search_snippet": st.column_config.TextColumn(
                "Description snippet",
                width="large",
            ),
            "posting_date": st.column_config.TextColumn(
                "Posting date"
            ),
            "retrieved_at": st.column_config.TextColumn(
                "Discovered at (UTC)"
            ),
            "date_status": st.column_config.TextColumn("Date verification status"),
        },
        hide_index=True,
        use_container_width=True,
    )
else:
    st.info("No unverified job candidates are available.")

if jobs:
    st.caption(
        f"{len(jobs)} public search result(s). "
        "Open each link to verify the actual vacancy, requirements, "
        "location, and whether applications are still open."
    )

    st.dataframe(
        jobs,
        column_config={
            "title": st.column_config.TextColumn("Search result"),
            "source": st.column_config.TextColumn("Source"),
            "url": st.column_config.LinkColumn(
                "Open original page",
                display_text="Open job page",
            ),
            "search_snippet": st.column_config.TextColumn(
                "Search snippet",
                width="large",
            ),
            "posting_date": st.column_config.TextColumn(
                "Posting date (UTC)"
            ),
            "retrieved_at": st.column_config.TextColumn(
                "Retrieved at (UTC)"
            ),
        },
        hide_index=True,
        use_container_width=True,
    )
elif not st.session_state.get("last_search_error"):
    st.info("Enter your search criteria and select Search jobs.")

st.divider()
st.caption(
    "Milestone 2: public job discovery. "
    "Application submission and AI resume matching are not implemented yet."
)

if preferences and preferences["source"] == "linkedin":
    filtered_url = build_freshness_url(
        role=preferences["target_role"],
        location=preferences["location"],
        freshness=preferences["freshness"],
    )
    st.link_button(
        "Open matching recent jobs on LinkedIn",
        filtered_url,
    )
st.divider()
st.header("Previously Saved Jobs")

saved_jobs = get_saved_jobs()

if saved_jobs:
    st.dataframe(
        saved_jobs,
        column_config={
            "url": st.column_config.LinkColumn(
                "Job URL",
                display_text="Open job",
            ),
        },
        hide_index=True,
        use_container_width=True,
    )
else:
    st.info("No jobs have been saved yet.")


st.divider()
st.header("AI Resume-to-Job Matching")


# ---------------------------------------------------------
# Resume-to-Job Matching with File Uploads
# ---------------------------------------------------------

st.divider()
st.header("📄 AI Resume-to-Job Matching")
st.write(
    "Upload a resume and a job description, or paste their text, "
    "to identify matching skills and potential skill gaps."
)

with st.container(border=True):
    st.subheader("Your documents")

    resume_tab, resume_paste_tab = st.tabs(
        ["📤 Upload Resume", "✍️ Paste Resume"]
    )

    with resume_tab:
        resume_file = st.file_uploader(
            "Choose your resume",
            type=["pdf", "docx", "txt"],
            max_upload_size=5,
            key="resume_upload",
        )

    with resume_paste_tab:
        resume_manual = st.text_area(
            "Resume text",
            height=180,
            placeholder="Paste your resume here...",
            key="resume_manual",
        )

    st.divider()

    jd_tab, jd_paste_tab = st.tabs(
        ["📄 Upload Job Description", "✍️ Paste Job Description"]
    )

    with jd_tab:
        jd_file = st.file_uploader(
            "Choose a job description",
            type=["pdf", "docx", "txt"],
            max_upload_size=5,
            key="jd_upload",
        )

    with jd_paste_tab:
        jd_manual = st.text_area(
            "Job description text",
            height=180,
            placeholder="Paste the complete job description here...",
            key="jd_manual",
        )

    st.caption(
        "Supported formats: PDF, DOCX and TXT. Maximum 5 MB per file. "
        "Pasted text takes priority if both options are supplied."
    )

    analyze = st.button(
        "✨ Analyze Resume Match",
        type="primary",
        use_container_width=True,
        key="analyze_uploaded_resume",
    )


def get_document_text(uploaded_file, pasted_text):
    if pasted_text and pasted_text.strip():
        return pasted_text.strip()

    return extract_text_from_file(uploaded_file)


if analyze:
    try:
        resume_text = get_document_text(resume_file, resume_manual)
        job_description = get_document_text(jd_file, jd_manual)

        result = match_resume_to_job(
            resume_text=resume_text,
            job_description=job_description,
        )

        if not result["job_skills_found"]:
            st.warning(
                "No recognized skills were found in the job description. "
                "Try a more detailed job description."
            )
        else:
            st.subheader("Your matching results")

            score = result["match_score"]
            matched = result["matched_skills"]
            missing = result["missing_skills"]

            metric1, metric2, metric3 = st.columns(3)

            metric1.metric("Skill Match", f"{score}%")
            metric2.metric("Matching Skills", len(matched))
            metric3.metric("Potential Skill Gaps", len(missing))

            st.progress(score / 100)

            st.caption(
                "This score measures recognized keyword overlap. "
                "It is not a hiring prediction or a measure of proficiency."
            )

            left, right = st.columns(2)

            with left:
                with st.container(border=True):
                    st.markdown("#### ✅ Matching Skills")

                    if matched:
                        for skill in matched:
                            st.write(f"✓ {skill}")
                    else:
                        st.info("No matching skills identified.")

            with right:
                with st.container(border=True):
                    st.markdown("#### 🎯 Potential Skill Gaps")

                    if missing:
                        for skill in missing:
                            st.write(f"• {skill}")
                    else:
                        st.success(
                            "No gaps among the recognized job skills."
                        )

            with st.expander("View detected skills"):
                st.markdown("**Resume skills**")
                st.write(
                    ", ".join(result["resume_skills"]) or "None detected"
                )

                st.markdown("**Job description skills**")
                st.write(
                    ", ".join(result["job_skills"]) or "None detected"
                )

    except (ValueError, TypeError) as exc:
        st.error(str(exc))

