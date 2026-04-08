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


def create_create_calendar_event_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def create_calendar_event(
        summary: str,
        start_datetime: str,
        end_datetime: str,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new event on Google Calendar.

        Use when the user asks to schedule, create, or add a calendar event.
        Ask for event details if not provided.

        Args:
            summary: The event title.
            start_datetime: Start time in ISO 8601 format (e.g. "2026-03-20T10:00:00").
            end_datetime: End time in ISO 8601 format (e.g. "2026-03-20T11:00:00").
            description: Optional event description.
            location: Optional event location.
            attendees: Optional list of attendee email addresses.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "auth_error", or "error"
            - event_id: Google Calendar event ID (if success)
            - html_link: URL to open the event (if success)
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined the action.
              Respond with a brief acknowledgment and do NOT retry or suggest alternatives.

        Examples:
            - "Schedule a meeting with John tomorrow at 10am"
            - "Create a calendar event for the team standup"
        """
        logger.info(
            f"create_calendar_event called: summary='{summary}', start='{start_datetime}', end='{end_datetime}'"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Google Calendar tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = GoogleCalendarToolMetadataService(db_session)
            context = await metadata_service.get_creation_context(
                search_space_id, user_id
            )

            if "error" in context:
                logger.error(f"Failed to fetch creation context: {context['error']}")
                return {"status": "error", "message": context["error"]}

            accounts = context.get("accounts", [])
            if accounts and all(a.get("auth_expired") for a in accounts):
                logger.warning(
                    "All Google Calendar accounts have expired authentication"
                )
                return {
                    "status": "auth_error",
                    "message": "All connected Google Calendar accounts need re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "google_calendar",
                }

            logger.info(
                f"Requesting approval for creating calendar event: summary='{summary}'"
            )
            approval = interrupt(
                {
                    "type": "google_calendar_event_creation",
                    "action": {
                        "tool": "create_calendar_event",
                        "params": {
                            "summary": summary,
                            "start_datetime": start_datetime,
                            "end_datetime": end_datetime,
                            "description": description,
                            "location": location,
                            "attendees": attendees,
                            "timezone": context.get("timezone"),
                            "connector_id": None,
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
                    "message": "User declined. The event was not created. Do not ask again or suggest alternatives.",
                }

            final_params: dict[str, Any] = {}
            edited_action = decision.get("edited_action")
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_summary = final_params.get("summary", summary)
            final_start_datetime = final_params.get("start_datetime", start_datetime)
            final_end_datetime = final_params.get("end_datetime", end_datetime)
            final_description = final_params.get("description", description)
            final_location = final_params.get("location", location)
            final_attendees = final_params.get("attendees", attendees)
            final_connector_id = final_params.get("connector_id")

            if not final_summary or not final_summary.strip():
                return {"status": "error", "message": "Event summary cannot be empty."}

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            _calendar_types = [
                SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
            ]

            if final_connector_id is not None:
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
            else:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type.in_(_calendar_types),
                    )
                )
                connector = result.scalars().first()
                if not connector:
                    return {
                        "status": "error",
                        "message": "No Google Calendar connector found. Please connect Google Calendar in your workspace settings.",
                    }
                actual_connector_id = connector.id

            logger.info(
                f"Creating calendar event: summary='{final_summary}', connector={actual_connector_id}"
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

            tz = context.get("timezone", "UTC")
            event_body: dict[str, Any] = {
                "summary": final_summary,
                "start": {"dateTime": final_start_datetime, "timeZone": tz},
                "end": {"dateTime": final_end_datetime, "timeZone": tz},
            }
            if final_description:
                event_body["description"] = final_description
            if final_location:
                event_body["location"] = final_location
            if final_attendees:
                event_body["attendees"] = [
                    {"email": e.strip()} for e in final_attendees if e.strip()
                ]

            try:
                created = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: (
                        service.events()
                        .insert(calendarId="primary", body=event_body)
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

            logger.info(
                f"Calendar event created: id={created.get('id')}, summary={created.get('summary')}"
            )

            kb_message_suffix = ""
            try:
                from app.services.google_calendar import GoogleCalendarKBSyncService

                kb_service = GoogleCalendarKBSyncService(db_session)
                kb_result = await kb_service.sync_after_create(
                    event_id=created.get("id"),
                    event_summary=final_summary,
                    calendar_id="primary",
                    start_time=final_start_datetime,
                    end_time=final_end_datetime,
                    location=final_location,
                    html_link=created.get("htmlLink"),
                    description=final_description,
                    connector_id=actual_connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                )
                if kb_result["status"] == "success":
                    kb_message_suffix = " Your knowledge base has also been updated."
                else:
                    kb_message_suffix = " This event will be added to your knowledge base in the next scheduled sync."
            except Exception as kb_err:
                logger.warning(f"KB sync after create failed: {kb_err}")
                kb_message_suffix = " This event will be added to your knowledge base in the next scheduled sync."

            return {
                "status": "success",
                "event_id": created.get("id"),
                "html_link": created.get("htmlLink"),
                "message": f"Successfully created '{final_summary}' on Google Calendar.{kb_message_suffix}",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error creating calendar event: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while creating the event. Please try again.",
            }

    return create_calendar_event
