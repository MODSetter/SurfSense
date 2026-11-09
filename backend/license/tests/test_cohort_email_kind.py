"""Telling a business address from a free mailbox or a school, by its domain alone."""

from __future__ import annotations

import pytest

from license.cohorts.email_kind import email_kind

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("address", "kind"),
    [
        ("ana@gmail.com", "free_mail"),
        ("ana@hotmail.co.uk", "free_mail"),
        ("ana@yahoo.co.in", "free_mail"),
        ("ana@gmx.de", "free_mail"),
        ("ana@outlook.com.br", "free_mail"),
        ("ana@proton.me", "free_mail"),
        ("ana@qq.com", "free_mail"),
        ("ana@mit.edu", "education"),
        ("ana@cs.stanford.edu", "education"),
        ("ana@ox.ac.uk", "education"),
        ("ana@unimelb.edu.au", "education"),
        ("ana@acme.com", "company"),
        ("ana@acme.co.uk", "company"),
        # A company host that merely starts with a mail brand's name.
        ("ana@live.acme-corp.com", "company"),
        ("ana@outlookgroup.com", "company"),
        ("not-an-address", "unknown"),
        ("ana@localhost", "unknown"),
    ],
)
def test_each_address_gets_the_kind_its_domain_suggests(address, kind):
    assert email_kind(address) == kind
