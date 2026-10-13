"""Pure HTML/JSON -> item mapping for the Indeed scraper.

I/O-free and deterministic so it can be unit-tested against captured fixtures;
the orchestrator stamps ``scrapedAt``.

Indeed embeds job data as a JS assignment::

    window.mosaic.providerData["mosaic-provider-jobcards"]={"metaData":{...}};

The literal recurs hundreds of times in the page, so :func:`extract_jobcards_blob`
anchors on the assignment (``...]=``) and brace-matches the balanced object.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import unescape
from re import sub as _re_sub
from typing import Any

_DEFAULT_BASE = "https://www.indeed.com"

_JOBCARDS_ANCHOR = 'window.mosaic.providerData["mosaic-provider-jobcards"]='

# A /viewjob page carries the posting model in ``window._rootProps`` (JSON,
# under ``preloadedVJData``); older pages inlined it as ``window._initialData``.
_ROOT_PROPS_ANCHOR = "window._rootProps"
_ROOT_PROPS_KEY = "preloadedVJData"
_INITIAL_DATA_ANCHOR = "window._initialData"

# Indeed's extractedSalary.type -> our SalaryPeriod.
_SALARY_PERIODS = {
    "HOURLY": "hour",
    "DAILY": "day",
    "WEEKLY": "week",
    "MONTHLY": "month",
    "YEARLY": "year",
}


def _brace_match(text: str, start: int) -> str | None:
    """Return the balanced ``{...}``/``[...]`` blob at ``text[start]``, quote-aware."""
    open_ch = text[start] if start < len(text) else ""
    close_ch = {"[": "]", "{": "}"}.get(open_ch)
    if close_ch is None:
        return None
    depth = 0
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        elif ch == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\":
                    i += 1
                i += 1
        i += 1
    return None


def extract_jobcards_blob(html: str) -> dict | None:
    """Decode the ``mosaic-provider-jobcards`` assignment, or ``None`` if absent."""
    import json

    idx = html.find(_JOBCARDS_ANCHOR)
    if idx == -1:
        return None
    brace = html.find("{", idx + len(_JOBCARDS_ANCHOR))
    if brace == -1:
        return None
    blob = _brace_match(html, brace)
    if not blob:
        return None
    try:
        data = json.loads(blob)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _decode_assignment(html: str, anchor: str) -> dict | None:
    """Decode the balanced JSON object assigned after ``anchor``, or ``None``."""
    import json

    idx = html.find(anchor)
    if idx == -1:
        return None
    brace = html.find("{", idx + len(anchor))
    if brace == -1:
        return None
    blob = _brace_match(html, brace)
    if not blob:
        return None
    try:
        data = json.loads(blob)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def extract_initial_data(html: str) -> dict | None:
    """Return a /viewjob posting model rooted at ``jobInfoWrapperModel``.

    Prefers ``window._rootProps`` (JSON) unwrapped at ``preloadedVJData``; falls
    back to a legacy inline ``window._initialData`` blob. ``window._initialData``
    is now a JS object literal that references other globals, so it is not JSON
    and is skipped when the JSON parse fails.
    """
    root = _decode_assignment(html, _ROOT_PROPS_ANCHOR)
    if isinstance(root, dict):
        vj = root.get(_ROOT_PROPS_KEY)
        if isinstance(vj, dict) and vj.get("jobInfoWrapperModel"):
            return vj
    legacy = _decode_assignment(html, _INITIAL_DATA_ANCHOR)
    if isinstance(legacy, dict) and legacy.get("jobInfoWrapperModel"):
        return legacy
    return None


def job_results(blob: dict | None) -> list[dict[str, Any]]:
    """Return the raw job records from a decoded blob."""
    if not isinstance(blob, dict):
        return []
    results = (
        blob.get("metaData", {}).get("mosaicProviderJobCardsModel", {}).get("results")
    )
    if not isinstance(results, list):
        return []
    return [r for r in results if isinstance(r, dict)]


def _utc_from_ms(value: Any) -> str | None:
    """Epoch milliseconds -> millisecond ISO string."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    dt = datetime.fromtimestamp(float(value) / 1000.0, tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _int(value: Any) -> int | None:
    """Coerce to int, dropping bools."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _abs_url(path: Any, base_url: str) -> str | None:
    """Resolve an Indeed-relative path against ``base_url``; keep absolute URLs."""
    if not isinstance(path, str) or not path:
        return None
    if path.startswith("http"):
        return path
    return f"{base_url}{path if path.startswith('/') else '/' + path}"


def _clean_snippet(snippet: Any) -> str | None:
    """Strip tags and decode entities into plain text."""
    if not isinstance(snippet, str) or not snippet:
        return None
    text = _re_sub(r"<[^>]+>", " ", snippet)
    text = unescape(text)
    return _re_sub(r"\s+", " ", text).strip() or None


def _taxonomy(raw: dict[str, Any]) -> dict[str, list[str]]:
    """Flatten ``taxonomyAttributes`` into ``{group label: [attribute labels]}``."""
    out: dict[str, list[str]] = {}
    for group in raw.get("taxonomyAttributes") or []:
        if not isinstance(group, dict):
            continue
        label = group.get("label")
        attrs = group.get("attributes")
        if isinstance(label, str) and isinstance(attrs, list):
            out[label] = [
                a["label"]
                for a in attrs
                if isinstance(a, dict) and isinstance(a.get("label"), str)
            ]
    return out


def _job_types(raw: dict[str, Any], taxo: dict[str, list[str]]) -> list[str]:
    """Job types from ``jobTypes`` then the taxonomy, deduped and order-stable."""
    seen: dict[str, None] = {}
    for jt in raw.get("jobTypes") or []:
        if isinstance(jt, str):
            seen.setdefault(jt, None)
    for label in ("job-types", "job-types-cc"):
        for jt in taxo.get(label, []):
            seen.setdefault(jt, None)
    return list(seen)


def _salary(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten salary from ``salarySnippet`` (text) + ``extractedSalary`` (bounds)."""
    snippet = raw.get("salarySnippet") or {}
    extracted = raw.get("extractedSalary") or {}
    estimated = raw.get("estimatedSalary") or {}
    source = extracted or estimated
    text = snippet.get("text") if isinstance(snippet, dict) else None
    return {
        "salaryText": text if isinstance(text, str) else None,
        "salaryMin": source.get("min") if isinstance(source, dict) else None,
        "salaryMax": source.get("max") if isinstance(source, dict) else None,
        "currency": snippet.get("currency") if isinstance(snippet, dict) else None,
        "period": _SALARY_PERIODS.get(
            source.get("type") if isinstance(source, dict) else None
        ),
        "isEstimated": bool(estimated) and not extracted,
    }


def _is_remote(raw: dict[str, Any], taxo: dict[str, list[str]]) -> bool:
    """Resolve remote/hybrid across Indeed's several signals."""
    if raw.get("remoteLocation") is True:
        return True
    if isinstance(raw.get("remoteWorkModel"), dict):
        return True
    return bool(taxo.get("remote"))


def parse_job(raw: dict[str, Any], *, base_url: str = _DEFAULT_BASE) -> dict[str, Any]:
    """Map one raw ``results[]`` record to a flat item dict.

    ``base_url`` is the country domain the record came from, so job and company
    URLs resolve to the right host.
    """
    taxo = _taxonomy(raw)
    job_key = raw.get("jobkey")
    remote_model = raw.get("remoteWorkModel")
    return {
        "jobKey": job_key if isinstance(job_key, str) else None,
        "title": raw.get("displayTitle") or raw.get("title"),
        "jobUrl": f"{base_url}/viewjob?jk={job_key}" if job_key else None,
        "applyUrl": raw.get("thirdPartyApplyUrl") or None,
        "company": raw.get("company") or raw.get("truncatedCompany"),
        "companyUrl": _abs_url(raw.get("companyOverviewLink"), base_url),
        "companyRating": raw.get("companyRating"),
        "companyReviewCount": _int(raw.get("companyReviewCount")),
        "formattedLocation": raw.get("formattedLocation"),
        "city": raw.get("jobLocationCity"),
        "state": raw.get("jobLocationState"),
        "postalCode": raw.get("jobLocationPostal"),
        "country": raw.get("country"),
        "isRemote": _is_remote(raw, taxo),
        "remoteType": remote_model.get("type")
        if isinstance(remote_model, dict)
        else None,
        "jobTypes": _job_types(raw, taxo),
        "salary": _salary(raw),
        "benefits": taxo.get("benefits", []),
        "descriptionText": _clean_snippet(raw.get("snippet")),
        "descriptionHtml": None,
        "sponsored": raw.get("sponsored"),
        "isNew": raw.get("newJob"),
        "urgentlyHiring": raw.get("urgentlyHiring"),
        "expired": raw.get("expired"),
        "indeedApplyEnabled": raw.get("indeedApplyEnabled"),
        "age": raw.get("formattedRelativeTime"),
        "datePublished": _utc_from_ms(raw.get("pubDate")),
        "createdAt": _utc_from_ms(raw.get("createDate")),
    }


def _detail_salary(hdr: dict[str, Any]) -> dict[str, Any] | None:
    """Salary from the detail header's flat ``salaryMin/Max/Currency/Type`` fields."""
    smin = hdr.get("salaryMin")
    smax = hdr.get("salaryMax")
    if smin is None and smax is None:
        return None
    return {
        "salaryText": None,
        "salaryMin": smin,
        "salaryMax": smax,
        "currency": hdr.get("salaryCurrency"),
        "period": _SALARY_PERIODS.get(hdr.get("salaryType")),
        "isEstimated": False,
    }


def parse_job_detail(html: str, *, base_url: str = _DEFAULT_BASE) -> dict[str, Any]:
    """Map a /viewjob page to enrichment fields (empty dict if not a job page).

    Returns only fields the detail page actually carries, so the caller can merge
    it onto a listing item without clobbering known values with blanks. The full
    description (``sanitizedJobDescription``) is the field listings never have.
    """
    data = extract_initial_data(html)
    if not isinstance(data, dict):
        return {}
    jim = (data.get("jobInfoWrapperModel") or {}).get("jobInfoModel") or {}
    if not isinstance(jim, dict):
        return {}
    hdr = jim.get("jobInfoHeaderModel")
    hdr = hdr if isinstance(hdr, dict) else {}
    taxo = _taxonomy(hdr)
    desc_html = jim.get("sanitizedJobDescription")
    desc_html = desc_html if isinstance(desc_html, str) and desc_html else None
    remote_model = hdr.get("remoteWorkModel")
    out: dict[str, Any] = {
        "descriptionHtml": desc_html,
        "descriptionText": _clean_snippet(desc_html),
        "title": hdr.get("jobTitle"),
        "company": hdr.get("companyName"),
        "companyUrl": _abs_url(hdr.get("companyOverviewLink"), base_url),
        "formattedLocation": hdr.get("formattedLocation") or data.get("jobLocation"),
        "remoteType": remote_model.get("type")
        if isinstance(remote_model, dict)
        else None,
        "jobTypes": _job_types(hdr, taxo),
        "benefits": taxo.get("benefits", []),
        "salary": _detail_salary(hdr),
    }
    if _is_remote(hdr, taxo):
        out["isRemote"] = True
    return {k: v for k, v in out.items() if v not in (None, [], {})}
