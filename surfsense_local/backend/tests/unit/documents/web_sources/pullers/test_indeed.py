from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.pullers.indeed import PULLER
from modules.documents.web_sources.pullers.puller import Fit, Listed, Pulled, ToolCall

pytestmark = pytest.mark.unit

JOB = "https://uk.indeed.com/viewjob?jk=abc123"


def job(**changed: object) -> dict:
    """A job as the Indeed plugin's `scrape` answers it, with its details."""
    return {
        "title": "Harbour Master",
        "jobUrl": JOB,
        "company": "Falmouth Harbour",
        "formattedLocation": "Falmouth",
        "isRemote": False,
        "salary": {"salaryText": "£38,000 a year"},
        "jobTypes": ["Full-time", "Permanent"],
        "benefits": ["Pension"],
        "datePublished": "2026-10-01",
        "descriptionText": "Keep the harbour safe at every tide.",
    } | changed


def test_a_job_is_one_source() -> None:
    """A job's own page, named by its `jk`."""
    assert PULLER.fit(urlsplit(JOB)) == Fit.ONE


def test_a_job_search_is_many_jobs() -> None:
    """Refused in the dialog rather than pulled as one source."""
    url = "https://uk.indeed.com/jobs?q=harbour&l=Falmouth"

    assert PULLER.fit(urlsplit(url)) == Fit.LIST


def test_the_job_comes_with_its_full_description() -> None:
    """A search card's description is cut short; the job's details are not."""
    assert PULLER.calls(JOB) == [
        ToolCall("scrape", {"urls": [JOB], "scrape_job_details": True, "max_items": 1})
    ]


def test_a_job_is_written_with_its_pay_and_description() -> None:
    """Pay and job type are facts a question can find."""
    pulled = PULLER.written(JOB, {"scrape": [job()]})

    assert pulled == Pulled(
        "Harbour Master",
        """# Harbour Master

- **Company:** Falmouth Harbour
- **Location:** Falmouth
- **Pay:** £38,000 a year
- **Job type:** Full-time, Permanent
- **Benefits:** Pension
- **Posted:** 2026-10-01
- **Link:** https://uk.indeed.com/viewjob?jk=abc123

## Description

Keep the harbour safe at every tide.""",
    )


def test_a_remote_job_says_so() -> None:
    """Remote is part of where the job is."""
    pulled = PULLER.written(JOB, {"scrape": [job(isRemote=True)]})

    assert pulled is not None
    assert "- **Location:** Falmouth, remote" in pulled.markdown


def test_a_job_the_plugin_could_not_open_is_nothing_to_keep() -> None:
    """The pull fails and says so, rather than keeping an empty source."""
    assert PULLER.written(JOB, {"scrape": []}) is None


def test_a_job_search_is_listed_as_its_jobs() -> None:
    """Cards only: a job's full description is read when it is added."""
    search = "https://uk.indeed.com/jobs?q=harbour&l=Falmouth"

    assert PULLER.listing is not None
    assert PULLER.listing.call(search, 20) == ToolCall(
        "scrape", {"urls": [search], "max_items": 20, "scrape_job_details": False}
    )
    assert PULLER.listing.items([job()]) == [
        Listed(JOB, "Harbour Master", "Falmouth Harbour · Falmouth")
    ]


def test_a_search_runs_on_indeed_itself() -> None:
    """Cards only; the plugin's own site, a place in the words if wanted."""
    assert PULLER.search is not None
    assert PULLER.search("harbour master", 20) == ToolCall(
        "scrape",
        {
            "search_queries": ["harbour master"],
            "max_items": 20,
            "max_items_per_query": 20,
            "scrape_job_details": False,
        },
    )
