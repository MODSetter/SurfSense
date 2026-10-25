from urllib.parse import SplitResult, parse_qs

from modules.documents.web_sources.pullers.puller import (
    Fit,
    Listed,
    Listing,
    Pulled,
    Puller,
    Results,
    ToolCall,
)
from modules.documents.web_sources.source_text.source_markdown import (
    about,
    source_markdown,
)


def _fit(url: SplitResult) -> Fit | None:
    host = url.hostname or ""
    if host != "indeed.com" and not host.endswith(".indeed.com"):
        return None
    # A job's own page, `/viewjob?jk=<key>`; a search page names one with `vjk`.
    return Fit.ONE if parse_qs(url.query).get("jk") else Fit.LIST


def _calls(url: str) -> list[ToolCall]:
    return [
        ToolCall("scrape", {"urls": [url], "scrape_job_details": True, "max_items": 1})
    ]


def _written(url: str, results: Results) -> Pulled | None:
    job = next(
        (
            item
            for item in results.get("scrape") or []
            if item.get("title") and not item.get("error")
        ),
        None,
    )
    if job is None:
        return None
    title = job["title"]
    location = job.get("formattedLocation")
    if job.get("isRemote"):
        location = f"{location}, remote" if location else "Remote"
    markdown = source_markdown(
        title,
        [
            ("Company", job.get("company")),
            ("Location", location),
            ("Pay", (job.get("salary") or {}).get("salaryText")),
            ("Job type", job.get("jobTypes")),
            ("Benefits", job.get("benefits")),
            ("Posted", job.get("datePublished")),
            ("Link", job.get("jobUrl") or url),
        ],
        [("Description", job.get("descriptionText"))],
    )
    return Pulled(title, markdown)


def _list_call(url: str, count: int) -> ToolCall:
    """A search's cards only: the full description is read when a job is added."""
    return ToolCall(
        "scrape", {"urls": [url], "max_items": count, "scrape_job_details": False}
    )


def _list_items(items: list[dict]) -> list[Listed]:
    return [
        Listed(
            job["jobUrl"],
            job.get("title") or job["jobUrl"],
            about(job.get("company"), job.get("formattedLocation")),
        )
        for job in items
        if job.get("jobUrl") and not job.get("error")
    ]


def _search_call(query: str, count: int) -> ToolCall:
    return ToolCall(
        "scrape",
        {
            "search_queries": [query],
            "max_items": count,
            "max_items_per_query": count,
            "scrape_job_details": False,
        },
    )


PULLER = Puller(
    id="indeed",
    plugin_id="indeed",
    fit=_fit,
    calls=_calls,
    written=_written,
    listing=Listing(_list_call, _list_items),
    search=_search_call,
)
