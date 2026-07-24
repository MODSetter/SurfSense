"""Offline tests for Indeed URL classification and search-URL building."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.proprietary.platforms.indeed_jobs.url_resolver import (
    build_search_url,
    country_domain,
    resolve_url,
)


def test_resolve_search_url():
    r = resolve_url(
        "https://www.indeed.com/jobs?q=software+engineer&l=Remote&sort=date"
    )
    assert r is not None
    assert r.kind == "search"
    assert r.value == "software engineer"
    assert r.location == "Remote"
    assert r.domain == "www.indeed.com"
    assert r.params.get("sort") == "date"


def test_resolve_company_url():
    r = resolve_url("https://www.indeed.com/cmp/Google/jobs")
    assert r is not None
    assert r.kind == "company"
    assert r.value == "Google"


def test_resolve_viewjob_url():
    r = resolve_url("https://uk.indeed.com/viewjob?jk=abc123&from=serp")
    assert r is not None
    assert r.kind == "job"
    assert r.value == "abc123"
    assert r.domain == "uk.indeed.com"


def test_resolve_country_subdomain_host():
    r = resolve_url("https://de.indeed.com/jobs?q=entwickler")
    assert r is not None
    assert r.kind == "search"
    assert r.domain == "de.indeed.com"


def test_resolve_rejects_non_indeed():
    assert resolve_url("https://www.linkedin.com/jobs?q=dev") is None
    assert resolve_url("https://notindeed.com.evil.com/jobs") is None


def test_country_domain_map():
    assert country_domain("us") == "www.indeed.com"
    assert country_domain("gb") == "uk.indeed.com"
    assert country_domain("de") == "de.indeed.com"
    assert country_domain("") == "www.indeed.com"


def test_build_search_url_basic():
    url = build_search_url(
        "data analyst",
        country="us",
        location="New York, NY",
        sort="date",
        start=20,
    )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert parsed.netloc == "www.indeed.com"
    assert parsed.path == "/jobs"
    assert qs["q"] == ["data analyst"]
    assert qs["l"] == ["New York, NY"]
    assert qs["sort"] == ["date"]
    assert qs["start"] == ["20"]


def test_build_search_url_remote_keyword_fallback_and_jobtype():
    url = build_search_url(
        "developer", country="gb", remote="remote", job_type="fulltime", from_days=7
    )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert parsed.netloc == "uk.indeed.com"
    assert qs["q"] == ["developer remote"]
    assert qs["jt"] == ["fulltime"]
    assert qs["fromage"] == ["7"]
