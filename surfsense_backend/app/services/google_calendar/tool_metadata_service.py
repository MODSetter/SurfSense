import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)
from app.services.composio_service import ComposioService

logger = logging.getLogger(__name__)

CALENDAR_CONNECTOR_TYPES = [
    SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
]

CALENDAR_DOCUMENT_TYPES = [
    DocumentType.GOOGLE_CALENDAR_CONNECTOR,
    DocumentType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
]


@dataclass
class GoogleCalendarAccount:
    id: int
    name: str

    @classmethod
    def from_connector(
        cls, connector: SearchSourceConnector
    ) -> "GoogleCalendarAccount":
        return cls(id=connector.id, name=connector.name)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}


@dataclass
class GoogleCalendarEvent:
    event_id: str
    summary: str
    start: str
    end: str
    description: str
    location: str
    attendees: list
    calendar_id: str
    document_id: int
    indexed_at: str | None

    @classmethod
    def from_document(cls, document: Document) -> "GoogleCalendarEvent":
        meta = document.document_metadata or {}
        return cls(
            event_id=meta.get("event_id", ""),
            summary=meta.get("event_summary", document.title),
            start=meta.get("start_time", ""),
            end=meta.get("end_time", ""),
            description=meta.get("description", ""),
            location=meta.get("location", ""),
            attendees=meta.get("attendees", []),
            calendar_id=meta.get("calendar_id", "primary"),
            document_id=document.id,
            indexed_at=meta.get("indexed_at"),
        )

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "summary": self.summary,
            "start": self.start,
            "end": self.end,
            "description": self.description,
            "location": self.location,
            "attendees": self.attendees,
            "calendar_id": self.calendar_id,
            "document_id": self.document_id,
            "indexed_at": self.indexed_at,
        }


class GoogleCalendarToolMetadataService:
    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    def _is_composio_connector(self, connector: SearchSourceConnector) -> bool:
        return (
            connector.connector_type
            == SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
        )

    def _get_composio_connected_account_id(
        self, connector: SearchSourceConnector
    ) -> str:
        cca_id = connector.config.get("composio_connected_account_id")
        if not cca_id:
            raise ValueError("Composio connected_account_id not found")
        return cca_id

    async def _execute_composio_calendar_tool(
        self,
        connector: SearchSourceConnector,
        tool_name: str,
        params: dict,
    ) -> tuple[dict | list | None, str | None]:
        service = ComposioService()
        result = await service.execute_tool(
            connected_account_id=self._get_composio_connected_account_id(connector),
            tool_name=tool_name,
            params=params,
            entity_id=f"surfsense_{connector.user_id}",
        )
        if not result.get("success"):
            return None, result.get("error", "Unknown Composio Calendar error")

        data = result.get("data")
        if isinstance(data, dict):
            inner = data.get("data", data)
            if isinstance(inner, dict):
                return inner.get("response_data", inner), None
            return inner, None
        return data, None

    async def _build_credentials(self, connector: SearchSourceConnector) -> Credentials:
        if self._is_composio_connector(connector):
            raise ValueError(
                "Composio Calendar connectors must use Composio tool execution"
            )

        config_data = dict(connector.config)

        from app.config import config as app_config
        from app.utils.oauth_security import TokenEncryption

        token_encrypted = config_data.get("_token_encrypted", False)
        if token_encrypted and app_config.SECRET_KEY:
            token_encryption = TokenEncryption(app_config.SECRET_KEY)
            if config_data.get("token"):
                config_data["token"] = token_encryption.decrypt_token(
                    config_data["token"]
                )
            if config_data.get("refresh_token"):
                config_data["refresh_token"] = token_encryption.decrypt_token(
                    config_data["refresh_token"]
                )
            if config_data.get("client_secret"):
                config_data["client_secret"] = token_encryption.decrypt_token(
                    config_data["client_secret"]
                )

        exp = config_data.get("expiry", "")
        if exp:
            exp = exp.replace("Z", "")

        return Credentials(
            token=config_data.get("token"),
            refresh_token=config_data.get("refresh_token"),
            token_uri=config_data.get("token_uri"),
            client_id=config_data.get("client_id"),
            client_secret=config_data.get("client_secret"),
            scopes=config_data.get("scopes", []),
            expiry=datetime.fromisoformat(exp) if exp else None,
        )

    async def _check_account_health(self, connector_id: int) -> bool:
        """Check if a Google Calendar connector's credentials are still valid.

        Uses a lightweight calendarList.list(maxResults=1) call to verify access.

        Returns True if the credentials are expired/invalid, False if healthy.
        """
        try:
            result = await self._db_session.execute(
                select(SearchSourceConnector).where(
                    SearchSourceConnector.id == connector_id
                )
            )
            connector = result.scalar_one_or_none()
            if not connector:
                return True

            if self._is_composio_connector(connector):
                _data, error = await self._execute_composio_calendar_tool(
                    connector,
                    "GOOGLECALENDAR_GET_CALENDAR",
                    {"calendar_id": "primary"},
                )
                return bool(error)

            creds = await self._build_credentials(connector)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: (
                    build("calendar", "v3", credentials=creds)
                    .calendarList()
                    .list(maxResults=1)
                    .execute()
                ),
            )
            return False
        except Exception as e:
            logger.warning(
                "Google Calendar connector %s health check failed: %s",
                connector_id,
                e,
            )
            return True

    async def _persist_auth_expired(self, connector_id: int) -> None:
        """Persist ``auth_expired: True`` to the connector config if not already set."""
        try:
            result = await self._db_session.execute(
                select(SearchSourceConnector).where(
                    SearchSourceConnector.id == connector_id
                )
            )
            db_connector = result.scalar_one_or_none()
            if db_connector and not db_connector.config.get("auth_expired"):
                db_connector.config = {**db_connector.config, "auth_expired": True}
                flag_modified(db_connector, "config")
                await self._db_session.commit()
                await self._db_session.refresh(db_connector)
        except Exception:
            logger.warning(
                "Failed to persist auth_expired for connector %s",
                connector_id,
                exc_info=True,
            )

    async def _get_accounts(
        self, search_space_id: int, user_id: str
    ) -> list[GoogleCalendarAccount]:
        result = await self._db_session.execute(
            select(SearchSourceConnector)
            .filter(
                and_(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type.in_(CALENDAR_CONNECTOR_TYPES),
                )
            )
            .order_by(SearchSourceConnector.last_indexed_at.desc())
        )
        connectors = result.scalars().all()
        return [GoogleCalendarAccount.from_connector(c) for c in connectors]

    async def get_creation_context(self, search_space_id: int, user_id: str) -> dict:
        accounts = await self._get_accounts(search_space_id, user_id)

        if not accounts:
            return {
                "accounts": [],
                "error": "No Google Calendar account connected",
            }

        accounts_with_status = []
        for acc in accounts:
            acc_dict = acc.to_dict()
            auth_expired = await self._check_account_health(acc.id)
            acc_dict["auth_expired"] = auth_expired
            if auth_expired:
                await self._persist_auth_expired(acc.id)
            accounts_with_status.append(acc_dict)

        healthy_account = next(
            (a for a in accounts_with_status if not a.get("auth_expired")), None
        )
        if not healthy_account:
            return {
                "accounts": accounts_with_status,
                "calendars": [],
                "timezone": "",
                "error": "All connected Google Calendar accounts have expired credentials",
            }

        connector_id = healthy_account["id"]
        result = await self._db_session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalar_one_or_none()

        calendars = []
        timezone_str = ""
        if connector:
            try:
                if self._is_composio_connector(connector):
                    cal_list, cal_error = await self._execute_composio_calendar_tool(
                        connector, "GOOGLECALENDAR_LIST_CALENDARS", {}
                    )
                    if cal_error:
                        raise RuntimeError(cal_error)
                    (
                        settings,
                        settings_error,
                    ) = await self._execute_composio_calendar_tool(
                        connector,
                        "GOOGLECALENDAR_SETTINGS_GET",
                        {"setting": "timezone"},
                    )
                    if not settings_error and isinstance(settings, dict):
                        timezone_str = settings.get("value", "")
                else:
                    creds = await self._build_credentials(connector)
                    loop = asyncio.get_event_loop()
                    service = await loop.run_in_executor(
                        None, lambda: build("calendar", "v3", credentials=creds)
                    )

                    cal_list = await loop.run_in_executor(
                        None, lambda: service.calendarList().list().execute()
                    )

                    tz_setting = await loop.run_in_executor(
                        None,
                        lambda: service.settings().get(setting="timezone").execute(),
                    )
                    timezone_str = tz_setting.get("value", "")

                calendar_items = []
                if isinstance(cal_list, dict):
                    calendar_items = (
                        cal_list.get("items") or cal_list.get("calendars") or []
                    )
                elif isinstance(cal_list, list):
                    calendar_items = cal_list

                for cal in calendar_items:
                    calendars.append(
                        {
                            "id": cal.get("id", ""),
                            "summary": cal.get("summary", ""),
                            "primary": cal.get("primary", False),
                        }
                    )
            except Exception:
                logger.warning(
                    "Failed to fetch calendars/timezone for connector %s",
                    connector_id,
                    exc_info=True,
                )

        return {
            "accounts": accounts_with_status,
            "calendars": calendars,
            "timezone": timezone_str,
        }

    async def get_update_context(
        self, search_space_id: int, user_id: str, event_ref: str
    ) -> dict:
        resolved = await self._resolve_event(search_space_id, user_id, event_ref)
        if not resolved:
            return {
                "error": (
                    f"Event '{event_ref}' not found in your indexed Google Calendar events. "
                    "This could mean: (1) the event doesn't exist, (2) it hasn't been indexed yet, "
                    "or (3) the event name is different."
                )
            }

        document, connector = resolved
        account = GoogleCalendarAccount.from_connector(connector)
        event = GoogleCalendarEvent.from_document(document)

        acc_dict = account.to_dict()
        auth_expired = await self._check_account_health(connector.id)
        acc_dict["auth_expired"] = auth_expired
        if auth_expired:
            await self._persist_auth_expired(connector.id)
            return {
                "error": "Google Calendar credentials have expired. Please re-authenticate.",
                "auth_expired": True,
                "connector_id": connector.id,
            }

        event_dict = event.to_dict()
        try:
            calendar_id = event.calendar_id or "primary"
            if self._is_composio_connector(connector):
                live_event, error = await self._execute_composio_calendar_tool(
                    connector,
                    "GOOGLECALENDAR_EVENTS_GET",
                    {"calendar_id": calendar_id, "event_id": event.event_id},
                )
                if error:
                    raise RuntimeError(error)
            else:
                creds = await self._build_credentials(connector)
                loop = asyncio.get_event_loop()
                service = await loop.run_in_executor(
                    None, lambda: build("calendar", "v3", credentials=creds)
                )
                live_event = await loop.run_in_executor(
                    None,
                    lambda: (
                        service.events()
                        .get(calendarId=calendar_id, eventId=event.event_id)
                        .execute()
                    ),
                )

            event_dict["summary"] = live_event.get("summary", event_dict["summary"])
            event_dict["description"] = live_event.get(
                "description", event_dict["description"]
            )
            event_dict["location"] = live_event.get("location", event_dict["location"])

            start_data = live_event.get("start", {})
            event_dict["start"] = start_data.get(
                "dateTime", start_data.get("date", event_dict["start"])
            )

            end_data = live_event.get("end", {})
            event_dict["end"] = end_data.get(
                "dateTime", end_data.get("date", event_dict["end"])
            )

            event_dict["attendees"] = [
                {
                    "email": a.get("email", ""),
                    "responseStatus": a.get("responseStatus", ""),
                }
                for a in live_event.get("attendees", [])
            ]
        except Exception:
            logger.warning(
                "Failed to fetch live event data for event %s, using KB metadata",
                event.event_id,
                exc_info=True,
            )

        return {
            "account": acc_dict,
            "event": event_dict,
        }

    async def get_deletion_context(
        self, search_space_id: int, user_id: str, event_ref: str
    ) -> dict:
        resolved = await self._resolve_event(search_space_id, user_id, event_ref)
        if not resolved:
            live_resolved = await self._resolve_live_event(
                search_space_id, user_id, event_ref
            )
            if not live_resolved:
                return {
                    "error": (
                        f"Event '{event_ref}' not found in your indexed or live Google Calendar events. "
                        "This could mean: (1) the event doesn't exist, "
                        "(2) the event name is different, or "
                        "(3) the connected calendar account cannot access it."
                    )
                }

            connector, live_event = live_resolved
            account = GoogleCalendarAccount.from_connector(connector)
            acc_dict = account.to_dict()
            auth_expired = await self._check_account_health(connector.id)
            acc_dict["auth_expired"] = auth_expired
            if auth_expired:
                await self._persist_auth_expired(connector.id)

            return {
                "account": acc_dict,
                "event": self._event_dict_from_live_event(live_event),
            }

        document, connector = resolved
        account = GoogleCalendarAccount.from_connector(connector)
        event = GoogleCalendarEvent.from_document(document)

        acc_dict = account.to_dict()
        auth_expired = await self._check_account_health(connector.id)
        acc_dict["auth_expired"] = auth_expired
        if auth_expired:
            await self._persist_auth_expired(connector.id)

        return {
            "account": acc_dict,
            "event": event.to_dict(),
        }

    async def _resolve_event(
        self, search_space_id: int, user_id: str, event_ref: str
    ) -> tuple[Document, SearchSourceConnector] | None:
        result = await self._db_session.execute(
            select(Document, SearchSourceConnector)
            .join(
                SearchSourceConnector,
                Document.connector_id == SearchSourceConnector.id,
            )
            .filter(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_type.in_(CALENDAR_DOCUMENT_TYPES),
                    SearchSourceConnector.user_id == user_id,
                    or_(
                        func.lower(
                            cast(Document.document_metadata["event_summary"], String)
                        )
                        == func.lower(event_ref),
                        func.lower(Document.title) == func.lower(event_ref),
                    ),
                )
            )
            .order_by(Document.updated_at.desc().nullslast())
            .limit(1)
        )
        row = result.first()
        if row:
            return row[0], row[1]
        return None

    async def _resolve_live_event(
        self, search_space_id: int, user_id: str, event_ref: str
    ) -> tuple[SearchSourceConnector, dict] | None:
        result = await self._db_session.execute(
            select(SearchSourceConnector)
            .filter(
                and_(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type.in_(CALENDAR_CONNECTOR_TYPES),
                )
            )
            .order_by(SearchSourceConnector.last_indexed_at.desc())
        )
        connectors = result.scalars().all()

        for connector in connectors:
            try:
                events = await self._search_live_events(connector, event_ref)
            except Exception:
                logger.warning(
                    "Failed to search live calendar events for connector %s",
                    connector.id,
                    exc_info=True,
                )
                continue

            if not events:
                continue

            normalized_ref = event_ref.strip().lower()
            exact_match = next(
                (
                    event
                    for event in events
                    if event.get("summary", "").strip().lower() == normalized_ref
                ),
                None,
            )
            return connector, exact_match or events[0]

        return None

    async def _search_live_events(
        self, connector: SearchSourceConnector, event_ref: str
    ) -> list[dict]:
        if self._is_composio_connector(connector):
            data, error = await self._execute_composio_calendar_tool(
                connector,
                "GOOGLECALENDAR_EVENTS_LIST",
                {
                    "calendar_id": "primary",
                    "q": event_ref,
                    "max_results": 10,
                    "single_events": True,
                    "order_by": "startTime",
                },
            )
            if error:
                raise RuntimeError(error)
            if isinstance(data, dict):
                return data.get("items") or data.get("events") or []
            return data if isinstance(data, list) else []

        creds = await self._build_credentials(connector)
        loop = asyncio.get_event_loop()
        service = await loop.run_in_executor(
            None, lambda: build("calendar", "v3", credentials=creds)
        )
        response = await loop.run_in_executor(
            None,
            lambda: (
                service.events()
                .list(
                    calendarId="primary",
                    q=event_ref,
                    maxResults=10,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            ),
        )
        return response.get("items", [])

    def _event_dict_from_live_event(self, event: dict) -> dict:
        start_data = event.get("start", {})
        end_data = event.get("end", {})
        return {
            "event_id": event.get("id", ""),
            "summary": event.get("summary", "No Title"),
            "start": start_data.get("dateTime", start_data.get("date", "")),
            "end": end_data.get("dateTime", end_data.get("date", "")),
            "description": event.get("description", ""),
            "location": event.get("location", ""),
            "attendees": [
                {
                    "email": attendee.get("email", ""),
                    "responseStatus": attendee.get("responseStatus", ""),
                }
                for attendee in event.get("attendees", [])
            ],
            "calendar_id": event.get("calendarId", "primary"),
            "document_id": None,
            "indexed_at": None,
        }
