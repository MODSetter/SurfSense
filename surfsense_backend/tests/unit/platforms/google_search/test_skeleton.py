"""Offline checks for the Google Search results scraper.

Covers the pure parts (no network): queries classification, search-operator
folding, URL building, Apify-spec schema defaults/serialization, and parsing a
rendered SERP into result blocks (against a compact synthetic fixture). The
live fetch / AI Mode flows are exercised by the e2e script, not here.
"""

from datetime import UTC, datetime

from app.proprietary.platforms.google_search import (
    GoogleSearchScrapeInput,
    SerpItem,
)
from app.proprietary.platforms.google_search.parsers import parse_serp
from app.proprietary.platforms.google_search.query_builder import (
    augment_query,
    build_search_url,
    parse_queries,
    resolve_date,
    term_from_url,
)


def test_parse_queries_classifies_terms_and_urls():
    entries = parse_queries(
        "best SEO tools\n"
        "\n"  # blank lines are skipped
        "  https://www.google.com/search?q=apify+web+scraping  \n"
        "javascript OR python site:stackoverflow.com\n"
        "https://example.com/search?q=not-google\n"
    )
    assert [(e.kind, e.value) for e in entries] == [
        ("term", "best SEO tools"),
        ("url", "https://www.google.com/search?q=apify+web+scraping"),
        ("term", "javascript OR python site:stackoverflow.com"),
        # non-Google URLs are treated as literal search terms, not scrape URLs
        ("term", "https://example.com/search?q=not-google"),
    ]


def test_term_from_url():
    assert term_from_url("https://www.google.com/search?q=apify+scraping") == (
        "apify scraping"
    )
    assert term_from_url("https://www.google.com/search") is None


def test_augment_query_folds_all_filters():
    inp = GoogleSearchScrapeInput(
        queries="x",
        forceExactMatch=True,
        site="allrecipes.com",
        relatedToSite="ignored.com",  # site: wins
        wordsInTitle=["easy apple", "pie"],
        wordsInText=["cinnamon"],
        wordsInUrl=["recipe"],
        fileTypes=["pdf", "doc"],
        beforeDate="2024-12-31",
        afterDate="2024-01-01",
    )
    assert augment_query("apple pie", inp) == (
        '"apple pie" site:allrecipes.com intitle:"easy apple" intitle:pie '
        "intext:cinnamon inurl:recipe filetype:pdf OR filetype:doc "
        "before:2024-12-31 after:2024-01-01"
    )


def test_augment_query_related_used_when_no_site():
    inp = GoogleSearchScrapeInput(queries="x", relatedToSite="example.com")
    assert augment_query("q", inp) == "q related:example.com"


def test_resolve_date_absolute_and_relative():
    assert resolve_date("2024-05-03") == "2024-05-03"
    now = datetime(2026, 7, 3, tzinfo=UTC)
    assert resolve_date("8 days", now=now) == "2026-06-25"
    assert resolve_date("3 months", now=now) == "2026-04-04"
    assert resolve_date("1 year", now=now) == "2025-07-03"
    assert resolve_date("someday") is None


def test_build_search_url_localization_and_paging():
    inp = GoogleSearchScrapeInput(
        queries="x",
        countryCode="ES",
        searchLanguage="de",
        languageCode="en",
        locationUule="w+CAIQICIhVW5pdGVkIFN0YXRlcyx1c2E=",
        quickDateRange="m6",
        includeUnfilteredResults=True,
    )
    url = build_search_url("hotels in Seattle", inp, page=2)
    assert url.startswith("https://www.google.com/search?q=hotels+in+Seattle")
    assert "start=10" in url
    assert "gl=es" in url
    assert "lr=lang_de" in url
    assert "hl=en" in url
    assert "uule=w%2BCAIQICIhVW5pdGVkIFN0YXRlcyx1c2E%3D" in url
    assert "tbs=qdr%3Am6" in url
    assert "filter=0" in url

    plain = build_search_url("q", GoogleSearchScrapeInput(queries="x"))
    assert "start=" not in plain  # page 1 carries no offset


def test_scrape_input_defaults_match_apify_spec():
    inp = GoogleSearchScrapeInput(queries="best SEO tools")
    assert inp.maxPagesPerQuery is None  # unset = 1 page
    assert inp.aiOverview.scrapeFullAiOverview is False
    assert inp.aiModeSearch.enableAiMode is False
    assert inp.focusOnPaidAds is False
    assert inp.forceExactMatch is False
    assert inp.mobileResults is False
    assert inp.saveHtml is False
    assert inp.saveHtmlToKeyValueStore is True  # actor default is ON
    assert inp.includeIcons is False
    # Excluded other-actor add-ons are still accepted (extra="allow") so a
    # verbatim Apify payload validates; they are ignored, not modeled.
    GoogleSearchScrapeInput(
        queries="q",
        perplexitySearch={"enablePerplexity": True},
        chatGptSearch={"enableChatGpt": True},
        maximumLeadsEnrichmentRecords=5,
    )


def test_output_item_serializes_full_shape():
    item = SerpItem(resultsTotal=42).to_output()
    assert item["resultsTotal"] == 42
    assert item["organicResults"] == []
    assert item["paidResults"] == []
    assert item["relatedQueries"] == []
    assert item["peopleAlsoAsk"] == []
    assert item["aiModeResult"] is None  # unsourced fields still emitted
    assert item["searchQuery"]["device"] == "DESKTOP"
    assert item["searchQuery"]["type"] == "SEARCH"


# Compact stand-in for a rendered SERP: the selectors parse_serp relies on,
# without the ~1 MB of a live capture. If Google's layout drifts, the fix is in
# parsers.py's selector constants; this fixture pins the expected extraction.
_SERP_FIXTURE = """
<html><body>
  <div id="result-stats">About 1,230 results (0.42 seconds)</div>
  <div id="rso">
    <div class="card">
      <div class="tF2Cxc">
        <img class="XNo5Ab" src="data:image/png;base64,iVBORfake">
        <a href="https://example.com/guide">
          <h3>The Example Guide</h3>
          <cite>https://example.com<span> > Blog</span></cite>
          <span class="VuuXrf">Example</span>
        </a>
        <div class="VwiC3b"><span class="YrbPuc">Jul 2, 2025 &middot; </span>Learn <em>apple pie</em> the easy way.</div>
      </div>
      <table><tbody><tr>
        <td class="cIkxbf">
          <h3><a href="https://example.com/recipes">Recipes</a></h3>
          <div class="zz3gNc">All our recipes ...</div>
        </td>
        <td class="cIkxbf">
          <h3><a href="https://example.com/about">About</a></h3>
        </td>
      </tr></tbody></table>
    </div>
    <div class="tF2Cxc">
      <a href="https://second.example/post"><h3>Second Result</h3>
        <cite>second.example</cite></a>
      <div class="VwiC3b">No date here, just a snippet.</div>
    </div>
  </div>
  <div id="tads">
    <div data-text-ad="1" data-ta-slot-pos="1">
      <a class="sVXRqc" href="https://shop.example/lp">
        <div role="heading" class="Va3FIb"><span>Buy Apple Pie Online</span></div>
      </a>
      <span class="x2VHCd">https://shop.example</span>
      <div class="Va3FIb">Fresh pies delivered daily. Order now and save 20%.</div>
    </div>
  </div>
  <div class="pla-unit" data-dtld="pieshop.example">
    <a class="pla-unit-single-clickable-target" href="https://pieshop.example/p/123"></a>
    <div class="bXPcId">Homemade Apple Pie 9-inch</div>
    <div class="CsnLnf">Pie Shop</div>
    <span class="VbBaOe">$24.99</span>
    <span class="tWaJ3e">$30</span>
  </div>
  <div class="related-question-pair" data-q="What is apple pie?">
    <span class="hgKElc">A pie with an apple filling.</span>
    <a href="https://pies.example/apple#:~:text=A%20pie"><h3>Apple pie - Pies</h3></a>
  </div>
  <div class="related-question-pair" data-q="How to bake?">
    <div class="n6owBd">Preheat the oven.<span class="WBgIic">Wiki +2</span></div>
    <div class="n6owBd">Bake until golden.</div>
  </div>
  <div class="related-question-pair" data-q="Why bake?"></div>
  <div id="m-x-content">
    <div class="n6owBd">Apple pie is a classic dessert.<span class="WBgIic">Wiki +3</span></div>
    <ul><li class="Z1qcYe">Best served warm.</li></ul>
    <ul>
      <li class="h7wxwc">
        <a class="NDNGvf" aria-label="Pie History - Pies.example. Opens in new tab."
           href="https://pies.example/history"></a>
        <span class="vhJ6Pe">A short history of pie.</span>
        <img data-src="https://thumbs.example/pie.jpg" src="data:image/gif;base64,x">
      </li>
      <li class="h7wxwc">
        <a class="NDNGvf" aria-label="Pie History - Pies.example. Opens in new tab."
           href="https://pies.example/history"></a>
      </li>
    </ul>
  </div>
  <div id="botstuff">
    <a class="ngTNl" href="/search?q=easy+apple+pie">easy apple pie</a>
    <a class="ngTNl" href="/search?q=apple+pie+recipe">apple pie recipe</a>
    <a class="fl" href="/search?q=x&start=10">2</a>
  </div>
</body></html>
"""


def test_parse_serp_extracts_all_blocks():
    item = parse_serp(_SERP_FIXTURE)

    assert item.resultsTotal == 1230

    assert len(item.organicResults) == 2
    first = item.organicResults[0]
    assert first.position == 1
    assert first.title == "The Example Guide"
    assert first.url == "https://example.com/guide"
    assert first.displayedUrl == "https://example.com"
    assert first.date == "Jul 2, 2025"
    assert first.emphasizedKeywords == ["apple pie"]
    # The leading date is stripped from the snippet.
    assert first.description == "Learn apple pie the easy way."
    # Sitelinks come from the sibling table inside this result's card.
    assert [(s.title, s.url) for s in first.siteLinks] == [
        ("Recipes", "https://example.com/recipes"),
        ("About", "https://example.com/about"),
    ]
    assert first.siteLinks[0].description == "All our recipes ..."
    assert first.siteLinks[1].description is None

    second = item.organicResults[1]
    assert second.date is None
    assert second.displayedUrl is None  # cite without an http head
    assert second.siteLinks == []  # no card of its own

    # Icons are opt-in: absent by default, the inlined data URI when asked.
    assert first.icon is None
    with_icons = parse_serp(_SERP_FIXTURE, include_icons=True)
    assert with_icons.organicResults[0].icon == "data:image/png;base64,iVBORfake"
    assert with_icons.organicResults[1].icon is None  # block carries no favicon

    # Text ad: heading is the title, the anchor is the clean landing URL, and
    # the non-heading .Va3FIb is the description (not the title echo).
    assert len(item.paidResults) == 1
    ad = item.paidResults[0]
    assert ad.title == "Buy Apple Pie Online"
    assert ad.url == "https://shop.example/lp"
    assert ad.displayedUrl == "https://shop.example"
    assert ad.description == "Fresh pies delivered daily. Order now and save 20%."
    assert ad.adPosition == 1

    # Product ad: title, merchant, domain, and both prices.
    assert len(item.paidProducts) == 1
    prod = item.paidProducts[0]
    assert prod.title == "Homemade Apple Pie 9-inch"
    assert prod.url == "https://pieshop.example/p/123"
    assert prod.displayedUrl == "pieshop.example"
    assert prod.description == "Pie Shop"
    assert prod.prices == ["$24.99", "$30"]

    # Related searches exclude the numeric pagination anchor (a.fl).
    assert [r.title for r in item.relatedQueries] == [
        "easy apple pie",
        "apple pie recipe",
    ]
    assert (
        item.relatedQueries[0].url == "https://www.google.com/search?q=easy+apple+pie"
    )

    # suggestedResults are the related queries re-shaped with type/position.
    assert [(s.position, s.title, s.type) for s in item.suggestedResults] == [
        (1, "easy apple pie", "organic"),
        (2, "apple pie recipe", "organic"),
    ]
    assert item.suggestedResults[0].url == item.relatedQueries[0].url

    assert [p.question for p in item.peopleAlsoAsk] == [
        "What is apple pie?",
        "How to bake?",
        "Why bake?",
    ]
    # Snippet-style answer: text + single source link (highlight fragment cut).
    snippet = item.peopleAlsoAsk[0]
    assert snippet.answer == "A pie with an apple filling."
    assert snippet.url == "https://pies.example/apple"
    assert snippet.title == "Apple pie - Pies"
    # AI-style answer: paragraphs joined, inline source chips stripped.
    ai = item.peopleAlsoAsk[1]
    assert ai.answer == "Preheat the oven. Bake until golden."
    assert ai.url is None and ai.title is None
    # Collapsed (never-expanded) question stays question-only.
    assert item.peopleAlsoAsk[2].answer is None

    # AI Overview: prose (chips stripped) + bullet, sources deduped by URL.
    aio = item.aiOverview
    assert aio is not None
    assert aio.content == "Apple pie is a classic dessert. Best served warm."
    assert len(aio.sources) == 1
    src = aio.sources[0]
    assert src.title == "Pie History - Pies.example"
    assert src.url == "https://pies.example/history"
    assert src.description == "A short history of pie."
    assert src.imageUrl == "https://thumbs.example/pie.jpg"


def test_parse_serp_empty_page_is_safe():
    item = parse_serp("<html><body>nothing here</body></html>")
    assert item.resultsTotal is None
    assert item.organicResults == []
    assert item.paidResults == []
    assert item.paidProducts == []
    assert item.relatedQueries == []
    assert item.peopleAlsoAsk == []
    assert item.aiOverview is None


def test_ai_overview_inside_paa_pair_is_not_page_overview():
    # An expanded PAA question embeds the same widget; it must stay the pair's
    # answer, not leak into the page-level aiOverview.
    html = """
    <html><body>
      <div class="related-question-pair" data-q="What is pie?">
        <div id="m-x-content"><div class="n6owBd">Pie is dessert.</div></div>
      </div>
    </body></html>
    """
    item = parse_serp(html)
    assert item.aiOverview is None
    assert item.peopleAlsoAsk[0].answer == "Pie is dessert."


# Mobile lightweight layout (phone UA render): Gx5Zad blocks, /url? redirect
# anchors, pre-loaded PAA accordions, clamped AI Overview. Mirrors a Jul 2026
# live capture, compacted.
_MOBILE_FIXTURE = """
<html><body><div id="main">
  <div class="Gx5Zad">
    <div class="ilUpNd"><span class="vA9HTb">AI Overview</span></div>
    <div class="frRrnc"><span>Pie is a baked dish.</span></div>
    <div class="Z99dvb">
      <div class="duf-h"><div class="A104Bf BMhZCf">Show more</div>
      <div class="A104Bf hf22jd">Show less</div></div>
      <div id="t1">Best served warm.
        <a href="/url?q=https://pies.example/history&amp;sa=U">
          <div class="UFvD1">Pie History</div></a>
        <a href="https://support.google.com/websearch?p=ai_overviews">Learn more</a>
      </div>
    </div>
  </div>
  <div class="Gx5Zad">
    <a href="/url?q=https://pies.example/apple&amp;sa=U">
      <h3><div class="UFvD1">Apple Pie Recipe</div></h3>
      <div class="AKfAgb">pies.example &rsaquo; apple</div>
    </a>
    <div class="H66NU"><span class="UK5aid">Jun 14, 2026</span><span> · </span>
      The best apple pie recipe.</div>
  </div>
  <div class="Gx5Zad">
    <div class="ilUpNd"><span class="vA9HTb">People also ask</span></div>
    <div class="Z99dvb">
      <div class="duf-h"><div class="bN5znb">What is pie?</div></div>
      <div id="t2"><div class="hgMFsd">A pie is a baked dish.</div>
        <a href="/url?q=https://pies.example/what&amp;sa=U">
          <div class="UFvD1">What is pie - Pies</div></a>
      </div>
    </div>
  </div>
  <div class="Gx5Zad">
    <div class="ilUpNd">People also search for</div>
    <a class="HA0EX" href="/search?q=easy+pie"><div>easy pie</div></a>
  </div>
</div></body></html>
"""


def test_parse_serp_mobile_layout():
    item = parse_serp(_MOBILE_FIXTURE)

    assert len(item.organicResults) == 1
    org = item.organicResults[0]
    assert org.title == "Apple Pie Recipe"
    assert org.url == "https://pies.example/apple"  # redirect unwrapped
    assert org.displayedUrl == "pies.example › apple"  # noqa: RUF001 - Google's breadcrumb char
    assert org.date == "Jun 14, 2026"
    assert org.description == "The best apple pie recipe."
    assert org.position == 1

    assert [r.title for r in item.relatedQueries] == ["easy pie"]
    assert item.relatedQueries[0].url.startswith("https://www.google.com/search")
    assert item.suggestedResults[0].title == "easy pie"

    paa = item.peopleAlsoAsk[0]
    assert paa.question == "What is pie?"
    assert paa.answer == "A pie is a baked dish."
    assert paa.url == "https://pies.example/what"
    assert paa.title == "What is pie - Pies"

    aio = item.aiOverview
    assert aio is not None
    # Prose + expansion joined, Show more/less chrome stripped.
    assert aio.content == "Pie is a baked dish. Best served warm. Pie History"
    assert [s.url for s in aio.sources] == ["https://pies.example/history"]
    assert aio.sources[0].title == "Pie History"


# Google AI Mode page (udm=50): the conversational answer streams into the
# [data-subtree='aimc'] container, built from the same blocks as the AI
# Overview (n6owBd paragraphs, Z1qcYe bullets, h7wxwc sources).
_AI_MODE_FIXTURE = """
<html><body><div id="search">
  <div data-subtree="aimc">
    <div class="n6owBd">Quantum computing uses qubits.<span class="WBgIic">IBM +2</span></div>
    <ul><li class="Z1qcYe">Superposition: both at once.</li></ul>
    <ul>
      <li class="h7wxwc">
        <a class="NDNGvf" aria-label="What Is Quantum Computing? | IBM. Opens in new tab."
           href="https://www.ibm.com/think/topics/quantum-computing"></a>
        <span class="vhJ6Pe">Quantum computing, defined.</span>
      </li>
    </ul>
  </div>
</div></body></html>
"""


def test_parse_ai_mode():
    from app.proprietary.platforms.google_search.parsers import parse_ai_mode

    result = parse_ai_mode(
        _AI_MODE_FIXTURE, query="what is quantum computing", url="https://g/x"
    )
    assert result is not None
    assert result.engine == "AI Mode" and result.provider == "Google"
    assert result.query == "what is quantum computing"
    assert result.url == "https://g/x"
    # Prose + bullets joined, source chips stripped.
    assert result.text == "Quantum computing uses qubits. Superposition: both at once."
    assert len(result.sources) == 1
    src = result.sources[0]
    assert src.title == "What Is Quantum Computing? | IBM"
    assert src.url == "https://www.ibm.com/think/topics/quantum-computing"
    assert src.description == "Quantum computing, defined."

    # A page without the answer container (e.g. generation failed) is None.
    assert parse_ai_mode("<html><body></body></html>", query="q", url="u") is None


async def test_ai_mode_flow_emits_item(monkeypatch):
    from app.proprietary.platforms.google_search import scraper

    async def fake_fetch(url, *, mobile=False):
        # SERP flow gets a plain SERP; the AI Mode flow's udm=50 URL gets
        # the AI Mode page.
        return _AI_MODE_FIXTURE if "udm=50" in url else _NO_ADS_FIXTURE

    monkeypatch.setattr(scraper, "fetch_serp_html", fake_fetch)

    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(
            queries="what is quantum computing",
            aiModeSearch={"enableAiMode": True},
        )
    )
    assert len(items) == 2  # SERP item + AI Mode item
    ai_item = items[1]
    assert ai_item["aiModeResult"]["text"].startswith("Quantum computing")
    assert ai_item["aiModeResult"]["query"] == "what is quantum computing"
    assert "udm=50" in ai_item["searchQuery"]["url"]
    assert ai_item["organicResults"] == []


# An organic-only page (no ad blocks) for the focusOnPaidAds retry test.
_NO_ADS_FIXTURE = """
<html><body><div id="rso">
  <div class="tF2Cxc"><a href="https://x.example/a"><h3>Only Organic</h3></a></div>
</div></body></html>
"""


async def test_focus_on_paid_ads_retries_until_ads(monkeypatch):
    from app.proprietary.platforms.google_search import scraper

    # First two renders have no ads, the third does; focusOnPaidAds should keep
    # re-rendering and return the ad-bearing page.
    pages = iter([_NO_ADS_FIXTURE, _NO_ADS_FIXTURE, _SERP_FIXTURE])
    calls = 0

    async def fake_fetch(_url, *, mobile=False):
        nonlocal calls
        calls += 1
        return next(pages)

    monkeypatch.setattr(scraper, "fetch_serp_html", fake_fetch)

    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="car insurance", focusOnPaidAds=True), limit=1
    )
    assert calls == 3  # retried past the two ad-less renders
    assert items[0]["paidResults"], "should return the ad-bearing SERP"


async def test_no_focus_takes_first_render(monkeypatch):
    from app.proprietary.platforms.google_search import scraper

    calls = 0

    async def fake_fetch(_url, *, mobile=False):
        nonlocal calls
        calls += 1
        return _NO_ADS_FIXTURE

    monkeypatch.setattr(scraper, "fetch_serp_html", fake_fetch)

    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="anything"), limit=1
    )
    assert calls == 1  # no retry without focusOnPaidAds
    assert items[0]["paidResults"] == []
    assert items[0]["organicResults"]
