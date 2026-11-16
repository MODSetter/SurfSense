"""Emails, phones and social profiles from raw HTML: they live in the footer, which extraction drops."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote, urldefrag, urlsplit

from lxml import html as lxml_html
from lxml.etree import ParserError

# Social/profile hosts worth surfacing as leads. Matched on host == d or a
# subdomain of d. ``x.com``/``twitter.com`` both kept (rename churn).
_SOCIAL_HOSTS = (
    "twitter.com",
    "x.com",
    "linkedin.com",
    "facebook.com",
    "fb.com",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "discord.com",
    "discord.gg",
    "t.me",
    "medium.com",
    "threads.net",
    "pinterest.com",
    "reddit.com",
    "crunchbase.com",
    "wellfound.com",
    "angel.co",
    "mastodon.social",
    "bsky.app",
    # Regional networks — the primary business contact channel in much of the
    # world (WhatsApp: LatAm/India/Africa; Line: JP/TH/TW; VK/OK: RU;
    # Weibo/WeChat: CN; Xing: DACH; Kakao: KR).
    "wa.me",
    "whatsapp.com",
    "line.me",
    "lin.ee",
    "vk.com",
    "ok.ru",
    "weibo.com",
    "weixin.qq.com",
    "xing.com",
    "pf.kakao.com",
)

# Code hosts: a profile is ``host/<user-or-org>``. Every issue, pull request
# and file is a deeper path, and a changelog links thousands of them.
_CODE_HOSTS = frozenset({"github.com", "gitlab.com"})
_CODE_HOST_RESERVED = frozenset(
    {
        "features",
        "pricing",
        "about",
        "login",
        "join",
        "signup",
        "explore",
        "topics",
        "marketplace",
        "sponsors",
        "orgs",
        "settings",
        "enterprise",
        "collections",
        "trending",
        "users",
        "groups",
        "help",
        "dashboard",
        "-",
    }
)

# Email domains that are almost never a real contact (SDKs, CDNs, examples).
_NOISE_EMAIL_DOMAINS = frozenset(
    {
        "sentry.io",
        "wixpress.com",
        "example.com",
        "example.org",
        "domain.com",
        "email.com",
        # Unambiguous placeholder domains; ambiguous ones (business.com,
        # company.com) are left to the placeholder local-part filter instead.
        "yourcompany.com",
        "yourdomain.com",
        "yoursite.com",
        "schema.org",
        "w3.org",
        "googleapis.com",
        "gstatic.com",
        "sentry-cdn.com",
        "cloudflare.com",
    }
)

# File extensions that surface as bogus email "TLDs" when an asset ref (``logo@2x.png``)
# or version-pinned dep (``react@18.2.0.js``) matches the email shape.
_ASSET_TLDS = frozenset(
    {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "svg",
        "webp",
        "ico",
        "bmp",
        "css",
        "js",
        "mjs",
        "cjs",
        "ts",
        "map",
        "json",
        "xml",
        "woff",
        "woff2",
        "ttf",
        "eot",
        "otf",
        "php",
        "html",
        "htm",
    }
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# The source can spell an address's "@" and "." as entities (Sphinx writes
# ``localhost&#64;other.com``); a parsed and re-serialised page shows them decoded.
_EMAIL_ENTITIES = re.compile(r"&(?:#64|#x40|commat|#46|#x2e|period);", re.IGNORECASE)
_ENTITY_CHAR = {
    "#64": "@",
    "#x40": "@",
    "commat": "@",
    "#46": ".",
    "#x2e": ".",
    "period": ".",
}


def _decode_email_entities(text: str) -> str:
    return _EMAIL_ENTITIES.sub(lambda m: _ENTITY_CHAR[m.group(0)[1:-1].lower()], text)


# Template/form placeholders, compared after stripping [._-] separators, so
# "your.email"/"your-email"/"youremail" all match. Deliberately excludes real
# common locals like hello/info/contact/support.
_PLACEHOLDER_EMAIL_LOCALS = frozenset(
    {
        "youremail",
        "yourname",
        "youraddress",
        "myemail",
        "email",
        "name",
        "user",
        "username",
        "someone",
        "somebody",
        "johndoe",
        "janedoe",
        "firstname",
        "lastname",
        "firstnamelastname",
        "firstlast",
        "test",
        "example",
        "sample",
        "placeholder",
    }
)

# Placeholder profile handles left in site templates ("github.com/username").
_PLACEHOLDER_SOCIAL_SEGMENTS = frozenset(
    {
        "username",
        "yourusername",
        "yourhandle",
        "handle",
        "user",
        "profile",
        "yourprofile",
        "yourname",
        "yourpage",
        "pagename",
        "youraccount",
        "account",
        "example",
        "placeholder",
        "yourcompany",
    }
)

_SEPARATORS_RE = re.compile(r"[._\-]+")


def _normalized(token: str) -> str:
    return _SEPARATORS_RE.sub("", token.strip().lower().lstrip("@"))


@dataclass
class Contacts:
    """Deduped contact signals harvested from one page's raw HTML."""

    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    socials: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {"emails": self.emails, "phones": self.phones, "socials": self.socials}

    @property
    def is_empty(self) -> bool:
        return not (self.emails or self.phones or self.socials)


def is_social_host(host: str) -> bool:
    """True when ``host`` is (a subdomain of) a known social/profile host."""
    return any(host == d or host.endswith("." + d) for d in _SOCIAL_HOSTS)


def is_social_url(url: str) -> bool:
    """True when ``url`` points at a profile on a known social host.

    On a code host only ``host/<name>`` counts: ``github.com/org/repo/issues/1``
    is a link, not anyone's profile.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in _CODE_HOSTS:
        segments = [segment for segment in parts.path.split("/") if segment]
        return len(segments) == 1 and segments[0].lower() not in _CODE_HOST_RESERVED
    return is_social_host(host)


def _keep_email(email: str) -> bool:
    local, _, domain = email.partition("@")
    domain = domain.lower()
    if domain in _NOISE_EMAIL_DOMAINS:
        return False
    if _normalized(local) in _PLACEHOLDER_EMAIL_LOCALS:
        return False
    # Drops asset/version false positives like ``logo@2x.png`` / ``react@18.2.0.js``
    # whose trailing token is a file extension, not a real TLD.
    return domain.rsplit(".", 1)[-1] not in _ASSET_TLDS


def _keep_social(url: str) -> bool:
    # ponytail: any placeholder-looking path segment drops the URL; a real
    # handle literally named "username"/"example" is collateral. Upgrade path:
    # per-host handle position rules (e.g. linkedin.com/in/<handle>).
    return not any(
        _normalized(segment) in _PLACEHOLDER_SOCIAL_SEGMENTS
        for segment in urlsplit(url).path.split("/")
        if segment
    )


def _dedup(values: list[str]) -> list[str]:
    """Case-insensitive dedupe that preserves first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def extract_contacts(
    raw_html: str | None, root: Any = None, scan_text: str | None = None
) -> Contacts:
    """Harvest emails, phone numbers, and social profile URLs from raw HTML.

    Emails come from ``mailto:`` hrefs (high confidence) and a plaintext scan of
    the source (noise-filtered). Phones come only from ``tel:`` hrefs — a text
    scan for phone numbers is too noisy to be worth it. Socials are ``href``
    targets on known profile hosts. Any parse error yields empty results rather
    than aborting the crawl. ``root``, when given, is ``raw_html`` already
    parsed, so the page is not parsed again. ``scan_text``, when given, is what
    the plaintext scan reads instead: the whole page when ``raw_html`` is a
    capped prefix of it.
    """
    if not raw_html or not raw_html.strip():
        return Contacts()

    emails: list[str] = []
    phones: list[str] = []
    socials: list[str] = []

    if root is None:
        try:
            root = lxml_html.fromstring(raw_html)
        except (ParserError, ValueError):
            root = None

    if root is not None:
        for href in root.xpath("//a/@href | //link/@href"):
            href = str(href).strip()
            low = href.lower()
            # unquote: hrefs URL-encode spaces etc. ("tel:+1%20408-629-1770")
            if low.startswith("mailto:"):
                addr = unquote(urlsplit(href).path.split("?")[0]).strip()
                if addr:
                    emails.append(addr)
            elif low.startswith("tel:"):
                num = unquote(urlsplit(href).path).strip()
                if num:
                    phones.append(num)
            elif low.startswith(("http://", "https://")):
                if is_social_url(href):
                    socials.append(urldefrag(href)[0])

    # Plaintext email scan over the source catches addresses rendered as text
    # (e.g. "hello@site.com" in a footer) that never appear as a mailto href.
    emails.extend(_EMAIL_RE.findall(_decode_email_entities(scan_text or raw_html)))

    return Contacts(
        emails=[e for e in _dedup(emails) if _keep_email(e)],
        phones=_dedup(phones),
        socials=[s for s in _dedup(socials) if _keep_social(s)],
    )
