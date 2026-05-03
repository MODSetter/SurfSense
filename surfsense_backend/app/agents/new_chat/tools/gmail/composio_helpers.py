from typing import Any

from app.db import SearchSourceConnector
from app.services.composio_service import ComposioService


def split_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    return [recipient.strip() for recipient in value.split(",") if recipient.strip()]


def unwrap_composio_data(data: Any) -> Any:
    if isinstance(data, dict):
        inner = data.get("data", data)
        if isinstance(inner, dict):
            return inner.get("response_data", inner)
        return inner
    return data


async def execute_composio_gmail_tool(
    connector: SearchSourceConnector,
    user_id: str,
    tool_name: str,
    params: dict[str, Any],
) -> tuple[Any, str | None]:
    cca_id = connector.config.get("composio_connected_account_id")
    if not cca_id:
        return None, "Composio connected account ID not found for this Gmail connector."

    result = await ComposioService().execute_tool(
        connected_account_id=cca_id,
        tool_name=tool_name,
        params=params,
        entity_id=f"surfsense_{user_id}",
    )
    if not result.get("success"):
        return None, result.get("error", "Unknown Composio Gmail error")

    return unwrap_composio_data(result.get("data")), None
