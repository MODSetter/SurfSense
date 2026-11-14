"""The Keygen setup for Business: idempotent, never strict, and the live policies only read.

Keygen is faked at its transport as an account holding the three live
policies on one product.
"""

from __future__ import annotations

import json
from collections import defaultdict
from contextlib import asynccontextmanager

import httpx2
import pytest

from license import keygen
from license.jobs import JOBS
from license.scripts.setup_business_policies import SetupError, setup
from license.settings import config

pytestmark = pytest.mark.unit

LIVE = ("pol-trial", "pol-individual", "pol-team")


def _policy(policy_id: str, product: str, **attributes) -> dict:
    return {
        "id": policy_id,
        "type": "policies",
        "attributes": {"strict": False, "scheme": None, "metadata": {}, **attributes},
        "relationships": {"product": {"data": {"type": "products", "id": product}}},
    }


class FakeAccount:
    """Policies, entitlements and product tokens, as Keygen CE answers them."""

    def __init__(self) -> None:
        self.policies = {
            "pol-trial": _policy("pol-trial", "prod-1", name="Trial"),
            "pol-individual": _policy(
                "pol-individual", "prod-1", name="Individual", scheme="ED25519_SIGN"
            ),
            "pol-team": _policy("pol-team", "prod-1", name="Team"),
        }
        self.entitlements: dict[str, dict] = {}
        self.attached: dict[str, set[str]] = defaultdict(set)
        self.requests: list[httpx2.Request] = []
        self.admin = True

    def writes(self) -> list[tuple[str, str]]:
        return [
            (request.method, request.url.path.split("/acct/", 1)[1])
            for request in self.requests
            if request.method != "GET"
        ]

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        path = request.url.path.split("/acct/", 1)[1].strip("/")
        parts = path.split("/")
        body = json.loads(request.content) if request.content else {}
        if parts == ["policies"] and request.method == "GET":
            product = request.url.params.get("product")
            return _list(
                p for p in self.policies.values() if _product(p) in (product, None)
            )
        if parts == ["policies"] and request.method == "POST":
            data = body["data"]
            policy_id = f"pol-new-{len(self.policies)}"
            self.policies[policy_id] = {
                "id": policy_id,
                "type": "policies",
                "attributes": data["attributes"],
                "relationships": data["relationships"],
            }
            return httpx2.Response(201, json={"data": self.policies[policy_id]})
        if parts[0] == "policies" and len(parts) == 2:
            found = self.policies.get(parts[1])
            return (
                httpx2.Response(200, json={"data": found})
                if found
                else httpx2.Response(404)
            )
        if parts[0] == "policies" and parts[2:] == ["entitlements"]:
            if request.method == "GET":
                return _list(self.entitlements[e] for e in self.attached[parts[1]])
            for item in body["data"]:
                if item["id"] in self.attached[parts[1]]:
                    return httpx2.Response(422)
                self.attached[parts[1]].add(item["id"])
            return httpx2.Response(200, json={"data": []})
        if parts == ["entitlements"] and request.method == "GET":
            return _list(self.entitlements.values())
        if parts == ["entitlements"] and request.method == "POST":
            if not self.admin:
                return httpx2.Response(403)
            entitlement_id = f"ent-{len(self.entitlements) + 1}"
            self.entitlements[entitlement_id] = {
                "id": entitlement_id,
                "attributes": body["data"]["attributes"],
            }
            return httpx2.Response(
                201, json={"data": self.entitlements[entitlement_id]}
            )
        if parts[0] == "products" and parts[2:] == ["tokens"]:
            return httpx2.Response(
                200, json={"data": {"attributes": {"token": "prod-token-secret"}}}
            )
        return httpx2.Response(404)


def _product(policy: dict) -> str:
    return policy["relationships"]["product"]["data"]["id"]


def _list(items) -> httpx2.Response:
    return httpx2.Response(200, json={"data": list(items), "links": {"next": None}})


@pytest.fixture
def account(monkeypatch: pytest.MonkeyPatch) -> FakeAccount:
    fake = FakeAccount()

    @asynccontextmanager
    async def http(client=None):
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(fake.handle)
        ) as session:
            yield session

    monkeypatch.setattr(keygen, "_http", http)
    for name, value in {
        "KEYGEN_ACCOUNT_ID": "acct",
        "KEYGEN_API_TOKEN": "admin-token",
        "KEYGEN_API_URL": "",
        "KEYGEN_HOST": "",
        "KEYGEN_POLICY_TRIAL": "pol-trial",
        "KEYGEN_POLICY_INDIVIDUAL": "pol-individual",
        "KEYGEN_POLICY_TEAM": "pol-team",
    }.items():
        monkeypatch.setattr(config, name, value)
    return fake


def business_policies(account: FakeAccount) -> dict[str, dict]:
    return {
        policy["attributes"]["metadata"]["surfsensePolicy"]: policy
        for policy in account.policies.values()
        if "surfsensePolicy" in policy["attributes"]["metadata"]
    }


async def test_a_first_run_creates_both_policies_and_every_job_on_each(
    account: FakeAccount,
) -> None:
    lines = await setup()

    ours = business_policies(account)
    assert set(ours) == {"business", "business-trial"}
    created = {
        entitlement["attributes"]["code"]: entitlement["attributes"]["name"]
        for entitlement in account.entitlements.values()
    }
    assert created == JOBS
    for policy in ours.values():
        assert account.attached[policy["id"]] == set(account.entitlements)
    assert lines == [
        f"KEYGEN_POLICY_BUSINESS={ours['business']['id']}",
        f"KEYGEN_POLICY_BUSINESS_TRIAL={ours['business-trial']['id']}",
    ]


async def test_the_business_policies_are_never_strict_and_join_the_live_product(
    account: FakeAccount,
) -> None:
    """The plugin host accepts only VALID, and a strict policy answers NO_MACHINE."""
    await setup()

    for plan, policy in business_policies(account).items():
        attributes = policy["attributes"]
        assert attributes["strict"] is False, plan
        assert attributes["floating"] is True
        assert attributes["maxMachines"] is None
        # The live policies' scheme, so the files carry the `alg` the app accepts.
        assert attributes["scheme"] == "ED25519_SIGN"
        assert _product(policy) == "prod-1"
    durations = {
        plan: policy["attributes"]["duration"]
        for plan, policy in business_policies(account).items()
    }
    assert durations == {"business": 395 * 86400, "business-trial": 14 * 86400}


async def test_a_second_run_creates_nothing(account: FakeAccount) -> None:
    first = await setup()
    writes = len(account.writes())

    second = await setup()

    assert second == first
    assert len(account.writes()) == writes


async def test_a_new_job_is_created_and_attached_on_a_rerun(
    account: FakeAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    await setup()
    sold = set(JOBS)
    monkeypatch.setitem(JOBS, "JOB_RFP", "RFP responses")

    await setup()

    codes = {e["attributes"]["code"] for e in account.entitlements.values()}
    assert codes == sold | {"JOB_RFP"}
    for policy in business_policies(account).values():
        assert len(account.attached[policy["id"]]) == len(sold) + 1


async def test_the_live_policies_are_only_read(account: FakeAccount) -> None:
    await setup(product_token=True)

    touched = {path.split("/")[1] for _, path in account.writes() if "/" in path}
    assert touched.isdisjoint(LIVE)
    assert {policy["attributes"]["strict"] for policy in account.policies.values()} == {
        False
    }


async def test_live_policies_on_two_products_refuse_before_any_write(
    account: FakeAccount,
) -> None:
    """A product token reads one product's licenses; resend would silently find none."""
    account.policies["pol-team"]["relationships"]["product"]["data"]["id"] = "prod-2"

    with pytest.raises(SetupError, match="more than one product"):
        await setup()

    assert account.writes() == []


async def test_an_unset_live_policy_refuses_before_any_call(
    account: FakeAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The team policy unread could be on another product, which the token would miss."""
    monkeypatch.setattr(config, "KEYGEN_POLICY_TEAM", "")

    with pytest.raises(SetupError, match="Set KEYGEN_POLICY_TEAM:"):
        await setup()

    assert account.requests == []


async def test_a_strict_business_policy_is_reported_never_edited(
    account: FakeAccount,
) -> None:
    await setup()
    business = business_policies(account)["business"]
    business["attributes"]["strict"] = True
    writes = len(account.writes())

    with pytest.raises(SetupError, match="strict"):
        await setup()

    assert len(account.writes()) == writes


async def test_a_dry_run_writes_nothing(account: FakeAccount) -> None:
    lines = await setup(dry_run=True)

    assert account.writes() == []
    assert lines == []


async def test_a_product_token_cannot_create_entitlements_and_says_so(
    account: FakeAccount,
) -> None:
    account.admin = False

    with pytest.raises(SetupError, match="admin token"):
        await setup()


async def test_the_product_token_is_made_only_when_asked(account: FakeAccount) -> None:
    without = await setup()
    with_token = await setup(product_token=True)

    assert not any(line.startswith("KEYGEN_API_TOKEN=") for line in without)
    assert with_token[-1] == "KEYGEN_API_TOKEN=prod-token-secret"
    assert ("POST", "products/prod-1/tokens") in account.writes()
