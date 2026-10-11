"""Keygen's validate-key action, which needs no token: the key is the credential."""

from dataclasses import dataclass

import httpx2

KEYGEN_API_URL = "https://api.keygen.sh"
# SurfSense's Keygen account, the backend's KEYGEN_ACCOUNT_ID. Not a secret: it is
# part of every validation URL.
SURFSENSE_ACCOUNT_ID = ""
TIMEOUT_SECONDS = 10.0


class KeygenUnreachableError(Exception):
    """No answer about the key: a network failure or Keygen's own 5xx."""


@dataclass(frozen=True)
class Keygen:
    api_url: str = KEYGEN_API_URL
    account_id: str = SURFSENSE_ACCOUNT_ID

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("SURFSENSE_ACCOUNT_ID in keygen.py is not set")

    async def validation_code(self, key: str) -> str:
        """Keygen's `meta.code`, such as VALID, EXPIRED or NOT_FOUND."""
        url = (
            f"{self.api_url.rstrip('/')}/v1/accounts/{self.account_id}"
            "/licenses/actions/validate-key"
        )
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }
        try:
            async with httpx2.AsyncClient(timeout=TIMEOUT_SECONDS) as http:
                response = await http.post(
                    url, json={"meta": {"key": key}}, headers=headers
                )
        except httpx2.TransportError as error:
            raise KeygenUnreachableError(str(error)) from error
        if response.status_code >= 500:
            raise KeygenUnreachableError(f"Keygen answered {response.status_code}")
        response.raise_for_status()
        return response.json()["meta"]["code"]
