"""The headers a plugin's server gets for a pasted key: `Authorization: Bearer <key>`."""


def token_headers(token: str | None) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"} if token else {}
