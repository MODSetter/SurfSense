"""Whether an address looks like a company, a free mailbox or a school.

A static rule, so it errs: a university on a plain domain reads as a company,
and so does a regional free-mail provider missing from the list.
"""

from __future__ import annotations

from typing import Literal

EmailKind = Literal["company", "free_mail", "education", "unknown"]

FREE_MAIL_DOMAINS = frozenset(
    {
        "126.com",
        "163.com",
        "aliyun.com",
        "att.net",
        "bk.ru",
        "btinternet.com",
        "comcast.net",
        "daum.net",
        "duck.com",
        "fastmail.com",
        "foxmail.com",
        "free.fr",
        "hanmail.net",
        "hey.com",
        "icloud.com",
        "inbox.ru",
        "interia.pl",
        "kakao.com",
        "laposte.net",
        "libero.it",
        "list.ru",
        "mac.com",
        "mail.com",
        "mail.ru",
        "mailbox.org",
        "me.com",
        "naver.com",
        "o2.pl",
        "onet.pl",
        "orange.fr",
        "pm.me",
        "posteo.de",
        "proton.me",
        "qq.com",
        "rambler.ru",
        "sbcglobal.net",
        "seznam.cz",
        "sina.com",
        "t-online.de",
        "tuta.io",
        "tutanota.com",
        "ukr.net",
        "verizon.net",
        "web.de",
        "wp.pl",
        "zoho.com",
        "zohomail.com",
    }
)

# Providers that run one brand under many country suffixes: hotmail.co.uk,
# yahoo.co.in, gmx.de.
FREE_MAIL_BRANDS = frozenset(
    {
        "aol",
        "gmail",
        "gmx",
        "googlemail",
        "hotmail",
        "live",
        "msn",
        "outlook",
        "protonmail",
        "rediffmail",
        "yahoo",
        "yandex",
        "ymail",
    }
)

# Second-level labels schools sit under: mit.edu, ox.ac.uk, unimelb.edu.au.
_EDUCATION_LABELS = frozenset({"edu", "ac", "k12"})
# Longest label of a public suffix such as com, co.uk or com.br, so that
# live.example.com is not mistaken for Microsoft's live.com.
_SUFFIX_LABEL_MAX = 3


def email_kind(address: str) -> EmailKind:
    _, at, domain = address.strip().lower().rpartition("@")
    if not at or "." not in domain:
        return "unknown"
    if domain in FREE_MAIL_DOMAINS or _is_brand_domain(domain):
        return "free_mail"
    if _EDUCATION_LABELS & set(domain.split(".")[1:]):
        return "education"
    return "company"


def _is_brand_domain(domain: str) -> bool:
    brand, _, suffix = domain.partition(".")
    return brand in FREE_MAIL_BRANDS and all(
        0 < len(label) <= _SUFFIX_LABEL_MAX for label in suffix.split(".")
    )
