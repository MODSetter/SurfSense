"""Offline parser tests: synthetic mapping plus a real captured blob."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from proprietary.indeed import parsers
from proprietary.indeed.parsers import (
    _brace_match,
    extract_jobcards_blob,
    job_results,
    parse_job,
    parse_job_detail,
    parse_job_detail_model,
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
    # A live /viewjob page (scrubbed): window._rootProps with preloadedVJData,
    # beside the non-JSON window._initialData literal.
    html = (_FIXTURE_DIR / "viewjob_live.html").read_text(encoding="utf-8")
    detail = parse_job_detail(html)
    assert detail["descriptionHtml"].startswith("<div>")
    assert "<div>" not in detail["descriptionText"]  # tags stripped
    _assert_live_detail(detail)


def test_parse_job_detail_reads_header_taxonomy_and_legacy_salary():
    # Older pages put job types, benefits, remote and pay on the header itself.
    hdr = {
        "jobTitle": "Data Analyst",
        "salaryMin": 60000,
        "salaryMax": 90000,
        "salaryCurrency": "USD",
        "salaryType": "YEARLY",
        "remoteWorkModel": {"type": "HYBRID"},
        "taxonomyAttributes": [
            {"label": "job-types", "attributes": [{"label": "Full-time"}]},
            {
                "label": "benefits",
                "attributes": [{"label": "401(k)"}, {"label": "Health insurance"}],
            },
            {"label": "remote", "attributes": [{"label": "Hybrid work"}]},
        ],
    }
    model = {"jobInfoWrapperModel": {"jobInfoModel": {"jobInfoHeaderModel": hdr}}}
    detail = parse_job_detail_model(model)
    assert detail["jobTypes"] == ["Full-time"]
    assert detail["benefits"] == ["401(k)", "Health insurance"]
    assert detail["isRemote"] is True
    assert detail["remoteType"] == "HYBRID"
    sal = detail["salary"]
    assert (sal["salaryMin"], sal["salaryMax"], sal["period"]) == (60000, 90000, "year")
    assert (sal["currency"], sal["salaryText"], sal["isEstimated"]) == (
        "USD",
        None,
        False,
    )


def test_parse_job_detail_reads_rootprops_shape():
    # Live /viewjob assigns window._rootProps (JSON) with the model under
    # preloadedVJData; window._initialData is now a non-JSON JS literal that
    # references other globals and must be skipped, not misparsed.
    html = (
        "<html><script>window._initialData = { ssr: true, "
        "viewJobClientSideModel: window._rootProps.preloadedVJData };</script>"
        '<script>window._rootProps = {"url":"x","preloadedVJData":'
        '{"jobInfoWrapperModel":{"jobInfoModel":'
        '{"sanitizedJobDescription":"<p>Full JD text</p>",'
        '"jobInfoHeaderModel":{"jobTitle":"Data Analyst",'
        '"companyName":"Acme"}}}}};</script></html>'
    )
    detail = parse_job_detail(html)
    assert detail["title"] == "Data Analyst"
    assert detail["company"] == "Acme"
    assert detail["descriptionHtml"] == "<p>Full JD text</p>"
    assert detail["descriptionText"] == "Full JD text"


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


# --- live captures (scrubbed): spa=1 body, search and company pages --------


def _spa_body() -> dict:
    """A live ``/viewjob?jk=...&spa=1`` body, the model a /viewjob page preloads."""
    raw = (_FIXTURE_DIR / "viewjob_spa.json").read_text(encoding="utf-8")
    return json.loads(raw)["body"]


def _assert_live_detail(detail: dict) -> None:
    assert detail["jobKey"] == "17c2d37519bd8374"
    assert detail["title"] == "Software Engineer I"
    assert detail["company"] == "Indeed"
    # The header's link carries per-view tracking (campaignid, tk, fromjk).
    assert detail["companyUrl"] == "https://www.indeed.com/cmp/Indeed"
    assert detail["companyRating"] == 4.2
    assert detail["companyReviewCount"] == 1792
    assert detail["jobTypes"] == ["Full-time"]
    assert detail["country"] == "US"
    assert detail["formattedLocation"] == "Austin, TX"
    assert len(detail["descriptionText"]) > 1000
    # The header's salaryMin/Max are null on live pages; salaryInfoModel has it.
    assert detail["salary"] == {
        "salaryText": "$94,000 - $142,000 a year",
        "salaryMin": 94000,
        "salaryMax": 142000,
        "currency": "USD",
        "period": "year",
        "isEstimated": False,
    }


def test_parse_job_detail_model_maps_live_spa_body():
    _assert_live_detail(parse_job_detail_model(_spa_body()))


def test_detail_salary_falls_back_to_company_tab_then_header():
    body = _spa_body()
    body["salaryInfoModel"] = None
    sal = parse_job_detail_model(body)["salary"]
    assert (sal["salaryMin"], sal["salaryMax"], sal["period"]) == (
        94000,
        142000,
        "year",
    )
    assert sal["salaryText"] is None

    body["companyTabModel"] = None
    hdr = body["jobInfoWrapperModel"]["jobInfoModel"]["jobInfoHeaderModel"]
    hdr.update(salaryMin=20, salaryMax=25, salaryCurrency="USD", salaryType="HOURLY")
    sal = parse_job_detail_model(body)["salary"]
    assert (sal["salaryMin"], sal["salaryMax"], sal["period"]) == (20, 25, "hour")
    assert sal["currency"] == "USD"


def test_detail_salary_flags_an_estimate():
    body = _spa_body()
    body["salaryInfoModel"]["salarySource"] = "ESTIMATED"
    assert parse_job_detail_model(body)["salary"]["isEstimated"] is True


def test_detail_job_types_split_the_metadata_line():
    body = _spa_body()
    jim = body["jobInfoWrapperModel"]["jobInfoModel"]
    jim["jobMetadataHeaderModel"]["jobType"] = "Full-time, Contract"
    assert parse_job_detail_model(body)["jobTypes"] == ["Full-time", "Contract"]


def test_parse_job_detail_model_rejects_non_models():
    assert parse_job_detail_model(None) == {}
    assert parse_job_detail_model({"jobKey": "x"}) == {}


def _search_page() -> str:
    return (_FIXTURE_DIR / "search_page_jobcards.html").read_text(encoding="utf-8")


def test_raw_decode_matches_the_brace_matcher_on_a_live_page():
    html = _search_page()
    anchor = 'window.mosaic.providerData["mosaic-provider-jobcards"]='
    brace = html.find("{", html.find(anchor) + len(anchor))
    expected = json.loads(_brace_match(html, brace))
    blob = extract_jobcards_blob(html)
    assert blob == expected
    assert len(job_results(blob)) == 12


def test_brace_matcher_is_the_fallback(monkeypatch):
    class _Failing:
        def raw_decode(self, *_args):
            raise ValueError("forced")

    monkeypatch.setattr(parsers, "_JSON", _Failing())
    assert len(job_results(extract_jobcards_blob(_search_page()))) == 12


def test_live_search_cards_with_no_rating_read_unknown():
    items = [parse_job(r) for r in job_results(extract_jobcards_blob(_search_page()))]
    unrated = [i for i in items if i["companyRating"] is None]
    assert unrated, "the capture holds cards Indeed sent with companyRating 0"
    assert all(i["companyReviewCount"] is None for i in unrated)
    rated = next(i for i in items if i["jobKey"] == "17c2d37519bd8374")
    assert (rated["companyRating"], rated["companyReviewCount"]) == (4.2, 1791)
    assert rated["companyUrl"] == "https://www.indeed.com/cmp/Indeed"


def test_live_search_capture_keeps_no_tracking_tokens():
    # Each viewJobLink carries per-view tokens, and sponsored cards an ad blob;
    # the capture keeps the parameters but not their live values.
    queries = [
        parse_qs(urlparse(raw["viewJobLink"]).query)
        for raw in job_results(extract_jobcards_blob(_search_page()))
    ]
    assert sum("ad" in query for query in queries) == 4
    for query in queries:
        for key in ("tk", "xkcb", "advn", "adid", "ad"):
            assert query.get(key, ["SCRUBBED"]) == ["SCRUBBED"], key


def test_live_company_page_cards_read_unknown_rating():
    html = (_FIXTURE_DIR / "company_page_jobcards.html").read_text(encoding="utf-8")
    items = [parse_job(r) for r in job_results(extract_jobcards_blob(html))]
    assert len(items) == 3
    for item in items:
        assert item["companyRating"] is None
        assert item["companyReviewCount"] is None
        assert item["companyUrl"] is None  # the scraper fills it from the slug


def test_rating_zero_with_reviews_keeps_the_count():
    raw = {**_raw_job(), "companyRating": 0, "companyReviewCount": 12}
    item = parse_job(raw)
    assert item["companyRating"] is None
    assert item["companyReviewCount"] == 12


def test_spa_model_reads_the_viewjob_model_from_a_spa_answer():
    from proprietary.indeed.parsers import spa_model

    text = (_FIXTURE_DIR / "viewjob_spa.json").read_text(encoding="utf-8")
    model = spa_model(text)
    assert model is not None and model["jobKey"] == "17c2d37519bd8374"
    assert parse_job_detail_model(model)["salary"]["salaryMin"] == 94000
    # A wall, an error answer or a body with no job reads as no model.
    assert spa_model("<html>Just a moment</html>") is None
    assert spa_model('{"status": "error", "body": null}') is None
    assert spa_model('{"status": "success", "body": {"jobKey": "x"}}') is None


def test_inline_viewjob_reads_the_first_job_s_answer_from_a_search_page():
    from proprietary.indeed.parsers import inline_viewjob

    answer = (_FIXTURE_DIR / "viewjob_spa.json").read_text(encoding="utf-8")
    html = f'<script>{{"autoOpenTwoPaneJobKey":"x","autoOpenTwoPaneViewjobResponse":{answer}}}</script>'
    model = inline_viewjob(html)
    assert model is not None and model["jobKey"] == "17c2d37519bd8374"
    assert inline_viewjob("<html>no pane</html>") is None


def test_a_null_inline_answer_is_not_the_next_object_along():
    other = {
        "status": "success",
        "body": {
            "jobKey": "k9",
            "jobInfoWrapperModel": {
                "jobInfoModel": {"sanitizedJobDescription": "<p>not the inline job</p>"}
            },
        },
    }
    html = (
        '<script>{"autoOpenTwoPaneViewjobResponse":null,'
        f'"other":{json.dumps(other)}}}</script>'
    )
    assert parsers.inline_viewjob(html) is None
