"""Offline parser tests: synthetic mapping plus a real captured blob."""

from __future__ import annotations

import json
from pathlib import Path

from app.proprietary.platforms.indeed_jobs.parsers import (
    extract_jobcards_blob,
    job_results,
    parse_job,
    parse_job_detail,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


# --- synthetic mapping (always runs) ---------------------------------------


def _raw_job() -> dict:
    return {
        "jobkey": "abc123",
        "displayTitle": "Senior Data Analyst",
        "title": "Senior Data Analyst (fallback)",
        "company": "Acme Corp",
        "truncatedCompany": "Acme",
        "companyOverviewLink": "/cmp/Acme-Corp",
        "companyRating": 4.1,
        "companyReviewCount": 320,
        "formattedLocation": "New York, NY",
        "jobLocationCity": "New York",
        "jobLocationState": "NY",
        "jobLocationPostal": "10001",
        "country": "US",
        "remoteLocation": False,
        "remoteWorkModel": {"type": "REMOTE_ALWAYS", "text": "Remote"},
        "jobTypes": [],
        "salarySnippet": {"currency": "USD", "text": "$90,000 - $120,000 a year"},
        "extractedSalary": {"min": 90000, "max": 120000, "type": "YEARLY"},
        "snippet": "<ul><li>5+ years <b>SQL</b> &amp; Python</li></ul>",
        "sponsored": True,
        "newJob": False,
        "urgentlyHiring": True,
        "expired": False,
        "indeedApplyEnabled": True,
        "formattedRelativeTime": "3 days ago",
        "pubDate": 1_774_242_000_000,
        "createDate": 1_774_276_267_415,
        "thirdPartyApplyUrl": "https://ats.example.com/apply/abc123",
        "taxonomyAttributes": [
            {"label": "job-types", "attributes": [{"label": "Full-time", "suid": "x"}]},
            {"label": "remote", "attributes": [{"label": "Remote", "suid": "y"}]},
            {
                "label": "benefits",
                "attributes": [
                    {"label": "Health insurance", "suid": "a"},
                    {"label": "401(k)", "suid": "b"},
                ],
            },
        ],
    }


def test_parse_job_maps_core_fields():
    item = parse_job(_raw_job())
    assert item["jobKey"] == "abc123"
    assert item["title"] == "Senior Data Analyst"  # displayTitle wins over title
    assert item["jobUrl"] == "https://www.indeed.com/viewjob?jk=abc123"
    assert item["applyUrl"] == "https://ats.example.com/apply/abc123"
    assert item["company"] == "Acme Corp"
    assert item["companyUrl"] == "https://www.indeed.com/cmp/Acme-Corp"
    assert item["companyReviewCount"] == 320
    assert item["city"] == "New York"
    assert item["isRemote"] is True
    assert item["remoteType"] == "REMOTE_ALWAYS"
    assert item["jobTypes"] == ["Full-time"]
    assert item["benefits"] == ["Health insurance", "401(k)"]
    assert item["sponsored"] is True
    assert item["urgentlyHiring"] is True


def test_parse_job_salary_and_snippet():
    item = parse_job(_raw_job())
    sal = item["salary"]
    assert sal["salaryText"] == "$90,000 - $120,000 a year"
    assert sal["salaryMin"] == 90000
    assert sal["salaryMax"] == 120000
    assert sal["currency"] == "USD"
    assert sal["period"] == "year"
    assert sal["isEstimated"] is False
    # snippet HTML is stripped + entities decoded into plain text.
    assert item["descriptionText"] == "5+ years SQL & Python"
    assert item["descriptionHtml"] is None


def test_parse_job_dates_from_epoch_ms():
    item = parse_job(_raw_job())
    assert item["datePublished"] == "2026-03-23T05:00:00.000Z"
    assert item["age"] == "3 days ago"


def test_parse_job_respects_base_url():
    item = parse_job(_raw_job(), base_url="https://uk.indeed.com")
    assert item["jobUrl"] == "https://uk.indeed.com/viewjob?jk=abc123"
    assert item["companyUrl"] == "https://uk.indeed.com/cmp/Acme-Corp"


def test_extract_blob_anchors_on_assignment_not_first_occurrence():
    # Decoy mention precedes the real assignment; the extractor must skip it.
    html = (
        '<script>var providers=["mosaic-provider-jobcards"];</script>'
        '<script>window.mosaic.providerData["mosaic-provider-jobcards"]='
        '{"metaData":{"mosaicProviderJobCardsModel":{"results":'
        '[{"jobkey":"k1"},{"jobkey":"k2"}]}}};</script>'
    )
    blob = extract_jobcards_blob(html)
    results = job_results(blob)
    assert [r["jobkey"] for r in results] == ["k1", "k2"]


def test_extract_blob_missing_returns_none():
    assert extract_jobcards_blob("<html>just a moment...</html>") is None
    assert job_results(None) == []


# --- fixture-pinned (real captured blob) -----------------------------------


def test_fixture_blob_parses_into_items():
    fixture = _FIXTURE_DIR / "sample_jobcards.json"
    blob = json.loads(fixture.read_text())
    results = job_results(blob)
    assert len(results) == 3
    for raw in results:
        item = parse_job(raw)
        assert isinstance(item["jobKey"], str) and item["jobKey"]
        assert item["title"]
        assert item["jobUrl"].startswith("https://www.indeed.com/viewjob?jk=")
        assert "salaryText" in item["salary"]


# --- detail page (parse_job_detail) ----------------------------------------


def test_parse_job_detail_extracts_description_and_fields():
    html = (_FIXTURE_DIR / "sample_viewjob.html").read_text()
    detail = parse_job_detail(html)
    assert detail["descriptionHtml"].startswith("<div>")
    assert "Data Analyst" in detail["descriptionText"]
    assert "<div>" not in detail["descriptionText"]  # tags stripped
    assert detail["title"]
    assert detail["company"]
    assert detail["formattedLocation"]
    assert detail["jobTypes"] == ["Full-time"]
    assert detail["benefits"] == ["401(k)", "Health insurance"]
    assert detail["isRemote"] is True
    assert detail["remoteType"] == "HYBRID"
    sal = detail["salary"]
    assert (sal["salaryMin"], sal["salaryMax"], sal["period"]) == (60000, 90000, "year")


def test_parse_job_detail_omits_blank_fields():
    # A page with a header but no salary/description must not emit those keys,
    # so a merge won't clobber listing values with blanks.
    html = (
        "<html><script>window._initialData = "
        '{"jobInfoWrapperModel":{"jobInfoModel":{"jobInfoHeaderModel":'
        '{"jobTitle":"Analyst"}}}};</script></html>'
    )
    detail = parse_job_detail(html)
    assert detail == {"title": "Analyst"}


def test_parse_job_detail_not_a_job_page_returns_empty():
    assert parse_job_detail("<html>just a moment...</html>") == {}
