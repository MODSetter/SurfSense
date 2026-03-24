import asyncio
import logging
from datetime import datetime
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.google_calendar import GoogleCalendarToolMetadataService

logger = logging.getLogger(__name__)


def create_delete_calendar_event_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def delete_calendar_event(
        event_title_or_id: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Delete a Google Calendar event.

        Use when the user asks to delete, remove, or cancel a calendar event.

        Args:
            event_title_or_id: The exact title or event ID of the event to delete.
            delete_from_kb: Whether to also remove the event from the knowledge base.
                          Default is False.
                          Set to True to remove from both Google Calendar and knowledge base.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", "auth_error", or "error"
            - event_id: Google Calendar event ID (if success)
            - deleted_from_kb: whether the document was removed from the knowledge base
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined. Respond with a brief
              acknowledgment and do NOT retry or suggest alternatives.
            - If status is "not_found", relay the exact message to the user and ask them
              to verify the event name or check if it has been indexed.
        Examples:
            - "Delete the team standup event"
            - "Cancel my dentist appointment on Friday"
        """
        logger.info(
            f"delete_calendar_event called: event_ref='{event_title_or_id}', delete_from_kb={delete_from_kb}"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Google Calendar tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = GoogleCalendarToolMetadataService(db_session)
            context = await metadata_service.get_deletion_context(
                search_space_id, user_id, event_title_or_id
            )

            if "error" in context:
                error_msg = context["error"]
                if "not found" in error_msg.lower():
                    logger.warning(f"Event not found: {error_msg}")
                    return {"status": "not_found", "message": error_msg}
                logger.error(f"Failed to fetch deletion context: {error_msg}")
                return {"status": "error", "message": error_msg}

            account = context.get("account", {})
            if account.get("auth_expired"):
                logger.warning(
                    "Google Calendar account %s has expired authentication",
                    account.get("id"),
                )
                return {
                    "status": "auth_error",
                    "message": "The Google Calendar account for this event needs re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "google_calendar",
                }

            event = context["event"]
            event_id = event["event_id"]
            document_id = event.get("document_id")
            connector_id_from_context = context["account"]["id"]

            if not event_id:
                return {
                    "status": "error",
                    "message": "Event ID is missing from the indexed document. Please re-index the event and try again.",
                }

            logger.info(
                f"Requesting approval for deleting calendar event: '{event_title_or_id}' (event_id={event_id}, delete_from_kb={delete_from_kb})"
            )
            approval = interrupt(
                {
                    "type": "google_calendar_event_deletion",
                    "action": {
                        "tool": "delete_calendar_event",
                        "params": {
                            "event_id": event_id,
                            "connector_id": connector_id_from_context,
                            "delete_from_kb": delete_from_kb,
                        },
                    },
                    "context": context,
                }
            )

            decisions_raw = (
                approval.get("decisions", []) if isinstance(approval, dict) else []
            )
            decisions = (
                decisions_raw if isinstance(decisions_raw, list) else [decisions_raw]
            )
            decisions = [d for d in decisions if isinstance(d, dict)]
            if not decisions:
                logger.warning("No approval decision received")
                return {"status": "error", "message": "No approval decision received"}

            decision = decisions[0]
            decision_type = decision.get("type") or decision.get("decision_type")
            logger.info(f"User decision: {decision_type}")

            if decision_type == "reject":
                return {
                    "status": "rejected",
                    "message": "User declined. The event was not deleted. Do not ask again or suggest alternatives.",
                }

            edited_action = decision.get("edited_action")
            final_params: dict[str, Any] = {}
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_event_id = final_params.get("event_id", event_id)
            final_connector_id = final_params.get(
                "connector_id", connector_id_from_context
            )
            final_delete_from_kb = final_params.get("delete_from_kb", delete_from_kb)

            if not final_connector_id:
                return {
                    "status": "error",
                    "message": "No connector found for this event.",
                }

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            _calendar_types = [
                SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
            ]

            result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == final_connector_id,
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type.in_(_calendar_types),
                )
            )
            connector = result.scalars().first()
            if not connector:
                return {
                    "status": "error",
                    "message": "Selected Google Calendar connector is invalid or has been disconnected.",
                }

            actual_connector_id = connector.id

            logger.info(
                f"Deleting calendar event: event_id='{final_event_id}', connector={actual_connector_id}"
            )

            if (
                connector.connector_type
                == SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
            ):
                from app.utils.google_credentials import build_composio_credentials

                cca_id = connector.config.get("composio_connected_account_id")
                if cca_id:
                    creds = build_composio_credentials(cca_id)
                else:
                    return {
                        "status": "error",
                        "message": "Composio connected account ID not found for this connector.",
                    }
            else:
                config_data = dict(connector.config)

                from app.config import config as app_config
                from app.utils.oauth_security import TokenEncryption

                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and app_config.SECRET_KEY:
                    token_encryption = TokenEncryption(app_config.SECRET_KEY)
                    for key in ("token", "refresh_token", "client_secret"):
                        if config_data.get(key):
                            config_data[key] = token_encryption.decrypt_token(
                                config_data[key]
                            )

                exp = config_data.get("expiry", "")
                if exp:
                    exp = exp.replace("Z", "")

                creds = Credentials(
                    token=config_data.get("token"),
                    refresh_token=config_data.get("refresh_token"),
                    token_uri=config_data.get("token_uri"),
                    client_id=config_data.get("client_id"),
                    client_secret=config_data.get("client_secret"),
                    scopes=config_data.get("scopes", []),
                    expiry=datetime.fromisoformat(exp) if exp else None,
                )

            service = await asyncio.get_event_loop().run_in_executor(
                None, lambda: build("calendar", "v3", credentials=creds)
            )

            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: (
                        service.events()
                        .delete(calendarId="primary", eventId=final_event_id)
                        .execute()
                    ),
                )
            except Exception as api_err:
                from googleapiclient.errors import HttpError

                if isinstance(api_err, HttpError) and api_err.resp.status == 403:
                    logger.warning(
                        f"Insufficient permissions for connector {actual_connector_id}: {api_err}"
                    )
                    try:
                        from sqlalchemy.orm.attributes import flag_modified

                        _res = await db_session.execute(
                            select(SearchSourceConnector).where(
                                SearchSourceConnector.id == actual_connector_id
                            )
                        )
                        _conn = _res.scalar_one_or_none()
                        if _conn and not _conn.config.get("auth_expired"):
                            _conn.config = {**_conn.config, "auth_expired": True}
                            flag_modified(_conn, "config")
                            await db_session.commit()
                    except Exception:
                        logger.warning(
                            "Failed to persist auth_expired for connector %s",
                            actual_connector_id,
                            exc_info=True,
                        )
                    return {
                        "status": "insufficient_permissions",
                        "connector_id": actual_connector_id,
                        "message": "This Google Calendar account needs additional permissions. Please re-authenticate in connector settings.",
                    }
                raise

            logger.info(f"Calendar event deleted: event_id={final_event_id}")

            delete_result: dict[str, Any] = {
                "status": "success",
                "event_id": final_event_id,
                "message": f"Successfully deleted the calendar event '{event.get('summary', event_title_or_id)}'.",
            }

            deleted_from_kb = False
            if final_delete_from_kb and document_id:
                try:
                    from app.db import Document

                    doc_result = await db_session.execute(
                        select(Document).filter(Document.id == document_id)
                    )
                    document = doc_result.scalars().first()
                    if document:
                        await db_session.delete(document)
                        await db_session.commit()
                        deleted_from_kb = True
                        logger.info(
                            f"Deleted document {document_id} from knowledge base"
                        )
                    else:
                        logger.warning(f"Document {document_id} not found in KB")
                except Exception as e:
                    logger.error(f"Failed to delete document from KB: {e}")
                    await db_session.rollback()
                    delete_result["warning"] = (
                        f"Event deleted, but failed to remove from knowledge base: {e!s}"
                    )

            delete_result["deleted_from_kb"] = deleted_from_kb
            if deleted_from_kb:
                delete_result["message"] = (
                    f"{delete_result.get('message', '')} (also removed from knowledge base)"
                )

            return delete_result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error deleting calendar event: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while deleting the event. Please try again.",
            }

    return delete_calendar_event
