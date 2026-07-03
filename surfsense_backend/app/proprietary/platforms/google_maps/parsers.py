"""Pure, I/O-free parsing of Google Maps' protobuf-over-JSON place data.

Google Maps returns a place's data as a deeply-nested JSON array (no field
names, just positions) from the ``/maps/preview/place`` RPC (element ``jd[6]``,
the ``darray``). Fields are read by fixed array paths.

The array paths are ported from the actively-maintained ``gosom/google-maps-
scraper`` (Go), which tracks Google's periodic structure shifts and carries
fallback paths (e.g. the Nov-2025 opening-hours move). Everything here is
deterministic and offline-unit-testable against captured fixtures.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def dig(obj: Any, *path: int) -> Any:
    """Safely walk a nested list by integer indices; ``None`` if any step misses.

    The Python twin of gosom's ``getNthElementAndCast`` — Maps arrays are ragged
    and shift between updates, so every access must tolerate a short/absent path.
    """
    cur = obj
    for idx in path:
        if not isinstance(cur, list) or idx >= len(cur) or cur[idx] is None:
            return None
        cur = cur[idx]
    return cur


def _dig_str(obj: Any, *path: int) -> str | None:
    val = dig(obj, *path)
    return val if isinstance(val, str) else None


def _dig_num(obj: Any, *path: int) -> float | None:
    val = dig(obj, *path)
    return val if isinstance(val, int | float) else None


def brace_match_json(text: str, start: int) -> str | None:
    """Return the balanced ``[...]`` / ``{...}`` blob beginning at ``text[start]``."""
    open_ch = text[start]
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


def _opening_hours(darray: list) -> list[dict[str, str]]:
    """Weekly hours. New layout (Nov 2025) at [203][0], old at [34][1]."""
    items = dig(darray, 203, 0) or dig(darray, 34, 1) or []
    hours: list[dict[str, str]] = []
    for item in items if isinstance(items, list) else []:
        day = _dig_str(item, 0)
        if not day:
            continue
        slots = dig(item, 3)  # new format: [ [label, [[h,m],[h,m]]], ... ]
        times: list[str] = []
        if isinstance(slots, list) and slots:
            times = [_dig_str(s, 0) for s in slots if _dig_str(s, 0)]
        else:  # old format: [1] is a flat list of strings
            old = dig(item, 1)
            times = (
                [t for t in old if isinstance(t, str)] if isinstance(old, list) else []
            )
        hours.append({"day": day, "hours": ", ".join(times) if times else "Closed"})
    return hours


def _categories(darray: list) -> list[str]:
    cats = dig(darray, 13)
    return [c for c in cats if isinstance(c, str)] if isinstance(cats, list) else []


def _website(darray: list) -> str | None:
    raw = _dig_str(darray, 7, 0)
    if raw and raw.startswith("/url?q="):  # Google redirect wrapper
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(raw).query).get("q", [None])[0]
        return q or raw
    return raw


def _additional_info(darray: list) -> dict[str, Any] | None:
    """About sections (``darray[100][1]``) in Apify's ``additionalInfo`` shape:
    ``{"Accessibility": [{"Wheelchair accessible entrance": true}, ...], ...}``.

    Option paths mirror gosom's About parser; enabled state is
    ``option[2][1][0][0] == 1``.
    """
    sections = dig(darray, 100, 1)
    if not isinstance(sections, list):
        return None
    info: dict[str, Any] = {}
    for section in sections:
        name = _dig_str(section, 1)
        options = dig(section, 2)
        if not name or not isinstance(options, list):
            continue
        entries = []
        for opt in options:
            opt_name = _dig_str(opt, 1)
            if opt_name:
                entries.append({opt_name: dig(opt, 2, 1, 0, 0) == 1})
        if entries:
            info[name] = entries
    return info or None


def _link_sources(items: Any, link_path: tuple, source_path: tuple) -> list[dict]:
    """Extract ``[{"url":…, "source":…}]`` pairs from a link-source array."""
    out = []
    for item in items if isinstance(items, list) else []:
        url = _dig_str(item, *link_path)
        source = _dig_str(item, *source_path)
        if url and source:
            out.append({"url": url, "source": source})
    return out


def _order_links(darray: list) -> list[dict]:
    """Order-online providers (paths from gosom, two known layouts)."""
    items = dig(darray, 75, 0, 1, 2) or dig(darray, 75, 0, 0, 2)
    return _link_sources(items, (1, 2, 0), (0, 0))


# Day numbers Google uses in the popular-times block (gosom's mapping),
# rendered as Apify's two-letter histogram keys.
_DAY_KEYS = {1: "Mo", 2: "Tu", 3: "We", 4: "Th", 5: "Fr", 6: "Sa", 7: "Su"}


def _popular_times(darray: list) -> dict[str, Any]:
    """Popular-times block (``darray[84]``) in Apify's field shapes.

    ``[84][0]`` is a list of ``[day_num, [[hour, occupancy%, …], …]]`` days;
    ``[84][6]`` is the live busyness text and ``[84][7][1]`` the live percent.
    """
    out: dict[str, Any] = {}
    days = dig(darray, 84, 0)
    if isinstance(days, list):
        histogram: dict[str, list] = {}
        for day in days:
            key = _DAY_KEYS.get(dig(day, 0))
            hours = dig(day, 1)
            if not key or not isinstance(hours, list):
                continue
            histogram[key] = [
                {"hour": h[0], "occupancyPercent": h[1]}
                for h in hours
                if isinstance(h, list) and len(h) >= 2
            ]
        if histogram:
            out["popularTimesHistogram"] = histogram
    live_text = _dig_str(darray, 84, 6)
    if live_text:
        out["popularTimesLiveText"] = live_text
    live_pct = _dig_num(darray, 84, 7, 1)
    if live_pct is not None:
        out["popularTimesLivePercent"] = int(live_pct)
    return out


def _reviews_tags(darray: list) -> list[dict]:
    """Review keyword tags (``darray[153][0]``): ``[{title, count}, …]``."""
    entries = dig(darray, 153, 0)
    out = []
    for e in entries if isinstance(entries, list) else []:
        title = _dig_str(e, 1)
        count = _dig_num(e, 3, 4)
        if title and count is not None:
            out.append({"title": title, "count": int(count)})
    return out


def _image_fields(darray: list) -> dict[str, Any]:
    """Image gallery fields: count, category tab names, and photo URLs.

    ``darray[37]`` holds ``[hero_photos, total_count]``; ``darray[171][0]``
    holds the gallery tabs (each with a thumbnail). ``ponytail:`` anonymous
    sessions only expose the few hero photos + one thumbnail per tab, not the
    full gallery — scraping thousands of photos would need the signed-in
    photo-listing RPC. ``imageUrls`` therefore tops out around a dozen.
    """
    out: dict[str, Any] = {}
    count = _dig_num(darray, 37, 1)
    if count is not None:
        out["imagesCount"] = int(count)
    tabs = dig(darray, 171, 0)
    urls: list[str] = []
    if isinstance(tabs, list):
        categories = [t for tab in tabs if (t := _dig_str(tab, 2))]
        if categories:
            out["imageCategories"] = categories
        urls.extend(
            u for tab in tabs if (u := _dig_str(tab, 3, 0, 6, 0)) and u not in urls
        )
    heroes = dig(darray, 37, 0)
    for photo in heroes if isinstance(heroes, list) else []:
        u = _dig_str(photo, 6, 0)
        if u and u not in urls:
            urls.append(u)
    if urls:
        out["imageUrls"] = urls
    return out


def _hotel_fields(darray: list) -> dict[str, Any]:
    """Hotel block (``darray[35]`` + ``[64]``), only present for lodging.

    Paths probed live on The Plaza (NYC): ``[35][6]`` star string,
    ``[35][0]/[1]`` the check-in/out dates the price quotes are for,
    ``[35][29][0]`` similar hotels, ``[35][44]`` booking-partner ads.
    """
    stars = _dig_str(darray, 35, 6) or (
        f"{int(n)} stars" if (n := _dig_num(darray, 64, 0)) else None
    )
    if not stars:
        return {}
    out: dict[str, Any] = {"hotelStars": stars}
    description = _dig_str(darray, 32, 1, 1)
    if description:
        out["hotelDescription"] = description
    check_in = _dig_str(darray, 35, 0)
    check_out = _dig_str(darray, 35, 1)
    if check_in:
        out["checkInDate"] = check_in
    if check_out:
        out["checkOutDate"] = check_out

    similar = []
    for entry in dig(darray, 35, 29, 0) or []:
        info = dig(entry, 0)
        title = _dig_str(info, 4)
        if not title:
            continue
        hotel: dict[str, Any] = {"title": title, "fid": _dig_str(info, 2)}
        if (score := _dig_num(info, 7)) is not None:
            hotel["totalScore"] = score
        if (count := _dig_num(info, 8)) is not None:
            hotel["reviewsCount"] = int(count)
        lat, lng = _dig_num(info, 3, 2), _dig_num(info, 3, 3)
        if lat is not None and lng is not None:
            hotel["location"] = {"lat": lat, "lng": lng}
        if desc := _dig_str(entry, 1):
            hotel["description"] = desc
        similar.append(hotel)
    if similar:
        out["similarHotelsNearby"] = similar

    ads = []
    for ad in dig(darray, 35, 44) or []:
        title = _dig_str(ad, 0)
        url = _dig_str(ad, 5, 0)
        if not title or not url:
            continue
        item: dict[str, Any] = {"title": title, "url": url}
        if price := _dig_str(ad, 1):
            item["price"] = price
        ads.append(item)
    if ads:
        out["hotelAds"] = ads
    return out


def _cid_from_fid(fid: str | None) -> str | None:
    """CID (a.k.a. ludocid) = the decimal value of the fid's second hex half."""
    if not fid or ":" not in fid:
        return None
    try:
        return str(int(fid.split(":")[1], 16))
    except ValueError:
        return None


def parse_place(darray: list) -> dict[str, Any]:
    """Map a place ``darray`` to PlaceItem-shaped fields (public Maps data only).

    Only fields with a stable, known array path are populated; the rest stay at
    their schema defaults. Paths mirror gosom's ``EntryFromJSON``.
    """
    lat = _dig_num(darray, 9, 2)
    lng = _dig_num(darray, 9, 3)
    dist = dig(darray, 175, 3)  # per-star review counts [1★,2★,3★,4★,5★]

    result: dict[str, Any] = {
        "title": _dig_str(darray, 11),
        "categories": _categories(darray),
        "address": _dig_str(darray, 18),
        "website": _website(darray),
        "phone": _dig_str(darray, 178, 0, 0),
        "plusCode": _dig_str(darray, 183, 2, 2, 0),
        "totalScore": _dig_num(darray, 4, 7),
        "reviewsCount": (int(v) if (v := _dig_num(darray, 4, 8)) is not None else None),
        "price": _dig_str(darray, 4, 2),
        "description": _dig_str(darray, 32, 1, 1),
        "placeId": _dig_str(darray, 78),
        "fid": _dig_str(darray, 10),
        "kgmid": _dig_str(darray, 89),
        "menu": _dig_str(darray, 38, 0),
        "imageUrl": _dig_str(darray, 72, 0, 1, 6, 0),
        "additionalInfo": _additional_info(darray),
    }
    result["cid"] = _cid_from_fid(result["fid"])

    reservations = _link_sources(dig(darray, 46), (0,), (1,))
    if reservations:
        result["tableReservationLinks"] = reservations
        result["reserveTableUrl"] = reservations[0]["url"]
    order_links = _order_links(darray)
    if order_links:
        result["orderBy"] = order_links  # Apify's field name for these
        food = next(
            (o["url"] for o in order_links if "food.google.com" in o["url"]), None
        )
        if food:
            result["googleFoodUrl"] = food
    if result["categories"]:
        result["categoryName"] = result["categories"][0]
    if lat is not None and lng is not None:
        result["location"] = {"lat": lat, "lng": lng}
    if isinstance(dist, list) and len(dist) >= 5:
        result["reviewsDistribution"] = {
            "oneStar": int(dist[0] or 0),
            "twoStar": int(dist[1] or 0),
            "threeStar": int(dist[2] or 0),
            "fourStar": int(dist[3] or 0),
            "fiveStar": int(dist[4] or 0),
        }
    hours = _opening_hours(darray)
    if hours:
        result["openingHours"] = hours

    result.update(_popular_times(darray))
    result.update(_image_fields(darray))
    result.update(_hotel_fields(darray))
    tags = _reviews_tags(darray)
    if tags:
        result["reviewsTags"] = tags

    # Closed status: darray[88][0] carries a status enum for closed places
    # ('CLOSED' verified live on a permanently-closed place; open places have
    # None or an editorial snippet there, so only exact enums count).
    status = _dig_str(darray, 88, 0)
    if status in ("CLOSED", "CLOSED_PERMANENTLY"):
        result["permanentlyClosed"] = True
    elif status == "CLOSED_TEMPORARILY":
        result["temporarilyClosed"] = True

    # Complete address components (borough/street/city/postal/state/country).
    result["neighborhood"] = _dig_str(darray, 183, 1, 0)
    result["street"] = _dig_str(darray, 183, 1, 1)
    result["city"] = _dig_str(darray, 183, 1, 3)
    result["postalCode"] = _dig_str(darray, 183, 1, 4)
    result["state"] = _dig_str(darray, 183, 1, 5)
    result["countryCode"] = _dig_str(darray, 183, 1, 6)

    return {k: v for k, v in result.items() if v is not None}


# --- reviews (GetLocalBoqProxy) ----------------------------------------------
#
# The BOQ proxy returns ``jd[1][10]`` = ``[.., reviews, .., nextToken]``. Each
# review ``r`` is a flat ~48-slot array. Index map (verified against live
# captures, matching the ``google-maps-review-scraper`` npm package):
#   r[1]  stars                r[2]  [relativeDate, ?, publishedMs]
#   r[3]  [name, photoUrl, contribUrl, nReviews, nPhotos, [?, localGuide]]
#   r[4]  owner reply [?, relativeDate, text, ...]
#   r[5]  reviewId             r[12] reviewUrl
#   r[13]/r[14] images [[url, caption, ...], ...]
#   r[26] language             r[27] text        r[28] translated text
#   r[30] guided Q&A (context + per-aspect ratings)   r[44] [origin, ...]


_CONTRIB_ID_RE = re.compile(r"/contrib/(\d+)")


def _ms_to_iso(ms: Any) -> str | None:
    """Convert a millisecond epoch (Google sends it as a string) to ISO-8601."""
    try:
        ms_val = float(ms)
    except (TypeError, ValueError):
        return None
    if not ms_val:
        return None
    from datetime import UTC, datetime

    try:
        dt = datetime.fromtimestamp(ms_val / 1000, tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _review_images(r: Any) -> list[str]:
    for idx in (13, 14):
        imgs = dig(r, idx)
        if isinstance(imgs, list):
            urls = [_dig_str(imgs, j, 0) for j in range(len(imgs))]
            return [u for u in urls if u]
    return []


def _guided_answers(r: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split the guided Q&A block into (reviewContext, reviewDetailedRating).

    Entries with a numeric rating (``entry[11] = [n]``) are per-aspect ratings
    (Food/Service/Atmosphere); entries with a chosen answer are context
    (e.g. ``Order type: Take out``).
    """
    context: dict[str, Any] = {}
    detailed: dict[str, Any] = {}
    block = dig(r, 30)
    if not isinstance(block, list):
        return context, detailed
    for entry in block:
        label = _dig_str(entry, 5) or _dig_str(entry, 1)
        if not label:
            continue
        rating = _dig_num(entry, 11, 0)
        if rating is not None:
            detailed[label] = rating
            continue
        answer = _dig_str(entry, 2, 0, 0, 1)
        if answer:
            context[label] = answer
    return context, detailed


def parse_review(r: Any) -> dict[str, Any] | None:
    """Map one BOQ review array to ReviewFields-shaped fields.

    Returns ``None`` for malformed entries (no author block).
    """
    if not isinstance(r, list):
        return None
    name = _dig_str(r, 3, 0)
    if not name:
        return None

    reviewer_url = _dig_str(r, 3, 2)
    reviewer_id = None
    if reviewer_url:
        m = _CONTRIB_ID_RE.search(reviewer_url)
        reviewer_id = m.group(1) if m else None

    n_reviews = _dig_num(r, 3, 3)
    local_guide = _dig_num(r, 3, 5, 1)
    text = _dig_str(r, 27)
    translated = _dig_str(r, 28)
    context, detailed = _guided_answers(r)

    fields: dict[str, Any] = {
        "reviewId": _dig_str(r, 5),
        "reviewUrl": _dig_str(r, 12),
        "name": name,
        "reviewerId": reviewer_id,
        "reviewerUrl": reviewer_url,
        "reviewerPhotoUrl": _dig_str(r, 3, 1),
        "reviewerNumberOfReviews": int(n_reviews) if n_reviews is not None else None,
        "isLocalGuide": bool(local_guide) if local_guide is not None else None,
        "stars": _dig_num(r, 1),
        "text": text,
        "textTranslated": translated if translated and translated != text else None,
        "publishAt": _dig_str(r, 2, 0),
        "publishedAtDate": _ms_to_iso(dig(r, 2, 2)),
        "originalLanguage": _dig_str(r, 26),
        "reviewOrigin": _dig_str(r, 44, 0),
        "reviewImageUrls": _review_images(r),
        "reviewContext": context or None,
        "reviewDetailedRating": detailed or None,
    }

    # Owner response (r[4]); only a relative date is exposed here.
    reply_text = _dig_str(r, 4, 2)
    if reply_text:
        fields["responseFromOwnerText"] = reply_text
        fields["responseFromOwnerDate"] = _dig_str(r, 4, 1)

    return {k: v for k, v in fields.items() if v not in (None, [])}


def parse_reviews_page(reviews: Any) -> list[dict[str, Any]]:
    """Parse one BOQ page's raw review list into ReviewFields dicts."""
    if not isinstance(reviews, list):
        return []
    out = []
    for entry in reviews:
        parsed = parse_review(entry)
        if parsed:
            out.append(parsed)
    return out


def strip_personal_data(review: dict[str, Any]) -> dict[str, Any]:
    """Drop reviewer identity fields (Apify ``personalData=false``).

    ``reviewId`` and the review content stay; name/id/url/photo are removed.
    """
    for key in ("name", "reviewerId", "reviewerUrl", "reviewerPhotoUrl"):
        review.pop(key, None)
    return review
