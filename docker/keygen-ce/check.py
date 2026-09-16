#!/usr/bin/env python3
"""Prove a self-hosted Keygen CE instance satisfies contracts 1 and 2.

Issues a real license the way the portal will, checks out a perpetual file, and
verifies it with contract 1's consumer algorithm. Exits non-zero on any failure.

    python check.py [--public-key <64-hex>]

Re-runs create additional products and policies; this is a throwaway stack.
"""
import argparse
import base64
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

HERE = pathlib.Path(__file__).parent


def load_env():
    path = HERE / ".env"
    if not path.exists():
        sys.exit("no .env here -- copy .env.example and fill it in first")
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )


ENV = load_env()
BASE = f"http://127.0.0.1:3000/v1/accounts/{ENV['KEYGEN_ACCOUNT_ID'].strip()}"

# Keygen forces TLS and 308s plain HTTP. It does not terminate TLS itself, but
# Rails honours X-Forwarded-Proto from RFC1918 peers -- so an internal caller
# needs this header rather than a TLS terminator. The backend client must too.
HEADERS = {
    "Host": ENV["KEYGEN_HOST"].strip(),
    "X-Forwarded-Proto": "https",
    "Content-Type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json",
}


def api(method, path, body=None, auth=None):
    headers = dict(HEADERS)
    if auth:
        headers["Authorization"] = auth
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        payload = e.read().decode()
        if e.code in (301, 302, 307, 308):
            sys.exit("redirected -- X-Forwarded-Proto missing? see README trap 3")
        sys.exit(f"{method} {path} -> {e.code}\n{payload}")
    except urllib.error.URLError as e:
        sys.exit(f"cannot reach {BASE} ({e.reason}) -- is `docker compose up -d web worker` done?")


def read_public_key():
    """The account key is console-only; CE does not expose it over the API."""
    try:
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "web", "bundle", "exec", "rails",
             "runner", "puts Account.sole.ed25519_public_key"],
            cwd=HERE, capture_output=True, text=True, timeout=120,
        ).stdout
    except (OSError, subprocess.SubprocessError) as e:
        sys.exit(f"could not read the account key ({e}); pass --public-key instead")
    found = re.findall(r"\b[0-9a-f]{64}\b", out)
    if not found:
        sys.exit(f"no key in rails output; pass --public-key instead\n{out}")
    return found[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public-key", help="64-hex account key, else read via rails")
    args = ap.parse_args()

    basic = base64.b64encode(
        f"{ENV['KEYGEN_ADMIN_EMAIL'].strip()}:{ENV['KEYGEN_ADMIN_PASSWORD'].strip()}".encode()
    ).decode()
    token = api("POST", "/tokens", auth=f"Basic {basic}")["data"]["attributes"]["token"]
    auth = f"Bearer {token}"
    print("1. admin token           OK")

    product = api("POST", "/products", {
        "data": {"type": "products", "attributes": {"name": "SurfSense"}}
    }, auth)["data"]["id"]
    print(f"2. product               OK  {product}")

    policies = {}
    for name, duration in (("trial", 14 * 86400), ("individual", 31536000), ("team", 31536000)):
        policies[name] = api("POST", "/policies", {"data": {
            "type": "policies",
            "attributes": {"name": name, "duration": duration, "requireFingerprintScope": False},
            "relationships": {"product": {"data": {"type": "products", "id": product}}},
        }}, auth)["data"]["id"]
    # The ids, not the names: these are what KEYGEN_POLICY_* must be set to, and
    # re-running to recover them would create a second set of policies.
    print("3. policies              OK")
    for name, policy_id in policies.items():
        print(f"     KEYGEN_POLICY_{name.upper():<12} {policy_id}")

    # The metadata the Stripe webhook writes. It is the only lookup index we get.
    license = api("POST", "/licenses", {"data": {
        "type": "licenses",
        "attributes": {"metadata": {
            "plan": "individual",
            "email": "buyer@example.com",
            "checkoutSessionId": "cs_test_check_py",
        }},
        "relationships": {"policy": {"data": {"type": "policies", "id": policies["individual"]}}},
    }}, auth)["data"]
    print(f"4. license               OK  {license['attributes']['key']}")

    # Contract 1 producer rule 2: the 30-day default TTL would kill every file a
    # month after purchase, so ttl must be null.
    checkout = api("POST", f"/licenses/{license['id']}/actions/check-out",
                   {"meta": {"ttl": None}}, auth)
    certificate = checkout["data"]["attributes"]["certificate"]
    (HERE / "issued.lic").write_text(certificate)
    print(f"5. check-out ttl:null    OK  {len(certificate)} bytes -> issued.lic")

    found = api("GET", "/licenses?limit=10&metadata%5BcheckoutSessionId%5D=cs_test_check_py",
                None, auth)["data"]
    assert any(item["id"] == license["id"] for item in found), "metadata filter missed the license"
    print(f"6. metadata[...] lookup  OK  {len(found)} hit")

    public_key = (args.public_key or read_public_key()).strip()
    verifier = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key))
    print(f"7. account public key    {public_key}")

    # --- contract 1, consumer rules, in order ---
    body = "".join(
        line for line in certificate.splitlines()
        if line and not line.startswith("-----")
    )
    envelope = json.loads(base64.b64decode(body))
    assert envelope["alg"] == "base64+ed25519", envelope["alg"]
    verifier.verify(base64.b64decode(envelope["sig"]),
                    b"license/" + envelope["enc"].encode())
    payload = json.loads(base64.b64decode(envelope["enc"]))
    attributes = payload["data"]["attributes"]
    assert payload["meta"]["expiry"] is None, "meta.expiry set -- the file would expire"
    assert attributes["metadata"]["plan"] == "individual"
    assert attributes["key"] == license["attributes"]["key"]
    print("8. verify                OK  alg, signature, ttl:null, plan, key")

    tampered = envelope["enc"][:-2] + ("AA" if not envelope["enc"].endswith("AA") else "AB")
    try:
        verifier.verify(base64.b64decode(envelope["sig"]), b"license/" + tampered.encode())
    except InvalidSignature:
        print("9. tampered payload      rejected")
    else:
        sys.exit("FAIL: a tampered payload verified")

    # Contract 2's enforcement call. Unauthenticated, as the scraper API makes it.
    def validate(key):
        return api("POST", "/licenses/actions/validate-key", {"meta": {"key": key}})["meta"]

    good = validate(license["attributes"]["key"])
    bad = validate("FFFFFF-000000-000000-000000-000000-V3")
    assert good["valid"] and good["code"] == "VALID", good
    assert not bad["valid"] and bad["code"] == "NOT_FOUND", bad
    print("10. validate-key         OK  VALID / NOT_FOUND, no auth needed")

    print("\nall good. compile this key into "
          "surfsense_local/backend/modules/license/verify.py:\n  " + public_key)
    print("back up the account keypair out of band BEFORE it ships in an installer.")


if __name__ == "__main__":
    main()
