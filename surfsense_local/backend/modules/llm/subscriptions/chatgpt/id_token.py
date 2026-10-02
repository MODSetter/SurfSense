import base64
import json
import time

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from modules.llm.subscriptions.chatgpt.endpoints import get_endpoints

JWKS_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# Clock drift between this machine and OpenAI's.
LEEWAY_SECONDS = 120


class InvalidIdTokenError(Exception):
    pass


async def verified_claims(id_token: str, client_id: str, nonce: str) -> dict:
    """The ID token's claims, once its RS256 signature, issuer, audience,
    expiry and nonce check out; OpenAI's docs ask for all five."""
    try:
        header_b64, claims_b64, signature_b64 = id_token.split(".")
        header = json.loads(_unb64(header_b64))
        claims = json.loads(_unb64(claims_b64))
    except ValueError as error:
        raise InvalidIdTokenError("the ID token is malformed") from error
    if header.get("alg") != "RS256":
        raise InvalidIdTokenError("the ID token is not signed with RS256")
    key = await _signing_key(header.get("kid"))
    try:
        key.verify(
            _unb64(signature_b64),
            f"{header_b64}.{claims_b64}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as error:
        raise InvalidIdTokenError("the ID token's signature does not verify") from error
    _check(claims, client_id, nonce)
    return claims


def _check(claims: dict, client_id: str, nonce: str) -> None:
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if claims.get("iss") != get_endpoints().auth_url:
        raise InvalidIdTokenError("the ID token is from another issuer")
    if client_id not in audiences:
        raise InvalidIdTokenError("the ID token is for another client")
    if not isinstance(claims.get("exp"), (int, float)) or (
        claims["exp"] + LEEWAY_SECONDS < time.time()
    ):
        raise InvalidIdTokenError("the ID token has expired")
    if claims.get("nonce") != nonce:
        raise InvalidIdTokenError("the ID token answers another sign-in")
    if not isinstance(claims.get("sub"), str):
        raise InvalidIdTokenError("the ID token names no account")


async def _signing_key(kid: object) -> rsa.RSAPublicKey:
    async with httpx.AsyncClient(timeout=JWKS_TIMEOUT) as client:
        reply = await client.get(get_endpoints().jwks_url)
        reply.raise_for_status()
        keys = reply.json().get("keys", [])
    for key in keys:
        if key.get("kty") == "RSA" and key.get("kid") == kid:
            return rsa.RSAPublicNumbers(
                int.from_bytes(_unb64(key["e"]), "big"),
                int.from_bytes(_unb64(key["n"]), "big"),
            ).public_key()
    raise InvalidIdTokenError("the ID token's signing key is not published")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
