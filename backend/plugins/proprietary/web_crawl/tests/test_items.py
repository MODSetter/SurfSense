"""``crawl_item``: the wire shape, with links and contacts bounded and counted."""

from proprietary.web_crawl import CrawlOutcomeStatus
from proprietary.web_crawl.items import MAX_CONTACTS, crawl_item
from proprietary.web_crawl.site_crawler import CrawlPage


def _page(**fields) -> CrawlPage:
    return CrawlPage(
        url="https://e.com/",
        status=CrawlOutcomeStatus.SUCCESS,
        depth=0,
        content="x" * 100,
        **fields,
    )


def test_contacts_are_capped_with_their_totals() -> None:
    """A directory page listed thousands of profiles in every item."""
    socials = [f"https://x.com/user{i}" for i in range(120)]
    item = crawl_item(
        _page(contacts={"emails": ["a@e.com"], "phones": [], "socials": socials}),
        max_length=50,
    )
    assert item["contacts"]["socials"] == socials[:MAX_CONTACTS]
    assert item["contacts"]["emails"] == ["a@e.com"]
    assert item["contactsTotal"] == {"emails": 1, "phones": 0, "socials": 120}


def test_links_report_how_many_the_page_had() -> None:
    links = [{"url": f"https://e.com/{i}", "kind": "internal"} for i in range(5)]
    item = crawl_item(_page(links=links, links_total=900), max_length=50)
    assert item["links"] == links
    assert item["linksTotal"] == 900
    assert item["linksTruncated"] is True
    assert item["markdown"] == "x" * 50


def test_links_cut_at_max_links() -> None:
    links = [{"url": f"https://e.com/{i}", "kind": "internal"} for i in range(5)]
    item = crawl_item(_page(links=links), max_length=50, max_links=2)
    assert item["links"] == links[:2]
    assert item["linksTotal"] == 5
    assert item["linksTruncated"] is True


def test_an_uncut_page_is_not_truncated() -> None:
    item = crawl_item(_page(links=[], contacts=None), max_length=50)
    assert item["linksTotal"] == 0
    assert item["linksTruncated"] is False
    assert item["contacts"] is None
    assert item["contactsTotal"] is None
