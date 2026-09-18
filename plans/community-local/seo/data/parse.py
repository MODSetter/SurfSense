#!/usr/bin/env python3
"""Render the saved DataForSEO JSON pulls in this directory as markdown tables.

The numbers in ../01-keyword-research.md come from here. Re-run after a fresh
pull to regenerate them, or to check a figure that looks wrong.

    python parse.py keyword-overview-curated.json          # keyword metrics
    python parse.py ranked-anythingllm.json --mode ranked   # competitor rankings
    python parse.py serp-competitors.json --mode competitors
    python parse.py keyword-ideas-*.json --min-volume 50    # several at once
    python parse.py gap-open-notebook.json --mode gap       # they rank, we don't
    python parse.py historical-head-terms.json --mode history
    python parse.py keyword-overview-*.json --mode score --csv ../master-keywords.csv
    python parse.py --compact-from RAW.json --market de-de   # trim a pull into intl/de-de.json
    python parse.py --mode markets --csv intl/master-intl.csv # concept x market pivot

Shapes differ per endpoint: Labs nests metrics under `keyword_data` for
related/ranked keywords but inlines them for overview/ideas, so `pick` walks
both. Self-check: `python parse.py --self-check`.
"""
import argparse
import csv
import datetime
import glob
import json
import math
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).parent

# SERP features worth seeing in a table; the rest are noise for our purposes.
FEATURES = {
    "ai_overview": "AIO",
    "featured_snippet": "snippet",
    "people_also_ask": "PAA",
    "video": "video",
    "discussions_and_forums": "forums",
    "knowledge_graph": "KG",
    "shopping": "shopping",
    "paid": "ads",
}

INTENT_SHORT = {
    "informational": "info",
    "navigational": "nav",
    "commercial": "comm",
    "transactional": "trans",
}


def pick(item):
    """Return (keyword, keyword_info, properties, serp_info, intent) for any shape."""
    data = item.get("keyword_data") or item
    return (
        data.get("keyword") or item.get("keyword"),
        data.get("keyword_info") or {},
        data.get("keyword_properties") or {},
        data.get("serp_info") or {},
        data.get("search_intent_info") or {},
    )


def load(path):
    path = pathlib.Path(path)
    # The pulls are stored gzipped -- 4 MB of pretty-printed JSON compresses to
    # about 300 KB, and a plans folder is the wrong place for the raw bulk.
    if path.suffix == ".gz":
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))  # PowerShell 5 writes a BOM
    # The MCP's AI-optimised subset puts items at the top level; the raw API
    # wraps them in tasks[].result[].
    if "items" in payload:
        return payload["items"] or []
    items = []
    for task in payload.get("tasks") or []:
        for result in task.get("result") or []:
            items.extend(result.get("items") or [])
    return items


def features_of(serp_info):
    types = serp_info.get("serp_item_types") or []
    return " ".join(FEATURES[t] for t in types if t in FEATURES)


def monthly(info):
    """Monthly volumes oldest-first. The MCP subset gives {"2026-07": 880},
    the raw API gives [{"year", "month", "search_volume"}]; accept both."""
    raw = info.get("monthly_searches") or {}
    if isinstance(raw, dict):
        pairs = [(key, value or 0) for key, value in raw.items()]
    else:
        pairs = [(f"{m.get('year')}-{m.get('month', 0):02d}", m.get("search_volume") or 0)
                 for m in raw]
    return [value for _key, value in sorted(pairs)]


def effective_volume(info):
    """(reported, recent, spike). Google Ads' 12-month average is inflated by
    one-off spikes: `local llm`, `private ai` and `sovereign ai` all jumped ~10x
    in the same month (Jul 2026). `recent` is the median of the last three
    months, which damps a single spike month but keeps a sustained ramp.
    `spike` is set when the peak month is more than 4x the 12-month median."""
    reported = info.get("search_volume") or 0
    series = monthly(info)
    if len(series) < 3:
        return reported, reported, False
    recent = int(statistics.median(series[-3:]))
    median12 = statistics.median(series[-12:]) or 1
    return reported, min(reported, recent), max(series[-12:]) > 4 * median12


def rows_metrics(items, min_volume):
    rows = []
    for item in items:
        keyword, info, props, serp, intent = pick(item)
        volume = info.get("search_volume") or 0
        if keyword is None or volume < min_volume:
            continue
        _reported, recent, spike = effective_volume(info)
        rows.append({
            "keyword": keyword,
            "volume": volume,
            "recent": recent if spike else None,
            "kd": props.get("keyword_difficulty"),
            "intent": INTENT_SHORT.get(intent.get("main_intent") or "", ""),
            "cpc": info.get("cpc") or 0,
            "trend": (info.get("search_volume_trend") or {}).get("yearly"),
            "features": features_of(serp),
        })
    # Dedupe by keyword, keeping the highest volume reading.
    best = {}
    for row in rows:
        if row["keyword"] not in best or row["volume"] > best[row["keyword"]]["volume"]:
            best[row["keyword"]] = row
    return sorted(best.values(), key=lambda r: -r["volume"])


def rows_ranked(items, min_volume):
    rows = []
    for item in items:
        keyword, info, props, serp, intent = pick(item)
        volume = info.get("search_volume") or 0
        if keyword is None or volume < min_volume:
            continue
        element = item.get("ranked_serp_element") or {}
        serp_item = element.get("serp_item") or element
        rows.append({
            "keyword": keyword,
            "volume": volume,
            "kd": props.get("keyword_difficulty"),
            "pos": serp_item.get("rank_absolute"),
            "intent": INTENT_SHORT.get(intent.get("main_intent") or "", ""),
            "url": (serp_item.get("relative_url") or serp_item.get("url") or "")[:70],
        })
    return sorted(rows, key=lambda r: -r["volume"])


def rows_urls(items):
    """Group a ranked_keywords pull by landing page. Shows which URLs carry the
    organic footprint -- the thing you lose if you unpublish one."""
    pages = {}
    for item in items:
        keyword, info, _props, _serp, _intent = pick(item)
        element = item.get("ranked_serp_element") or {}
        serp_item = element.get("serp_item") or element
        url = serp_item.get("relative_url") or serp_item.get("url") or "?"
        page = pages.setdefault(url, {"url": url, "keywords": 0, "volume": 0, "etv": 0.0,
                                      "best_pos": None})
        page["keywords"] += 1
        page["volume"] += info.get("search_volume") or 0
        page["etv"] += serp_item.get("etv") or 0.0
        position = serp_item.get("rank_absolute")
        if position and (page["best_pos"] is None or position < page["best_pos"]):
            page["best_pos"] = position
    return sorted(pages.values(), key=lambda p: -p["volume"])


POSITION_BANDS = [("top 3", 1, 3), ("top 10", 1, 10), ("11-20", 11, 20), ("21+", 21, 999)]

# What the /free footprint is actually made of. The no-signup promise is the one
# the desktop app keeps better than the hosted page did; the brand terms are the
# one it cannot keep at all. Sizing them separately is what settled the decision.
BASELINE_CLUSTERS = [
    ("no sign up / no login / no account",
     r"no.?(sign|login|log in|regist)|without (login|regist|sign)|no.?account|"
     r"without (signing|logging)"),
    ("hosted brand terms", r"chat ?gpt|\bgpt\b|claude|gemini"),
    ("no restrictions / unlimited", r"no restriction|no filter|unfiltered|uncensor|unlimited"),
]


def landing_rows(items, prefix):
    """One row per keyword whose landing page starts with `prefix`, from a
    ranked_keywords pull. Positions are absolute, so AI Overviews and PAA boxes
    that push an organic result down are already counted."""
    rows = []
    for item in items:
        keyword, info, _props, _serp, _intent = pick(item)
        element = item.get("ranked_serp_element") or {}
        serp_item = element.get("serp_item") or element
        url = serp_item.get("relative_url") or serp_item.get("url") or ""
        if not url.startswith(prefix):
            continue
        rows.append({"keyword": keyword or "", "volume": info.get("search_volume") or 0,
                     "pos": serp_item.get("rank_absolute") or 999,
                     "etv": serp_item.get("etv") or 0.0})
    return rows


def render_baseline(items, prefix):
    """Why one landing page's headline volume is not what it looks like: split it
    by position band, then by what the query actually asks for. Volume sits where
    nobody clicks; value concentrates in whichever promise the page really makes."""
    rows = landing_rows(items, prefix)
    if not rows:
        return f"_no rows under {prefix}_\n"
    total_v = sum(r["volume"] for r in rows) or 1
    total_e = sum(r["etv"] for r in rows) or 1.0
    top10 = [r for r in rows if r["pos"] <= 10]

    def summarise(label, group):
        return {"band": label, "cluster": label, "keywords": len(group),
                "volume": f"{sum(r['volume'] for r in group):,}",
                "vol %": f"{100 * sum(r['volume'] for r in group) / total_v:.1f}%",
                "etv": f"${sum(r['etv'] for r in group):,.0f}",
                "etv %": f"{100 * sum(r['etv'] for r in group) / total_e:.1f}%",
                "top 10": f"{len([r for r in group if r['pos'] <= 10])} of {len(top10)}"}

    out = [f"### {prefix} — {len(rows)} keywords, {total_v:,} volume, ${total_e:,.0f} etv\n",
           table([summarise(name, [r for r in rows if lo <= r["pos"] <= hi])
                  for name, lo, hi in POSITION_BANDS],
                 ["band", "keywords", "volume", "vol %", "etv", "etv %"]),
           ""]
    clusters, claimed = [], set()
    for name, pattern in BASELINE_CLUSTERS:
        group = [r for r in rows if re.search(pattern, r["keyword"])]
        clusters.append(summarise(name, group))
        if name.startswith("no sign up"):  # the rest is measured against this one
            claimed = {r["keyword"] for r in group}
    clusters.append(summarise("everything else", [r for r in rows if r["keyword"] not in claimed]))
    out.append(table(clusters, ["cluster", "keywords", "volume", "etv", "etv %", "top 10"]))
    out.append("\nClusters overlap: a brand term is usually also a no-signup term.")
    out.append('"everything else" is the complement of the no-signup cluster only.\n')
    out.append("Most valuable rows:")
    for r in sorted(rows, key=lambda r: -r["etv"])[:8]:
        out.append(f"  pos {r['pos']:<4} {r['volume']:>7,}  ${r['etv']:>7.2f}  {r['keyword']}")
    return "\n".join(out)


def rows_competitors(items):
    """serp_competitors items. `intersections` is how many of the seed keywords
    the domain ranks for; the trimmed artifact archive drops the field and keeps
    `keywords_positions`, so count that when it is missing."""
    rows = []
    for item in items:
        positions = item.get("keywords_positions") or {}
        rows.append({
            "domain": item.get("domain"),
            "intersections": item.get("intersections") or len(positions) or None,
            "avg_pos": item.get("avg_position"),
            "median_pos": item.get("median_position"),
            "rank": item.get("rank"),
            "visibility": item.get("visibility"),
            "keywords": ((item.get("metrics") or {}).get("organic") or {}).get("count"),
        })
    return sorted(rows, key=lambda r: (-(r["intersections"] or 0), r["median_pos"] or 0))


def rows_gap(items, min_volume):
    """domain_intersection with intersections=false: keywords target1 ranks
    for and target2 does not. target1's result sits in first_domain_serp_element."""
    rows = []
    for item in items:
        keyword, info, props, _serp, intent = pick(item)
        volume = info.get("search_volume") or 0
        if keyword is None or volume < min_volume:
            continue
        element = item.get("first_domain_serp_element") or {}
        rows.append({
            "keyword": keyword,
            "volume": volume,
            "kd": props.get("keyword_difficulty"),
            "pos": element.get("rank_absolute"),
            "intent": INTENT_SHORT.get(intent.get("main_intent") or "", ""),
            "url": (element.get("relative_url") or element.get("url") or "")[:60],
        })
    return sorted(rows, key=lambda r: -r["volume"])


def rows_history(items):
    """historical_search_volume: one row per keyword, average volume per
    calendar year, plus the peak month so a spike is visible next to the trend."""
    rows = []
    for item in items:
        keyword, info, _p, _s, _i = pick(item)
        raw = info.get("monthly_searches") or []
        by_year = {}
        peak = ("", 0)
        for month in raw:
            year, volume = month.get("year"), month.get("search_volume") or 0
            by_year.setdefault(year, []).append(volume)
            if volume > peak[1]:
                peak = (f"{year}-{month.get('month', 0):02d}", volume)
        row = {"keyword": keyword}
        for year in sorted(by_year):
            row[str(year)] = int(statistics.mean(by_year[year]))
        row["peak"] = f"{peak[1]} ({peak[0]})"
        rows.append(row)
    return rows


# Cluster and page assignment, first match wins. ponytail: regex on the keyword
# text, not semantic clustering; it is a first pass for a human to override in
# the CSV, and it is wrong for maybe one keyword in twenty.
# Keywords that share a word with a cluster but are about something else:
# laptop shopping, podcasts *about* AI, coding agents, image/voice generators.
EXCLUDE = (r"laptop|coding|code |agent|image|video gen|voice|music|generator for|"
           r"^best ai podcasts?$|podcasts? about|^notion ai$|^local ai$|^locally ai$")

CLUSTERS = [
    ("brand", r"surf ?sense", "/ landing"),
    ("mcp", r"\bmcp\b|notebooklm api|have an api", "/mcp-server"),
    ("podcast", r"(notes?|pdfs?|documents?|text|articles?|papers?) (in)?to (an? )?podcast|"
                r"podcast (generator|maker|from)|audio overview|notebooklm podcast|"
                r"ai podcast (generator|from)", "feature: podcast"),
    # The other Studio outputs (formats.py), one cluster per feature page. Named
    # edtech tools first so `quillbot summarizer` sizes the competitor, not the
    # feature; generator/maker/from/to forms only, so `presentation skills`,
    # `learning style quiz` and `study tips` from the ideas pull stay out.
    ("competitor", r"quizlet|knowt|turbolearn|studyfetch|notegpt|mindgrasp|napkin ai|mapify|"
                   r"gamma (ai|alternative)|revisely|youlearn|remnote|quillbot|penseum|quizgecko",
     "compare pages"),
    ("study", r"study guide (maker|generator|creator|from|ai)|ai study (guide|tools?|assistant|buddy|"
              r"companion|app)|ai.?powered study|^study ai$|ai (tools? )?for stud(ying|ents)|"
              r"best ai (tools? )?for stud|study tools? (ai|like)|notebooklm (for|to) study|"
              r"how to use notebooklm (to|for) stud|interactive study guide", "feature: study guide"),
    ("flashcards", r"flash ?cards? (generator|maker|ai|from|for studying)|ai (generated )?flash ?cards?|"
                   r"(pdf|notes?|text) to (flash ?cards?|anki)|(make|turn|convert) .*flash ?cards|"
                   r"notebooklm flash|anki (ai|flashcard|card)|free flash ?card generator", "feature: flashcards"),
    ("quiz", r"quiz (generator|maker|ai|from|creator)|ai quiz|(pdf|notes?|text) to quiz|notebooklm quiz|"
             r"(test|exam|question|mcq|multiple choice|practice test|practice questions?) generator|"
             r"exam generator from", "feature: quiz"),
    ("mindmap", r"mind ?map (ai|generator|maker|from)|ai mind ?map|(pdf|text|notes?|youtube) to mind ?map|"
                r"notebooklm mind ?map|mind ?mapping tool|mind ?map notebooklm", "feature: mind map"),
    ("summary", r"summariz|summary (generator|ai)|ai summary|notebooklm summary|briefing doc",
     "feature: summary"),
    ("slides", r"slides? (generator|maker|ai)|ai slides?\b|slide deck|power ?point (generator|maker|ai)|"
               r"ai power ?point|\bppt (ai|generator|maker)|ai ppt|"
               r"(pdf|word|notes?|text|document) to (ppt|powerpoint|presentation|slides)|"
               r"presentation (generator|maker|ai)|ai presentation|"
               r"notebooklm (slides?|slide deck|presentation|ppt|powerpoint)", "feature: slides"),
    ("infographic", r"infographic (generator|maker|ai)|ai infographic|to infographic|notebooklm infographic",
     "feature: infographic"),
    ("report", r"ai report (generator|writer)|report generator ai|research report generator|"
               r"notebooklm reports?|literature review (ai|generator)|ai (word )?document (generator|writer)",
     "feature: report"),
    ("spreadsheet", r"spreadsheet|\bexcel\b|data table|table extract|pdf table|\bcsv\b|"
                    r"(extract|pull) (a )?(tables?|data) from pdf", "feature: spreadsheet"),
    ("video", r"video overview|(notes?|pdfs?|documents?) (in)?to (an? )?video|explainer video generator|"
              r"lecture video generator|notebooklm (cinematic )?video", "feature: video (WIP)"),
    ("webpage", r"ai html generator|web ?page generator|notebooklm html|interactive report", "feature: web page"),
    ("notebooklm-switch", r"notebooklm (alternative|offline|privacy|self.?hosted|competitor)|"
                          r"(open source|local|offline|private) notebooklm|"
                          r"notebooklm (vs|versus|for (lawyers|business|research))|"
                          r"\b(vs|versus)\.? notebooklm|notebooklm enterprise|"
                          r"(apps?|tools?|software) like notebooklm|"
                          r"is notebooklm (safe|private|secure)|notebooklm (data privacy|security)",
     "/ landing"),
    ("notebooklm-install", r"notebooklm (for )?(download|windows|mac|linux|desktop|app)|"
                           r"(download|install) notebooklm", "/downloads"),
    ("download", r"^(download|install) (an? )?(ai|llm)|^ai download|ai app download", "/downloads"),
    ("notebooklm-pricing", r"notebooklm (pricing|price|plans?|plus|pro|cost|free|limits?|"
                           r"source limit|student discount|subscription)|"
                           r"is notebooklm free|how much (is|does) notebooklm|"
                           r"how many sources .*notebooklm|does notebooklm have a limit",
     "/pricing"),
    ("notebooklm-nav", r"^(google |gemini )?notebook ?lm( ai| google)?$|^notebooklm\.google|"
                       r"notebooklm (login|log in|sign ?in)$", "not ours: brand navigation"),
    ("notebooklm-brand", r"notebook\s?lm", "blog: notebooklm how-to"),
    ("compliance", r"hipaa|gdpr|dsgvo|confidential|sensitive|legal document|compliant|\bsecure ai\b",
     "page: compliance"),
    # Added 17 Sep 2026 with the production-chat pass (../07-what-users-do.md).
    # Professional work outruns study ~1.8:1 among users who state a task, and
    # these terms carry the highest CPCs in the research ($30-67) — but nothing
    # here matched a cluster before, so --drop-other discarded every one of them
    # and the master list could not see the strategy. Sits after `compliance` so
    # HIPAA/GDPR still route to the compliance page, and after the artifact
    # clusters so `ai report generator` stays with `report`.
    ("professional", r"ai for (lawyers?|attorneys?|accountants?|consultants?|auditors?|"
                     r"audit|compliance|professional services|analysts?|"
                     r"project managers?|small business|business|work)\b|"
                     r"^legal ai$|^free legal ai$|ai contract (review|analysis)|"
                     r"contract analysis software|ai (knowledge base|workspace)|"
                     r"business ai assistant|due diligence ai|ai audit tool|"
                     r"ai document (analysis|review|summarizer)|"
                     r"ai (proposal|report) writer|proposal generator|"
                     r"rfp response ai|ai rfp response|sop generator|"
                     r"ai tools for consultants|consulting ai tools|"
                     r"executive summary (generator|ai)|ai executive summary",
     "page: documents into deliverables"),
    ("self-hosted", r"self.?host|on.?prem|sovereign", "/ landing"),
    ("offline", r"offline|without internet|air.?gap", "/ landing"),
    ("private", r"\bprivate\b|privacy|no data|doesn.?t (train|use)", "/ landing"),
    ("local", r"\blocal(ly)? (ai|llm|model|rag|chat|server|inference|assistant|notebook)|"
              r"\b(ai|llm|models?|rag|chatbot) (run(ning)? )?local(ly)?\b|run .* locally|"
              r"on your (own )?(machine|computer|device)", "/ landing"),
    ("rag", r"\brag\b|chat with (your )?(pdf|doc|files)|document (chat|search|qa|intelligence)|"
            r"knowledge base|search your|ai that reads", "feature: sources"),
    ("competitor", r"anythingllm|anything llm|open ?webui|lm studio|\bjan\b|msty|khoj|"
                   r"gpt4all|ollama|onyx|open.?notebook|librechat|perplexica|privategpt", "compare pages"),
    ("pkm", r"obsidian|second brain|\bpkm\b|zettelkasten|knowledge management|notion (alternative|vs)",
     "blog: pkm"),
    ("open-source", r"open.?source (ai|llm|notebook|rag|knowledge|research|chatbot)|github", "repo + / landing"),
    ("research", r"research assistant|ai for research|research (tool|ai)|phd|academic|"
                 r"\bpapers?\b|scholar", "blog: research"),
    ("category", r"^(ai|llm) notebook$|^notebook ai$|^ai research notebook$", "/ landing"),
]

INTENT_WEIGHT = {"trans": 1.3, "comm": 1.2, "info": 1.0, "nav": 0.6, "": 1.0}


def cluster_of(keyword):
    text = keyword.lower()
    if re.search(EXCLUDE, text) and not re.search(r"surf ?sense", text):
        return "other", "—"
    for name, pattern, page in CLUSTERS:
        if re.search(pattern, text):
            return name, page
    return "other", "—"


def difficulty(props, info_backlinks):
    """(kd, source). DataForSEO leaves KD blank on most sub-100-volume terms.
    Fall back to the average referring domains of the current top 10, which is
    the raw signal KD is built from anyway: 20*log10(n+1) maps 10 domains to
    ~21, 100 to ~40, 1000 to ~60. Marked '~' in the tables."""
    kd = props.get("keyword_difficulty")
    if kd is not None:
        return kd, "kd"
    domains = (info_backlinks or {}).get("referring_domains")
    if domains is not None:
        return min(95, round(20 * math.log10(domains + 1))), "~"
    return 30, "?"


def score(volume, kd, intent, trend):
    """Opportunity, 0 to roughly 40. log volume so a 100k head term does not
    drown everything; scaled by how much of the SERP is winnable (100-kd),
    the intent's value to us, and a mild trend factor (+200% caps at 1.5x,
    -50% floors at 0.875x)."""
    trend_factor = 1 + max(-50, min(200, trend or 0)) / 400
    return round(math.log10(volume + 1) * (100 - kd) / 100
                 * INTENT_WEIGHT.get(intent, 1.0) * trend_factor * 10, 1)


def rows_score(items, min_volume, drop_other=False):
    rows = {}
    for item in items:
        keyword, info, props, serp, intent = pick(item)
        if keyword is None:
            continue
        if drop_other and cluster_of(keyword)[0] == "other":
            continue
        reported, recent, spike = effective_volume(info)
        if reported < min_volume:
            continue
        kd, kd_source = difficulty(props, (item.get("keyword_data") or item).get("avg_backlinks_info"))
        short_intent = INTENT_SHORT.get(intent.get("main_intent") or "", "")
        trend = (info.get("search_volume_trend") or {}).get("yearly")
        name, page = cluster_of(keyword)
        row = {
            "keyword": keyword,
            "volume": reported,
            "recent": recent,
            "spike": "spike" if spike else "",
            "kd": f"{kd}{'' if kd_source == 'kd' else kd_source}",
            "intent": short_intent,
            "cpc": info.get("cpc") or 0,
            "trend": trend,
            "aio": "AIO" if "ai_overview" in (serp.get("serp_item_types") or []) else "",
            "cluster": name,
            "page": page,
            "score": score(recent, kd, short_intent, trend),
        }
        if keyword not in rows or row["volume"] > rows[keyword]["volume"]:
            rows[keyword] = row
    return sorted(rows.values(), key=lambda r: -r["score"])


SCORE_COLUMNS = ["keyword", "volume", "recent", "spike", "kd", "intent", "cpc", "trend",
                 "aio", "cluster", "page", "score"]


def rows_authority(items):
    """backlinks/summary: one row per domain. `dofollow domains` is the number
    that approximates authority; raw `backlinks` is dominated by sitewide
    footers and scraper mirrors (surfsense.com: 29k backlinks, 280 domains)."""
    rows = []
    for item in items:
        domains = item.get("referring_main_domains") or 0
        nofollow = item.get("referring_main_domains_nofollow") or 0
        rows.append({
            "domain": item.get("target"),
            "rank": item.get("rank"),
            "backlinks": item.get("backlinks"),
            "ref domains": domains,
            "dofollow domains": domains - nofollow,
            "crawled pages": item.get("crawled_pages"),
            "spam": item.get("backlinks_spam_score"),
            "first seen": (item.get("first_seen") or "")[:7],
        })
    return sorted(rows, key=lambda r: -(r["dofollow domains"] or 0))


def render_serp(items, keyword=""):
    """serp/google/organic/live/advanced: the page as a reader sees it.
    Organic rows carry rank_absolute so the AI Overview and PAA boxes that push
    them down are visible; AIO citations are what a page must resemble to be
    quoted; PAA and related searches are ready-made H2s."""
    out = [f"### {keyword}".rstrip() if keyword else ""]
    organic, aio_refs, aio_pos, paa, related, paid = [], {}, None, [], [], []
    for item in items:
        kind = item.get("type")
        if kind == "organic":
            organic.append({"pos": item.get("rank_absolute"), "domain": item.get("domain"),
                            "title": (item.get("title") or "")[:70],
                            "url": (item.get("url") or "").replace("https://", "")[:70]})
        elif kind == "ai_overview":
            aio_pos = item.get("rank_absolute")
            for ref in item.get("references") or []:
                aio_refs.setdefault(ref.get("domain"), ref.get("title"))
        elif kind == "people_also_ask":
            paa += [q.get("title") for q in item.get("items") or []]
        elif kind == "related_searches" and not related:
            related = item.get("items") or []
        elif kind == "paid":
            paid.append(item.get("domain"))
    out.append(f"AI Overview: {'absolute position ' + str(aio_pos) if aio_pos else 'none'}"
               f"{'; paid: ' + ', '.join(sorted(set(paid))) if paid else ''}\n")
    if aio_refs:
        out.append("AIO citations:\n" + "\n".join(f"- {d} — {t}" for d, t in aio_refs.items()) + "\n")
    out.append(table(organic, ["pos", "domain", "title", "url"]))
    if paa:
        out.append("People also ask: " + " · ".join(paa) + "\n")
    if related:
        out.append("Related searches: " + " · ".join(related) + "\n")
    return "\n".join(out)


# --- International pass (intl/): one compact archive per market -------------

INTL = HERE / "intl"
ENDPOINT = "dataforseo_labs/google/keyword_overview/live"


def market_config():
    return json.loads((INTL / "lists.json").read_text(encoding="utf-8-sig"))


def month_dict(info):
    """monthly_searches as {"YYYY-MM": volume}, whichever shape the API used."""
    raw = info.get("monthly_searches") or {}
    if isinstance(raw, dict):
        return {key: value or 0 for key, value in raw.items()}
    return {f"{m.get('year')}-{m.get('month', 0):02d}": m.get("search_volume") or 0 for m in raw}


HISTORY_MONTHS = 12  # all effective_volume reads; search_volume_trend.yearly carries the YoY


def compact_market(items, market_id, cfg, pulled):
    """Trim a keyword_overview pull to the fields this script reads (a 1.4 MB
    full response becomes ~60 KB) and record which requested keywords came
    back empty. Under roughly 10 searches a month DataForSEO returns no row at
    all, so `missing` is the below-threshold list, distinct from 'never asked'.
    History is cut to the last HISTORY_MONTHS; the API goes back to 2019."""
    market = cfg["markets"][market_id]
    asked = list(dict.fromkeys(w for name in market["lists"] for w in cfg["lists"][name]))
    slim = {}
    for item in items:
        keyword, info, props, _serp, intent = pick(item)
        if keyword is None:
            continue
        volume = info.get("search_volume") or 0
        months = dict(sorted(month_dict(info).items())[-HISTORY_MONTHS:])
        kw_info = {"search_volume": volume}
        if info.get("cpc"):
            kw_info["cpc"] = info["cpc"]
        yearly = (info.get("search_volume_trend") or {}).get("yearly")
        if yearly is not None:
            kw_info["search_volume_trend"] = {"yearly": yearly}
        if months:
            kw_info["monthly_searches"] = months
        row = {"keyword": keyword, "keyword_info": kw_info}
        if props.get("keyword_difficulty") is not None:
            row["keyword_properties"] = {"keyword_difficulty": props["keyword_difficulty"]}
        domains = ((item.get("keyword_data") or item).get("avg_backlinks_info") or {}).get("referring_domains")
        if domains is not None:
            row["avg_backlinks_info"] = {"referring_domains": domains}
        if intent.get("main_intent"):
            row["search_intent_info"] = {"main_intent": intent["main_intent"]}
        if keyword not in slim or volume > slim[keyword]["keyword_info"]["search_volume"]:
            slim[keyword] = row
    return {
        "market": market["name"], "location_code": market["location_code"],
        "language_code": market["language_code"], "pulled": pulled, "endpoint": ENDPOINT,
        "lists": market["lists"],
        "note": "Trimmed to the fields parse.py reads; `missing` = requested keywords DataForSEO "
                "returned no row for (below its ~10/mo reporting threshold in this market).",
        "missing": [w for w in asked if w not in slim],
        "items": sorted(slim.values(), key=lambda r: -r["keyword_info"]["search_volume"]),
    }


def check_market(path, market):
    """Full API responses echo the request under tasks[].data; refuse to file a
    pull under the wrong market. (AI-mode responses carry no echo and pass.)"""
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8-sig"))
    for task in payload.get("tasks") or []:
        sent = task.get("data") or {}
        got = (sent.get("location_code"), sent.get("language_code"))
        want = (market["location_code"], market["language_code"])
        if got != want:
            sys.exit(f"{path}: response is for {got}, archive is {want}")
    return bool(payload.get("tasks"))


def write_compact(payload, path):
    """One item per line so archives diff cleanly in git."""
    head = [f' "{k}": {json.dumps(v, ensure_ascii=False)},' for k, v in payload.items() if k != "items"]
    body = ",\n  ".join(json.dumps(i, ensure_ascii=False) for i in payload["items"])
    path.write_text("{\n" + "\n".join(head) + '\n "items": [\n  ' + body + "\n ]}\n", encoding="utf-8")


# One concept per keyword across languages, first match wins. The patterns carry
# the translated terms from intl/lists.json so "lokale ki", "ia locale" and
# "ローカルllm" all land in `local`. Brand terms are sub-classified first because
# "notebooklm alternative deutsch" is an alternative search, not a language one.
# ponytail: regex, not translation; wrong for maybe one keyword in twenty, and
# a human overrides in the CSV.
NLM_CONCEPTS = [
    ("nlm-head", r"^(google )?notebooklm$|^노트북lm$"),
    ("nlm-switch", r"(open source|local|offline|private) notebooklm|"
                   r"notebooklm (open source|offline|enterprise|オープンソース|オフライン|開源|企業|法人|"
                   r"for (lawyers|business|research|students)|für anwälte)"),
    ("nlm-alternative", r"alternativ|alternatief|alternatywa|代替|代わり|類似|대안|대체|替代|"
                        r"competitor|(apps|tools) like|\bvs\b"),
    ("nlm-privacy", r"datenschutz|dsgvo|rgpd|privacy|security|セキュリティ|情報漏洩|safe|private"),
    ("podcast", r"podcast|ポッドキャスト|팟캐스트|音声概要|audio overview"),
    ("nlm-download", r"herunterladen|télécharger|descargar|baixar|scaricare|ダウンロード|다운로드|下載|"
                     r"pobierz|downloaden|download|install|desktop|windows|mac|linux|\bapp$|アプリ"),
    ("nlm-price", r"kostenlos|preis|gratuit|prix|tarif|gratis|precio|grátis|gratuito|preço|prezzo|"
                  r"無料|料金|무료|가격|免費|收費|darmow|za darmo|cena|prijs|\bpris\b|free|pricing|"
                  r"plus|\bpro\b|limit"),
    ("nlm-lang", r"deutsch|français|español|português|日本語|한국어|italiano|nederlands|po polsku|"
                 r"svenska|中文"),
]
CONCEPTS = [
    ("podcast", r"podcast|ポッドキャスト|팟캐스트"),
    ("tools", r"ollama|lm studio|anythingllm|gpt4all|jan ai|open webui|msty|khoj|librechat|onyx|"
              r"open notebook|privategpt|private gpt"),
    ("pkm", r"obsidian|zweites gehirn|second cerveau|segundo cerebro|segundo cérebro|第二の脳|second brain"),
    ("legal", r"anwält|kanzlei|avocat|abogado|advogado|avvocat|advocaten|prawnik|jurister|lawyer|legal"),
    ("air-gap", r"air.?gap|エアギャップ|에어갭"),
    ("self-hosted", r"self.?host|selbst hosten|auto.?h[ée]berg|autoaloj|auto aloj|auto hospedad|"
                    r"セルフホスト|셀프호스팅|자체 호스팅|självhostad|zelf gehost"),
    ("on-prem", r"on.?prem|sur site|オンプレ|온프레미스|地端部署|企業內部|私有化部署"),
    ("sovereign", r"sovereign|souverän|souverain|soberan|sovran|ソブリン|소버린|suverän|suwerenn|soeverein"),
    ("compliance", r"gdpr|dsgvo|rgpd|lgpd|\bavg\b|rodo|hipaa|soc 2|data residency|compliant|konform|"
                   r"conforme|資安|個資|情報漏洩|セキュリティ|セキュア|보안|secure|sicher|sécuris|segur|"
                   r"sicura|säker|veilig|bezpieczn|안전한"),
    ("offline", r"offline|hors ligne|sans internet|sin internet|sem internet|ohne internet|ohne cloud|senza internet|"
                r"オフライン|오프라인|離線|bez internetu|utan internet|zonder internet|without internet|"
                r"works offline"),
    ("rag-docs", r"chat (mit|avec|con|com|met|z|with)|chatta med|pdf|documents?|dokumente|文書|문서|"
                 r"rag\b|knowledge base|wissensdatenbank"),
    ("local", r"\blocal|lokal|locale|ローカル|로컬|本地|地端|本機|localmente|lokaal|run llama"),
    ("private", r"privat|privée|privada|private|プライベート|프라이빗|私有|prywatn|privé|confidenti|"
                r"vertraulich|datenschutz|privacy"),
    ("open-source", r"open.?source|código abierto|codigo abierto|código aberto|オープンソース|오픈소스|"
                    r"開源|öppen källkod|otwarta"),
    ("research", r"research assistant"),
]
# Demand our pages can target: everything except brand navigation, brand how-to
# and competitor brand names.
NOT_ADDRESSABLE = {"nlm-head", "nlm-other", "nlm-lang", "tools", "other"}


def concept_of(keyword):
    text = keyword.lower()
    groups = NLM_CONCEPTS if re.search(r"notebook ?lm|노트북lm", text) else CONCEPTS
    for name, pattern in groups:
        if re.search(pattern, text):
            return name
    return "nlm-other" if groups is NLM_CONCEPTS else "other"


def close_variants(items):
    """Google Ads folds close variants into one record: `self hosted llm` and
    `self-hosted llm`, `alternative` and `alternatives`, `ローカルllm` and
    `ローカル llm` all come back with the same monthly series, so summing them
    double counts. Map each later spelling to the first one carrying the same
    series (>= 6 shared months, >= 3 distinct non-zero values so flat 10/mo
    tails do not merge). ponytail: O(n^2) over < 200 keywords per market."""
    kept, variant_of = [], {}
    for item in items:  # archives are volume-desc, so the busier spelling wins
        keyword, info, *_ = pick(item)
        series = month_dict(info)
        for other_keyword, other_series in kept:
            common = series.keys() & other_series.keys()
            if len(common) >= 6 and len({series[m] for m in common} - {0}) >= 3 \
                    and all(series[m] == other_series[m] for m in common):
                variant_of[keyword] = other_keyword
                break
        else:
            kept.append((keyword, series))
    return variant_of


def rows_markets(archives, cfg):
    """archives: [(market_id, payload)]. Returns (summary rows, pivot rows,
    long rows). Volumes are the spike-damped `recent` figure, so one viral
    month does not make a market look bigger than it is, and close variants
    of one Google record count once."""
    english = set(cfg["lists"]["en-core"]) | set(cfg["lists"]["en-extended"])
    concepts = [n for n, _ in NLM_CONCEPTS] + ["nlm-other"] + \
               [n for n, _ in CONCEPTS if n != "podcast"] + ["other"]
    summary, pivot, long_rows = [], [], []
    for market_id, payload in archives:
        by_concept = dict.fromkeys(concepts, 0)
        addressable, en_addressable, value, cpcs, top = 0, 0, 0.0, [], []
        variant_of = close_variants(payload["items"])
        for item in payload["items"]:
            keyword, info, props, _serp, intent = pick(item)
            _reported, recent, _spike = effective_volume(info)
            name = concept_of(keyword)
            cpc = info.get("cpc") or 0
            is_en = keyword in english
            long_rows.append({
                "market": market_id, "language": payload["language_code"], "keyword": keyword,
                "english": "en" if is_en else "", "concept": name, "volume": info.get("search_volume") or 0,
                "recent": recent, "cpc": cpc, "kd": props.get("keyword_difficulty"),
                "intent": INTENT_SHORT.get(intent.get("main_intent") or "", ""),
                "variant_of": variant_of.get(keyword, ""),
            })
            if keyword in variant_of:
                continue
            by_concept[name] += recent
            if cpc:
                cpcs.append(cpc)
            if name not in NOT_ADDRESSABLE:
                addressable += recent
                en_addressable += recent if is_en else 0
                value += recent * cpc
                top.append((recent, keyword))
        top.sort(reverse=True)
        non_english = payload["language_code"] != "en"
        summary.append({
            "market": market_id, "lang": payload["language_code"],
            "head": by_concept["nlm-head"], "addressable": addressable, "value": int(value),
            "en share": f"{round(100 * en_addressable / addressable)}%" if non_english and addressable else "",
            "median cpc": statistics.median(cpcs) if cpcs else 0,
            "top addressable": " · ".join(f"{k} {v}" for v, k in top[:3]),
        })
        pivot.append({"market": market_id, **{c: by_concept[c] or None for c in concepts}})
    summary.sort(key=lambda r: -r["addressable"])
    order = {r["market"]: i for i, r in enumerate(summary)}
    pivot.sort(key=lambda r: order[r["market"]])
    return summary, pivot, long_rows


SUMMARY_COLUMNS = ["market", "lang", "head", "addressable", "value", "en share", "median cpc",
                   "top addressable"]
LONG_COLUMNS = ["market", "language", "keyword", "english", "concept", "volume", "recent", "cpc",
                "kd", "intent", "variant_of"]


def table(rows, columns):
    if not rows:
        return "_no rows_\n"
    out = ["| " + " | ".join(columns) + " |",
           "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column)
            if value is None or value == "":
                cells.append("—")
            elif isinstance(value, float):
                cells.append(f"{value:.2f}")
            else:
                cells.append(str(value))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def self_check():
    """One runnable check: every shape parses and sorts."""
    overview = {"items": [{
        "keyword": "local rag", "keyword_info": {"search_volume": 500, "cpc": 1.5,
        "search_volume_trend": {"yearly": 20}},
        "keyword_properties": {"keyword_difficulty": 30},
        "serp_info": {"serp_item_types": ["ai_overview", "organic", "images"]},
        "search_intent_info": {"main_intent": "informational"}}]}
    nested = {"tasks": [{"result": [{"items": [{"keyword_data": {
        "keyword": "offline ai", "keyword_info": {"search_volume": 900},
        "keyword_properties": {"keyword_difficulty": 40},
        "search_intent_info": {"main_intent": "commercial"}},
        "ranked_serp_element": {"serp_item": {"rank_absolute": 3,
        "relative_url": "/docs"}}}]}]}]}

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        flat = pathlib.Path(tmp) / "flat.json"
        deep = pathlib.Path(tmp) / "deep.json"
        flat.write_text(json.dumps(overview))
        deep.write_text(json.dumps(nested))

        rows = rows_metrics(load(flat), 0)
        assert len(rows) == 1, rows
        assert rows[0]["keyword"] == "local rag"
        assert rows[0]["kd"] == 30
        assert rows[0]["intent"] == "info"
        # Only whitelisted features survive; "images" must be dropped.
        assert rows[0]["features"] == "AIO", rows[0]["features"]

        ranked = rows_ranked(load(deep), 0)
        assert ranked[0]["pos"] == 3 and ranked[0]["url"] == "/docs", ranked
        assert ranked[0]["intent"] == "comm"

        # min_volume filters, and the nested shape is reachable via tasks[].
        assert rows_metrics(load(deep), 1000) == []
        assert len(rows_metrics(load(deep), 100)) == 1

        # Dedupe keeps the larger reading.
        dupes = [{"keyword": "x", "keyword_info": {"search_volume": 10}},
                 {"keyword": "x", "keyword_info": {"search_volume": 99}}]
        deduped = rows_metrics(dupes, 0)
        assert len(deduped) == 1 and deduped[0]["volume"] == 99, deduped

        # Grouping by URL sums volume and keeps the best (lowest) position.
        two_pages = [
            {"keyword": "a", "keyword_info": {"search_volume": 100},
             "ranked_serp_element": {"serp_item": {"relative_url": "/free",
                                                   "rank_absolute": 9, "etv": 1.5}}},
            {"keyword": "b", "keyword_info": {"search_volume": 400},
             "ranked_serp_element": {"serp_item": {"relative_url": "/free",
                                                   "rank_absolute": 4, "etv": 2.5}}},
            {"keyword": "c", "keyword_info": {"search_volume": 50},
             "ranked_serp_element": {"serp_item": {"relative_url": "/", "rank_absolute": 7}}},
        ]
        pages = rows_urls(two_pages)
        assert pages[0]["url"] == "/free", pages
        assert pages[0]["keywords"] == 2 and pages[0]["volume"] == 500, pages
        assert pages[0]["best_pos"] == 4 and pages[0]["etv"] == 4.0, pages
        assert pages[1]["etv"] == 0.0 and pages[1]["best_pos"] == 7, pages

        # Gzipped pulls load identically to plain JSON.
        import gzip
        packed = pathlib.Path(tmp) / "packed.json.gz"
        with gzip.open(packed, "wt", encoding="utf-8") as handle:
            json.dump(overview, handle)
        assert rows_metrics(load(packed), 0) == rows_metrics(load(flat), 0)

        assert "no rows" in table([], ["keyword"])

        # Gap rows read target1's element; the second domain has none by design.
        gap = [{"keyword_data": {"keyword": "notebooklm alternative",
                                 "keyword_info": {"search_volume": 590}},
                "first_domain_serp_element": {"rank_absolute": 5, "relative_url": "/blog/alt"}}]
        assert rows_gap(gap, 0)[0]["pos"] == 5 and rows_gap(gap, 0)[0]["url"] == "/blog/alt"

        # Spike damping: one 10x month must not lift the effective volume, but a
        # sustained three-month ramp must keep it. Both shapes of monthly data.
        flat_months = {f"2026-{m:02d}": 2000 for m in range(1, 12)}
        flat_months["2026-07"] = 60000  # the July spike
        spiky = {"search_volume": 8100, "monthly_searches": flat_months}
        reported, recent, spike = effective_volume(spiky)
        assert (reported, recent, spike) == (8100, 2000, True), (reported, recent, spike)
        ramp = {"search_volume": 2900, "monthly_searches": [
            {"year": 2025, "month": 9 + i, "search_volume": v} for i, v in
            enumerate([480, 720, 720, 590])] + [
            {"year": 2026, "month": i + 1, "search_volume": v} for i, v in
            enumerate([720, 880, 880, 720, 1000, 4400, 6600, 14800])]}
        reported, recent, spike = effective_volume(ramp)
        assert (reported, recent) == (2900, 2900), (reported, recent)  # min(reported, 6600)
        assert spike is True  # still flagged so the reader sees the shape

        # Difficulty falls back to referring domains, marked as a proxy.
        assert difficulty({"keyword_difficulty": 12}, {"referring_domains": 5000}) == (12, "kd")
        assert difficulty({}, {"referring_domains": 99}) == (40, "~")
        assert difficulty({}, None) == (30, "?")

        # Cluster regexes: first match wins, in the order that matters.
        assert cluster_of("notebooklm mcp")[0] == "mcp"
        assert cluster_of("open source notebooklm")[0] == "notebooklm-switch"
        assert cluster_of("notebooklm download")[0] == "notebooklm-install"
        assert cluster_of("notebooklm for windows")[0] == "notebooklm-install"
        assert cluster_of("privategpt")[0] == "competitor"
        assert cluster_of("private ai")[0] == "private"
        assert cluster_of("is notebooklm free")[0] == "notebooklm-pricing"
        assert cluster_of("notebooklm price")[0] == "notebooklm-pricing"
        assert cluster_of("how many sources can you add to notebooklm")[0] == "notebooklm-pricing"
        assert cluster_of("notebooklm")[0] == "notebooklm-nav"
        assert cluster_of("google notebooklm")[0] == "notebooklm-nav"
        assert cluster_of("notebooklm for students")[0] == "notebooklm-brand"
        assert cluster_of("obsidian vs notebooklm")[0] == "notebooklm-switch"
        assert cluster_of("self hosted ai")[0] == "self-hosted"
        assert cluster_of("hipaa compliant ai")[0] == "compliance"
        assert cluster_of("local ai models")[0] == "local"
        assert cluster_of("turn notes into podcast")[0] == "podcast"
        assert cluster_of("ai notebook")[0] == "category"
        assert cluster_of("surfsense ai")[0] == "brand"
        # Studio outputs: the NotebookLM-branded form lands on the feature, the
        # named edtech tool on competitor, generic study/quiz/video chatter on other.
        for keyword, expected in [("notebooklm mind map", "mindmap"), ("pdf to flashcards", "flashcards"),
                                  ("study guide maker", "study"), ("notebooklm for studying", "study"),
                                  ("quiz generator from pdf", "quiz"), ("pdf summarizer", "summary"),
                                  ("notebooklm slide deck", "slides"), ("notebooklm infographic", "infographic"),
                                  ("literature review ai", "report"), ("ai spreadsheet generator", "spreadsheet"),
                                  ("notebooklm video overview", "video"), ("quillbot summarizer", "competitor"),
                                  ("presentation skills", "other"), ("learning style quiz", "other"),
                                  ("study tips", "other"), ("text to video ai", "other")]:
            assert cluster_of(keyword)[0] == expected, (keyword, cluster_of(keyword)[0], expected)
        # EXCLUDE: shares a word with a cluster but is not our market.
        for noise in ("laptop local", "best ai podcasts", "open source ai coding agent",
                      "notion ai", "local ai", "banana"):
            assert cluster_of(noise)[0] == "other", noise

        # Score: more winnable volume scores higher; navigational is discounted.
        assert score(1000, 10, "comm", 0) > score(1000, 60, "comm", 0)
        assert score(1000, 10, "nav", 0) < score(1000, 10, "info", 0)
        assert score(0, 10, "info", 0) == 0

        # History averages per year and names the peak month.
        hist = [{"keyword": "x", "keyword_info": {"monthly_searches": [
            {"year": 2025, "month": 1, "search_volume": 100},
            {"year": 2025, "month": 2, "search_volume": 300},
            {"year": 2026, "month": 1, "search_volume": 900}]}}]
        row = rows_history(hist)[0]
        assert row["2025"] == 200 and row["2026"] == 900 and row["peak"] == "900 (2026-01)", row

        # Baseline: only the named landing page, and volume-heavy rows that rank
        # nowhere must not be mistaken for value. `free ai`-shaped row is 100x the
        # volume of the no-signup row and worth less.
        ranked = [
            {"keyword": "free ai", "keyword_info": {"search_volume": 110000},
             "ranked_serp_element": {"serp_item": {"relative_url": "/free", "rank_absolute": 28,
                                                   "etv": 231.0}}},
            {"keyword": "chat free no sign up", "keyword_info": {"search_volume": 6600},
             "ranked_serp_element": {"serp_item": {"relative_url": "/free", "rank_absolute": 6,
                                                   "etv": 223.08}}},
            {"keyword": "chatgpt without login", "keyword_info": {"search_volume": 1900},
             "ranked_serp_element": {"serp_item": {"relative_url": "/free", "rank_absolute": 18,
                                                   "etv": 9.69}}},
            {"keyword": "notebooklm alternative", "keyword_info": {"search_volume": 1300},
             "ranked_serp_element": {"serp_item": {"relative_url": "/", "rank_absolute": 1,
                                                   "etv": 99.0}}},
        ]
        assert [r["keyword"] for r in landing_rows(ranked, "/free")] == \
            ["free ai", "chat free no sign up", "chatgpt without login"], landing_rows(ranked, "/free")
        rendered = render_baseline(ranked, "/free")
        assert "3 keywords, 118,500 volume, $464 etv" in rendered, rendered
        # 21+ holds 93.8% of volume and 51.9% of value; the no-signup cluster holds
        # 1 of 1 top-10 positions. Both are the shape the /free decision rests on.
        assert "| 21+ | 1 | 110,000 | 92.8% | $231 | 49.8% |" in rendered, rendered
        assert "| no sign up / no login / no account | 2 | 8,500 | $233 | 50.2% | 1 of 1 |" \
            in rendered, rendered
        assert "| hosted brand terms | 1 | 1,900 | $10 | 2.1% | 0 of 1 |" in rendered, rendered
        assert "| everything else | 1 | 110,000 | $231 | 49.8% | 0 of 1 |" in rendered, rendered
        assert render_baseline(ranked, "/nope") == "_no rows under /nope_\n"

        # Concepts: brand terms sub-classify first, translations share a row.
        for keyword, expected in [
            ("notebooklm", "nlm-head"), ("notebooklm alternative deutsch", "nlm-alternative"),
            ("notebooklm für anwälte", "nlm-switch"), ("open source notebooklm", "nlm-switch"),
            ("notebooklm 音声概要", "podcast"), ("télécharger notebooklm", "nlm-download"),
            ("notebooklm app", "nlm-download"), ("is notebooklm free", "nlm-price"),
            ("notebooklm 無料", "nlm-price"), ("notebooklm deutsch", "nlm-lang"),
            ("notebooklm mcp", "nlm-other"), ("is notebooklm private", "nlm-privacy"),
            ("lokale ki", "local"), ("ローカルllm", "local"), ("ia en local", "local"),
            ("run llama locally", "local"), ("ki ohne cloud", "offline"), ("ia sans internet", "offline"),
            ("dsgvo konforme ki", "compliance"), ("ki datenschutz", "private"), ("私有 llm", "private"),
            ("私有化部署 llm", "on-prem"), ("ia auto-hébergée", "self-hosted"), ("souveräne ki", "sovereign"),
            ("open source chatgpt alternative", "open-source"), ("private gpt", "tools"),
            ("ki für anwälte", "legal"), ("chat mit pdf", "rag-docs"), ("ローカルrag", "rag-docs"),
            ("zweites gehirn ki", "pkm"), ("air gapped ki", "air-gap"), ("banana", "other"),
        ]:
            assert concept_of(keyword) == expected, (keyword, concept_of(keyword), expected)

        # Compaction keeps only what the readers use, computes `missing` from the
        # requested lists, and round-trips through write_compact/load.
        cfg = {"lists": {"en-core": ["local llm", "private ai"], "en-extended": ["chat with pdf"],
                         "de": ["lokale ki"]},
               "markets": {"de-de": {"location_code": 2276, "language_code": "de",
                                     "name": "Germany / German", "lists": ["de", "en-core", "en-extended"]}}}
        raw = [{"keyword": "lokale ki", "keyword_info": {
                    "search_volume": 720, "cpc": 1.5, "competition": 0.2, "categories": [1],
                    "search_volume_trend": {"yearly": 40, "monthly": -5},
                    "monthly_searches": [{"year": 2026, "month": 8, "search_volume": 880},
                                         {"year": 2026, "month": 7, "search_volume": 720}]},
                "keyword_properties": {"keyword_difficulty": 12, "detected_language": "de"},
                "avg_backlinks_info": {"referring_domains": 40.5, "backlinks": 900},
                "search_intent_info": {"main_intent": "informational", "foreign_intent": ["x"]}},
               {"keyword": "local llm", "keyword_info": {"search_volume": 1000}},
               {"keyword": "local llm", "keyword_info": {"search_volume": 1300}}]
        packed = compact_market(raw, "de-de", cfg, "2026-09-14")
        assert packed["missing"] == ["private ai", "chat with pdf"], packed["missing"]
        assert [i["keyword"] for i in packed["items"]] == ["local llm", "lokale ki"]  # by volume, deduped
        first = packed["items"][1]
        assert first["keyword_info"] == {"search_volume": 720, "cpc": 1.5, "search_volume_trend": {"yearly": 40},
                                         "monthly_searches": {"2026-07": 720, "2026-08": 880}}, first
        assert first["keyword_properties"] == {"keyword_difficulty": 12}
        assert first["avg_backlinks_info"] == {"referring_domains": 40.5}
        assert "competition" not in json.dumps(packed) and "foreign_intent" not in json.dumps(packed)
        out = pathlib.Path(tmp) / "de-de.json"
        write_compact(packed, out)
        assert json.loads(out.read_text(encoding="utf-8"))["missing"] == packed["missing"]
        assert rows_metrics(load(out), 0)[0]["keyword"] == "local llm"

        # History is cut to HISTORY_MONTHS.
        long_series = [{"year": 2024, "month": m, "search_volume": 10} for m in range(1, 13)] + \
                      [{"year": 2025, "month": m, "search_volume": 10} for m in range(1, 13)] + \
                      [{"year": 2026, "month": m, "search_volume": 10} for m in range(1, 7)]
        cut = compact_market([{"keyword": "local llm", "keyword_info": {"search_volume": 10, "monthly_searches": long_series}}],
                             "de-de", cfg, "2026-09-14")["items"][0]["keyword_info"]["monthly_searches"]
        assert len(cut) == HISTORY_MONTHS and min(cut) == "2025-07" and max(cut) == "2026-06", cut

        # Markets: English share counts only addressable demand; pivot lands the
        # German term in the same `local` column as the English one.
        summary, pivot, long_rows = rows_markets([("de-de", packed)], cfg)
        assert summary[0]["addressable"] == 1300 + 720 and summary[0]["en share"] == "64%", summary
        assert pivot[0]["local"] == 2020 and pivot[0]["nlm-head"] is None, pivot
        assert {r["english"] for r in long_rows} == {"en", ""}

        # Close variants of one Google record count once; flat 10/mo tails do not merge.
        wave = dict(zip((f"2026-{m:02d}" for m in range(1, 9)), [100, 120, 90, 100, 130, 110, 100, 90]))
        flat = dict.fromkeys(wave, 10)
        twins = [{"keyword": "self hosted llm", "keyword_info": {"search_volume": 100, "monthly_searches": wave}},
                 {"keyword": "self-hosted llm", "keyword_info": {"search_volume": 100,
                                                                 "monthly_searches": {**wave, "2026-09": 100}}},
                 {"keyword": "notebooklm desktop app", "keyword_info": {"search_volume": 10, "monthly_searches": flat}},
                 {"keyword": "notebooklm for windows", "keyword_info": {"search_volume": 10, "monthly_searches": flat}}]
        assert close_variants(twins) == {"self-hosted llm": "self hosted llm"}, close_variants(twins)
        cfg_en = {"lists": {"en-core": [t["keyword"] for t in twins], "en-extended": []},
                  "markets": {"gb-en": {"location_code": 2826, "language_code": "en", "name": "UK",
                                        "lists": ["en-core"]}}}
        summary, pivot, long_rows = rows_markets([("gb-en", {"language_code": "en", "items": twins})], cfg_en)
        assert summary[0]["addressable"] == 100 + 10 + 10 and pivot[0]["self-hosted"] == 100, summary
        assert [r["variant_of"] for r in long_rows] == ["", "self hosted llm", "", ""], long_rows
    print("parse.py self-check OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="JSON files or globs in this directory")
    ap.add_argument("--mode", default="metrics",
                    choices=["metrics", "ranked", "competitors", "urls", "gap", "history", "score",
                             "authority", "serp", "markets", "baseline"])
    ap.add_argument("--url-prefix", default="/free",
                    help="landing page to split in --mode baseline")
    ap.add_argument("--min-volume", type=int, default=0)
    ap.add_argument("--csv", help="score/markets mode: also write the full list here")
    ap.add_argument("--top", type=int, default=0, help="score mode: rows to print (0 = all)")
    ap.add_argument("--drop-other", action="store_true",
                    help="score mode: skip keywords no cluster regex claims (generic AI noise)")
    ap.add_argument("--compact-from", nargs="+", metavar="RAW",
                    help="keyword_overview response(s) to trim into intl/<market>.json")
    ap.add_argument("--market", help="market id from intl/lists.json, with --compact-from")
    ap.add_argument("--pulled", default=datetime.date.today().isoformat(),
                    help="date stamp for --compact-from (default: today)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    if args.compact_from:
        if not args.market:
            sys.exit("--compact-from needs --market <id from intl/lists.json>")
        cfg = market_config()
        verified = all(check_market(raw, cfg["markets"][args.market]) for raw in args.compact_from)
        items = [item for raw in args.compact_from for item in load(raw)]
        payload = compact_market(items, args.market, cfg, args.pulled)
        target = INTL / f"{args.market}.json"
        write_compact(payload, target)
        print(f"{target.name}: {len(payload['items'])} keywords, {len(payload['missing'])} missing, "
              f"location {'verified' if verified else 'unverified (AI-mode response)'}")
        return

    if args.mode == "markets":
        cfg = market_config()
        # PowerShell does not expand globs, so do it here; no files = every market.
        archive_paths = [pathlib.Path(p) for pattern in args.files
                         for p in sorted(glob.glob(str(HERE / pattern)))] or sorted(INTL.glob("*-*.json"))
        archives = [(p.stem, json.loads(p.read_text(encoding="utf-8-sig"))) for p in archive_paths]
        summary, pivot, long_rows = rows_markets(archives, cfg)
        print(f"<!-- {len(archives)} markets from {INTL.name}/ -->\n")
        print(table(summary, SUMMARY_COLUMNS))
        print(table(pivot, list(pivot[0].keys()) if pivot else ["market"]))
        if args.csv:
            target = (HERE / args.csv).resolve()
            with target.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=LONG_COLUMNS)
                writer.writeheader()
                writer.writerows(long_rows)
            print(f"<!-- wrote {len(long_rows)} rows to {target.name} -->")
        return

    paths = []
    for pattern in args.files:
        # Pulls are stored gzipped, but accept the bare .json name too so the
        # filenames quoted in the research docs keep working.
        found = sorted(set(glob.glob(str(HERE / pattern))) |
                       set(glob.glob(str(HERE / (pattern + ".gz")))))
        paths.extend(found or [pattern])
    if not paths:
        sys.exit("nothing to parse; pass a filename or --self-check")

    if args.mode == "serp":
        # One SERP per file; the keyword is the filename minus the serp- prefix.
        for path in paths:
            name = pathlib.Path(path).name.split(".")[0]
            print(render_serp(load(path), name.removeprefix("serp-").replace("-", " ")))
        return

    items = []
    for path in paths:
        items.extend(load(path))
    print(f"<!-- {len(items)} items from {', '.join(pathlib.Path(p).name for p in paths)} -->\n")

    if args.mode == "authority":
        print(table(rows_authority(items), ["domain", "rank", "backlinks", "ref domains",
                                            "dofollow domains", "crawled pages", "spam", "first seen"]))
    elif args.mode == "competitors":
        print(table(rows_competitors(items),
                    ["domain", "intersections", "median_pos", "avg_pos", "visibility", "keywords"]))
    elif args.mode == "urls":
        print(table(rows_urls(items), ["url", "keywords", "volume", "etv", "best_pos"]))
    elif args.mode == "baseline":
        print(render_baseline(items, args.url_prefix))
    elif args.mode == "ranked":
        print(table(rows_ranked(items, args.min_volume),
                    ["keyword", "volume", "kd", "pos", "intent", "url"]))
    elif args.mode == "gap":
        print(table(rows_gap(items, args.min_volume),
                    ["keyword", "volume", "kd", "pos", "intent", "url"]))
    elif args.mode == "history":
        rows = rows_history(items)
        years = sorted({k for r in rows for k in r if k.isdigit()})
        print(table(rows, ["keyword", *years, "peak"]))
    elif args.mode == "score":
        rows = rows_score(items, args.min_volume, args.drop_other)
        if args.csv:
            target = (HERE / args.csv).resolve()
            with target.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=SCORE_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            print(f"<!-- wrote {len(rows)} rows to {target.name} -->\n")
        print(table(rows[:args.top] if args.top else rows, SCORE_COLUMNS))
    else:
        print(table(rows_metrics(items, args.min_volume),
                    ["keyword", "volume", "recent", "kd", "intent", "cpc", "trend", "features"]))


if __name__ == "__main__":
    main()
