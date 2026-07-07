"""Parse a rendered Google Search results page into Apify-shaped models.

Two layouts are handled: the desktop layout below, and the **mobile
lightweight layout** Google serves to phone UAs (``mobileResults``), which
uses a completely different DOM — see the ``_mobile_*`` extractors and the
dispatch in :func:`parse_serp`.

Selectors are the current desktop layout's (verified live, Jul 2026):

* organic result container ...... ``div.tF2Cxc``
* title ......................... ``h3``
* link .......................... first ``<a href>`` in the block
* displayed (green) URL ......... ``cite`` (first line, when it's a URL)
* source/site name .............. ``.VuuXrf``
* description ................... ``.VwiC3b``
* inline date ................... ``span.YrbPuc``/``.LEwnzc``
* emphasized keywords ........... ``em``
* sitelinks (expanded) .......... ``td.cIkxbf`` cells in the result's card
* related searches .............. ``a.ngTNl`` (bottom block)
* people-also-ask ............... ``div.related-question-pair[data-q]``
* PAA snippet answer ............ ``.hgKElc`` (+ source ``a`` with ``h3``)
* PAA AI answer ................. ``.n6owBd`` paragraphs (source chips
  ``span.WBgIic`` stripped)
* AI Overview ................... ``#m-x-content`` widget; prose ``.n6owBd``
  + ``li.Z1qcYe``, sources ``li.h7wxwc``
* result count .................. ``#result-stats``

``ponytail:`` these class names are Google's obfuscated build hashes and will
drift; each extractor degrades to ``None``/``[]`` rather than raising, so a
layout change loses a field, never the whole page. When a selector goes stale
the fix is to re-capture a live SERP and update the constant here.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from scrapling.parser import Adaptor

from .schemas import (
    AiModeResult,
    AiOverviewResult,
    AiSource,
    OrganicResult,
    PaidProduct,
    PaidResult,
    PeopleAlsoAskItem,
    RelatedQuery,
    SerpItem,
    SiteLink,
    SuggestedResult,
)

_GOOGLE = "https://www.google.com"
_RESULT_COUNT_RE = re.compile(r"[\d,]+")
# Leading inline date Google prepends to a snippet, e.g. "Jul 2, 2025 · rest…".
_DATE_PREFIX_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s*[·\u00b7]?\s*")
_PRICE_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")


def _one(node, selector: str):
    """First element matching ``selector`` under ``node``, or ``None``.

    Scrapling's ``Adaptor``/``Selector`` expose ``css`` (list) but no
    ``css_first``, so this is the shared "first match" accessor.
    """
    found = node.css(selector)
    return found[0] if found else None


def _text(node) -> str | None:
    """First non-empty text of a node, collapsed to single spaces."""
    if node is None:
        return None
    raw = node.get_all_text(strip=True)
    if not raw:
        return None
    return re.sub(r"\s+", " ", raw)


def _abs_url(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("/"):
        return _GOOGLE + href
    return href


def parse_results_total(doc: Adaptor) -> int | None:
    """The integer from ``#result-stats`` ("About 123 results" -> 123).

    The timing suffix "(0.53 seconds)" is cut so its digits never match. Some
    SERPs (brand queries) render a visible "About 0 results" node while the
    real count sits in a second, hidden ``#result-stats`` — so scan all nodes
    and prefer the first non-zero count.
    """
    totals: list[int] = []
    for node in doc.css("#result-stats"):
        stats = _text(node)
        match = _RESULT_COUNT_RE.search(stats.split("(", 1)[0]) if stats else None
        if match:
            totals.append(int(match.group().replace(",", "")))
    if not totals:
        return None
    return next((t for t in totals if t), totals[0])


def _first_link(block) -> str | None:
    for a in block.css("a"):
        href = a.attrib.get("href")
        if href and href.startswith("http"):
            return href
    return None


def _displayed_url(block) -> str | None:
    cite = _one(block, "cite")
    if cite is None:
        return None
    # cite is breadcrumb text ("https://site.com > Blog"); keep the URL head.
    head = cite.get_all_text(strip=True).split("\n", 1)[0].strip()
    return head if head.startswith("http") else None


def _inline_date(block) -> str | None:
    node = _one(block, "span.YrbPuc") or _one(block, ".LEwnzc span")
    date = _text(node)
    # The date span carries a trailing separator ("Jul 2, 2025 · "); drop it.
    return re.sub(r"\s*[·\u00b7\-]\s*$", "", date).strip() or None if date else None


def _description(block, date: str | None) -> str | None:
    desc = _text(_one(block, ".VwiC3b"))
    if not desc:
        return None
    # Google prepends the date to the snippet; drop it so description is clean.
    if date and desc.startswith(date):
        desc = desc[len(date) :]
    desc = _DATE_PREFIX_RE.sub("", desc)
    # Strip a separator left behind between the date and the snippet body.
    desc = re.sub(r"^\s*[·\u00b7\-]\s*", "", desc)
    return desc.strip() or None


def _site_links(block) -> list[SiteLink]:
    """Expanded sitelinks of one organic result (brand queries' top result).

    The sitelinks table is a *sibling* of the ``tF2Cxc`` block inside the
    result's card, so we climb to the widest ancestor that still contains only
    this one result and read its ``td.cIkxbf`` cells (title ``h3``/link/
    ``.zz3gNc`` description). ``ponytail:`` only the expanded table variant is
    handled; the compact inline-links variant (rare, class-drifty) parses as
    no sitelinks rather than wrong ones.
    """
    card = None
    ancestor = block.parent
    for _ in range(4):
        if ancestor is None or len(ancestor.css("div.tF2Cxc")) != 1:
            break
        card = ancestor
        ancestor = ancestor.parent
    if card is None:
        return []
    links: list[SiteLink] = []
    for cell in card.css("td.cIkxbf"):
        title = _text(_one(cell, "h3"))
        url = _first_link(cell)
        if title and url:
            links.append(
                SiteLink(title=title, url=url, description=_text(_one(cell, ".zz3gNc")))
            )
    return links


def _icon(block) -> str | None:
    """Favicon of a result block, as the base64 data URI the render inlines.

    The rendered desktop SERP swaps every favicon ``img.XNo5Ab`` src to a
    ``data:image/...;base64,`` URI, which is exactly the shape the actor
    emits for ``includeIcons``; non-data srcs (unloaded lazy images) are
    skipped rather than fetched.
    """
    for img in block.css("img.XNo5Ab"):
        src = img.attrib.get("src") or ""
        if src.startswith("data:image"):
            return src
    return None


def parse_organic(doc: Adaptor, *, include_icons: bool = False) -> list[OrganicResult]:
    """Every ``div.tF2Cxc`` organic block, in page order (1-based positions)."""
    results: list[OrganicResult] = []
    for i, block in enumerate(doc.css("div.tF2Cxc"), start=1):
        title = _text(_one(block, "h3"))
        url = _first_link(block)
        if not title or not url:
            continue
        date = _inline_date(block)
        emphasized = []
        for em in block.css("em::text"):
            word = str(em).strip()
            if word and word not in emphasized:
                emphasized.append(word)
        results.append(
            OrganicResult(
                title=title,
                url=url,
                displayedUrl=_displayed_url(block),
                description=_description(block, date),
                date=date,
                emphasizedKeywords=emphasized,
                siteLinks=_site_links(block),
                icon=_icon(block) if include_icons else None,
                position=i,
            )
        )
    return results


def parse_paid_results(
    doc: Adaptor, *, include_icons: bool = False
) -> list[PaidResult]:
    """Text ads (``div[data-text-ad]``), covering the top and bottom ad blocks.

    Fields mirror an organic result: the heading is the title, the ad's anchor
    is the (clean) landing URL, ``.x2VHCd`` is the green displayed URL, and the
    non-heading ``.Va3FIb`` block is the description. ``adPosition`` comes from
    Google's own ``data-ta-slot-pos``.
    """
    ads: list[PaidResult] = []
    for block in doc.css("div[data-text-ad]"):
        heading = _one(block, "div[role='heading']")
        title = _text(heading)
        anchor = _one(block, "a.sVXRqc") or _one(block, "a[href^='http']")
        url = anchor.attrib.get("href") if anchor is not None else None
        if not title or not url:
            continue
        # The description shares the .Va3FIb class with the heading; pick the
        # longest .Va3FIb whose text isn't the title itself.
        description = None
        for cand in block.css(".Va3FIb"):
            text = _text(cand)
            if (
                text
                and text != title
                and (description is None or len(text) > len(description))
            ):
                description = text
        slot = block.attrib.get("data-ta-slot-pos")
        ads.append(
            PaidResult(
                title=title,
                url=url,
                displayedUrl=_text(_one(block, ".x2VHCd")),
                description=description,
                icon=_icon(block) if include_icons else None,
                adPosition=int(slot) if slot and slot.isdigit() else None,
            )
        )
    return ads


def parse_paid_products(doc: Adaptor) -> list[PaidProduct]:
    """Shopping / product ads (``div.pla-unit``).

    Title is the product name (``.bXPcId``); the merchant domain is the
    ``data-dtld`` attribute; the clickable card's anchor is the destination;
    prices are the current (``.VbBaOe``) and struck-through original
    (``.tWaJ3e``) amounts, with a ``$`` regex fallback.
    """
    products: list[PaidProduct] = []
    for pla in doc.css("div.pla-unit"):
        title = _text(_one(pla, ".bXPcId"))
        anchor = _one(pla, "a.pla-unit-single-clickable-target")
        url = anchor.attrib.get("href") if anchor is not None else None
        if not title or not url:
            continue
        prices: list[str] = []
        for sel in (".VbBaOe", ".tWaJ3e"):
            price = _text(_one(pla, sel))
            if price and price not in prices:
                prices.append(price)
        if not prices:
            prices = _PRICE_RE.findall(_text(pla) or "")
        products.append(
            PaidProduct(
                title=title,
                url=url,
                displayedUrl=pla.attrib.get("data-dtld"),
                description=_text(_one(pla, ".CsnLnf")),
                prices=prices,
            )
        )
    return products


def parse_related_queries(doc: Adaptor) -> list[RelatedQuery]:
    """Bottom "related searches" block (``a.ngTNl``)."""
    out: list[RelatedQuery] = []
    for a in doc.css("a.ngTNl"):
        title = _text(a)
        href = _abs_url(a.attrib.get("href"))
        if title and href:
            out.append(RelatedQuery(title=title, url=href))
    return out


def _ai_generated_text(root) -> str | None:
    """Prose of an AI-generated block: paragraphs + bullets, in page order.

    Both the SERP AI Overview and PAA AI answers are built from ``.n6owBd``
    paragraphs and ``li.Z1qcYe`` bullets, with inline source chips —
    ``span.WBgIic`` "YouTube +2" pills — mixed into the text; the chips are
    stripped out. Google renders some blocks twice (collapsed + expanded), so
    repeated fragments are dropped.
    """
    parts: list[str] = []
    for block in root.css(".n6owBd, li.Z1qcYe"):
        text = _text(block)
        if not text:
            continue
        for chip in block.css("span.WBgIic"):
            chip_text = _text(chip)
            if chip_text:
                text = text.replace(chip_text, " ")
        text = re.sub(r"\s+", " ", text).strip()
        if text and text not in parts:
            parts.append(text)
    return " ".join(parts) or None


def _paa_answer(pair) -> str | None:
    """Answer text of an *expanded* PAA pair, or ``None`` if not loaded.

    Two shapes exist: a classic featured-snippet answer (``.hgKElc``) and an
    AI-generated one (see :func:`_ai_generated_text`).
    """
    snippet = _text(_one(pair, ".hgKElc"))
    if snippet:
        return snippet
    return _ai_generated_text(pair)


def _paa_source(pair) -> tuple[str | None, str | None]:
    """(url, title) of a snippet answer's source link; (None, None) otherwise.

    Snippet answers cite one page via an anchor wrapping an ``h3``; AI answers
    cite many pages inline and carry no single source, matching the actor's
    null url/title there. Google's ``#:~:text=`` highlight fragment is an
    artifact of the expansion click, not part of the source URL.
    """
    for a in pair.css("a[href^='http']"):
        href = a.attrib.get("href") or ""
        title = _text(_one(a, "h3"))
        if href and title and "google.com" not in href:
            return href.split("#:~:", 1)[0], title
    return None, None


def parse_ai_overview(doc: Adaptor) -> AiOverviewResult | None:
    """The inline AI Overview widget (``#m-x-content``), or ``None``.

    ``content`` is the generated prose (paragraphs + bullets, source chips
    stripped); ``sources`` come from :func:`_ai_sources`. A widget that only
    says "not available" parses to ``None``.
    """
    box = _one(doc, "#m-x-content")
    if box is None:
        return None
    # Expanded PAA questions embed the same widget; that's the pair's answer,
    # not the page's AI Overview.
    ancestor = box.parent
    while ancestor is not None:
        if "related-question-pair" in (ancestor.attrib.get("class") or ""):
            return None
        ancestor = ancestor.parent
    content = _ai_generated_text(box)
    if not content:
        return None
    return AiOverviewResult(content=content, sources=_ai_sources(box))


def _ai_sources(root) -> list[AiSource]:
    """Cited sources of an AI answer (AI Overview and AI Mode share the DOM).

    ``li.h7wxwc`` list items: anchor ``a.NDNGvf`` carries the URL and a
    "<title>. Opens in new tab." aria-label; ``.vhJ6Pe`` is the snippet and
    the thumbnail URL sits in the lazy image's ``data-src``. Google renders
    the list twice (collapsed rail + expanded sheet), so dedupe by URL.
    """
    sources: list[AiSource] = []
    seen: set[str] = set()
    for li in root.css("li.h7wxwc"):
        anchor = _one(li, "a.NDNGvf") or _one(li, "a[href^='http']")
        if anchor is None:
            continue
        url = anchor.attrib.get("href")
        if not url or url in seen:
            continue
        seen.add(url)
        title = (anchor.attrib.get("aria-label") or "").removesuffix(
            ". Opens in new tab."
        ).strip() or None
        image = _one(li, "img[data-src]")
        sources.append(
            AiSource(
                title=title,
                url=url,
                description=_text(_one(li, ".vhJ6Pe")),
                imageUrl=image.attrib.get("data-src") if image is not None else None,
            )
        )
    return sources


def parse_ai_mode(html: str, *, query: str, url: str) -> AiModeResult | None:
    """Parse a Google AI Mode page (``/search?udm=50``) into an AiModeResult.

    The conversational answer lives in the ``[data-subtree='aimc']``
    container, built from the same blocks as the AI Overview (``.n6owBd``
    paragraphs + ``li.Z1qcYe`` bullets, sources in ``li.h7wxwc``), so the
    extractors are shared. Returns ``None`` when the answer container is
    missing or empty (answer failed to stream before network-idle).
    """
    doc = Adaptor(html)
    box = _one(doc, "[data-subtree='aimc']")
    if box is None:
        return None
    text = _ai_generated_text(box)
    if not text:
        return None
    return AiModeResult(text=text, sources=_ai_sources(box), query=query, url=url)


def parse_people_also_ask(doc: Adaptor) -> list[PeopleAlsoAskItem]:
    """People-also-ask pairs (``div.related-question-pair[data-q]``).

    The fetch layer clicks the initially-served questions open (see
    ``fetch._expand_paa``), so expanded pairs carry answers here. Expansion
    appends extra collapsed questions; those emit with ``answer=None``.
    """
    out: list[PeopleAlsoAskItem] = []
    seen: set[str] = set()
    for pair in doc.css("div.related-question-pair"):
        question = pair.attrib.get("data-q") or _text(_one(pair, "span"))
        if not question or question in seen:
            continue
        seen.add(question)
        url, title = _paa_source(pair)
        out.append(
            PeopleAlsoAskItem(
                question=question,
                answer=_paa_answer(pair),
                url=url,
                title=title,
                date=_inline_date(pair),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Mobile lightweight layout (phone UAs). Verified live, Jul 2026:
#
# * result/section block ....... ``div.Gx5Zad`` (organic ones contain ``h3``)
# * anchor title ............... ``.UFvD1``
# * displayed breadcrumb ....... ``.AKfAgb``
# * description ................ ``.H66NU`` ("Jun 14, 2026 · snippet…")
# * PAA question ............... ``.bN5znb`` inside the "People also ask"
#   block; answers are pre-rendered in the collapsed accordions (no clicks)
# * related searches ........... ``a.HA0EX[href^='/search']``
# * AI Overview ................ block headed "AI Overview"; full text is
#   pre-rendered behind the Show more clamp
#
# Result links are Google redirects (``/url?q=<target>&sa=…``). There is no
# ``#result-stats`` and no marked ad/sitelink blocks in this layout.
# ---------------------------------------------------------------------------

_MOBILE_AIO_CHROME = (
    "AI Overview",
    "Can't generate an AI overview right now. Try again later.",
    "Show more",
    "Show less",
    "Learn more",
)


def _mobile_target(anchor) -> str | None:
    """Landing URL of a mobile redirect anchor (``/url?q=<target>&…``)."""
    href = anchor.attrib.get("href") or ""
    if href.startswith("/url?"):
        return (parse_qs(urlsplit(href).query).get("q") or [None])[0]
    return href if href.startswith("http") else None


def _mobile_section(doc: Adaptor, header: str):
    """The ``Gx5Zad`` block whose text starts with ``header``, or ``None``."""
    for block in doc.css("div.Gx5Zad"):
        text = _text(block) or ""
        if text.startswith(header):
            return block
    return None


def _mobile_organic(doc: Adaptor) -> list[OrganicResult]:
    """Blocks carrying an ``h3`` title (PAA/AIO embeds carry none).

    ``ponytail:`` emphasizedKeywords and siteLinks aren't distinguishable in
    this layout and emit empty; upgrade path is a fresh capture if the actor's
    mobile output proves richer.
    """
    results: list[OrganicResult] = []
    for block in doc.css("div.Gx5Zad"):
        title = _text(_one(block, "h3"))
        anchor = _one(block, "a[href^='/url?']")
        url = _mobile_target(anchor) if anchor is not None else None
        if not title or not url:
            continue
        raw_desc = _text(_one(block, ".H66NU"))
        date_match = _DATE_PREFIX_RE.match(raw_desc or "")
        date = re.sub(r"[\s·]+$", "", date_match.group()) if date_match else None
        results.append(
            OrganicResult(
                title=title,
                url=url,
                displayedUrl=_text(_one(block, ".AKfAgb")),
                description=_DATE_PREFIX_RE.sub("", raw_desc or "") or None,
                date=date or None,
                position=len(results) + 1,
            )
        )
    return results


def _mobile_related(doc: Adaptor) -> list[RelatedQuery]:
    out: list[RelatedQuery] = []
    for a in doc.css("a.HA0EX[href^='/search']"):
        title = _text(a)
        href = _abs_url(a.attrib.get("href"))
        if title and href:
            out.append(RelatedQuery(title=title, url=href))
    return out


def _mobile_paa(doc: Adaptor) -> list[PeopleAlsoAskItem]:
    """Accordion entries of the "People also ask" block (answers pre-loaded)."""
    section = _mobile_section(doc, "People also ask")
    if section is None:
        return []
    out: list[PeopleAlsoAskItem] = []
    for accordion in section.css(".Z99dvb"):
        question = _text(_one(accordion, ".bN5znb"))
        if not question:
            continue
        answer = _text(_one(accordion, ".hgMFsd"))
        anchor = _one(accordion, "a[href^='/url?']")
        url = _mobile_target(anchor) if anchor is not None else None
        title = _text(_one(anchor, ".UFvD1")) if anchor is not None else None
        out.append(
            PeopleAlsoAskItem(question=question, answer=answer, url=url, title=title)
        )
    return out


def _mobile_ai_overview(doc: Adaptor) -> AiOverviewResult | None:
    """The "AI Overview" block; its full text sits behind a CSS-only clamp.

    The prose is interleaved with widget chrome (header, error stub, the
    Show more/less toggle), so the block text is taken whole and the known
    chrome strings are stripped out.

    ponytail: source-link titles stay inline in ``content`` (they're
    interleaved with the prose in this layout, with no clean container to
    split on); the upgrade path is per-child-div walking of the expansion.
    """
    section = _mobile_section(doc, "AI Overview")
    if section is None:
        return None
    content = _text(section) or ""
    for chrome in _MOBILE_AIO_CHROME:
        content = content.replace(chrome, " ")
    content = re.sub(r"\s+", " ", content).strip()
    if not content:
        return None
    sources: list[AiSource] = []
    seen: set[str] = set()
    for anchor in section.css("a[href^='/url?']"):
        url = _mobile_target(anchor)
        title = _text(_one(anchor, ".UFvD1"))
        # google.com targets are widget chrome ("Learn more"), not citations.
        if url and url not in seen and "google.com" not in url:
            seen.add(url)
            sources.append(AiSource(title=title, url=url))
    return AiOverviewResult(content=content, sources=sources)


def parse_serp(html: str, *, include_icons: bool = False) -> SerpItem:
    """Parse a full rendered SERP page into a :class:`SerpItem`.

    Provenance (``searchQuery``) is stamped by the caller; this fills the
    result blocks. Missing sections yield empty lists, never errors. The
    mobile lightweight layout (no ``#rso``, ``Gx5Zad`` blocks) dispatches to
    the ``_mobile_*`` extractors (which carry no favicon imgs, so
    ``include_icons`` is a desktop-only concern).
    """
    doc = Adaptor(html)
    if _one(doc, "#rso") is None and doc.css("div.Gx5Zad"):
        related = _mobile_related(doc)
        return SerpItem(
            organicResults=_mobile_organic(doc),
            relatedQueries=related,
            peopleAlsoAsk=_mobile_paa(doc),
            aiOverview=_mobile_ai_overview(doc),
            suggestedResults=[
                SuggestedResult(title=r.title, url=r.url, position=i)
                for i, r in enumerate(related, start=1)
            ],
        )
    related = parse_related_queries(doc)
    return SerpItem(
        resultsTotal=parse_results_total(doc),
        organicResults=parse_organic(doc, include_icons=include_icons),
        paidResults=parse_paid_results(doc, include_icons=include_icons),
        paidProducts=parse_paid_products(doc),
        relatedQueries=related,
        peopleAlsoAsk=parse_people_also_ask(doc),
        aiOverview=parse_ai_overview(doc),
        # The actor synthesizes suggestedResults from the related-searches
        # block, re-shaped as typed/positioned result entries.
        suggestedResults=[
            SuggestedResult(title=r.title, url=r.url, position=i)
            for i, r in enumerate(related, start=1)
        ],
    )
