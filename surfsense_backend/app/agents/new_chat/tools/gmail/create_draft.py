import asyncio
import base64
import logging
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.services.gmail import GmailToolMetadataService

logger = logging.getLogger(__name__)


def create_create_gmail_draft_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def create_gmail_draft(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        bcc: str | None = None,
    ) -> dict[str, Any]:
        """Create a draft email in Gmail.

        Use when the user asks to draft, compose, or prepare an email without
        sending it.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Email body content.
            cc: Optional CC recipient(s), comma-separated.
            bcc: Optional BCC recipient(s), comma-separated.

        Returns:
            Dictionary with:
            - status: "success", "rejected", or "error"
            - draft_id: Gmail draft ID (if success)
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined the action.
              Respond with a brief acknowledgment and do NOT retry or suggest alternatives.
            - If status is "insufficient_permissions", the connector lacks the required OAuth scope.
              Inform the user they need to re-authenticate and do NOT retry the action.

        Examples:
            - "Draft an email to alice@example.com about the meeting"
            - "Compose a reply to Bob about the project update"
        """
        logger.info(f"create_gmail_draft called: to='{to}', subject='{subject}'")

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Gmail tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = GmailToolMetadataService(db_session)
            context = await metadata_service.get_creation_context(
                search_space_id, user_id
            )

            if "error" in context:
                logger.error(f"Failed to fetch creation context: {context['error']}")
                return {"status": "error", "message": context["error"]}

            accounts = context.get("accounts", [])
            if accounts and all(a.get("auth_expired") for a in accounts):
                logger.warning("All Gmail accounts have expired authentication")
                return {
                    "status": "auth_error",
                    "message": "All connected Gmail accounts need re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "gmail",
                }

            logger.info(
                f"Requesting approval for creating Gmail draft: to='{to}', subject='{subject}'"
            )
            result = request_approval(
                action_type="gmail_draft_creation",
                tool_name="create_gmail_draft",
                params={
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "cc": cc,
                    "bcc": bcc,
                    "connector_id": None,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. The draft was not created. Do not ask again or suggest alternatives.",
                }

            final_to = result.params.get("to", to)
            final_subject = result.params.get("subject", subject)
            final_body = result.params.get("body", body)
            final_cc = result.params.get("cc", cc)
            final_bcc = result.params.get("bcc", bcc)
            final_connector_id = result.params.get("connector_id")

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            _gmail_types = [
                SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
                SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
            ]

            if final_connector_id is not None:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type.in_(_gmail_types),
                    )
                )
                connector = result.scalars().first()
                if not connector:
                    return {
                        "status": "error",
                        "message": "Selected Gmail connector is invalid or has been disconnected.",
                    }
                actual_connector_id = connector.id
            else:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type.in_(_gmail_types),
                    )
                )
                connector = result.scalars().first()
                if not connector:
                    return {
                        "status": "error",
                        "message": "No Gmail connector found. Please connect Gmail in your workspace settings.",
                    }
                actual_connector_id = connector.id

            logger.info(
                f"Creating Gmail draft: to='{final_to}', subject='{final_subject}', connector={actual_connector_id}"
            )

            is_composio_gmail = (
                connector.connector_type
                == SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR
            )
            if is_composio_gmail:
                cca_id = connector.config.get("composio_connected_account_id")
                if not cca_id:
                    return {
                        "status": "error",
                        "message": "Composio connected account ID not found for this Gmail connector.",
                    }
            else:
                from google.oauth2.credentials import Credentials

                from app.config import config
                from app.utils.oauth_security import TokenEncryption

                config_data = dict(connector.config)
                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and config.SECRET_KEY:
                    token_encryption = TokenEncryption(config.SECRET_KEY)
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

                creds = Credentials(
                    token=config_data.get("token"),
                    refresh_token=config_data.get("refresh_token"),
                    token_uri=config_data.get("token_uri"),
                    client_id=config_data.get("client_id"),
                    client_secret=config_data.get("client_secret"),
                    scopes=config_data.get("scopes", []),
                    expiry=datetime.fromisoformat(exp) if exp else None,
                )

            message = MIMEText(final_body)
            message["to"] = final_to
            message["subject"] = final_subject
            if final_cc:
                message["cc"] = final_cc
            if final_bcc:
                message["bcc"] = final_bcc
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            try:
                if is_composio_gmail:
                    from app.agents.new_chat.tools.gmail.composio_helpers import (
                        execute_composio_gmail_tool,
                        split_recipients,
                    )

                    created, error = await execute_composio_gmail_tool(
                        connector,
                        user_id,
                        "GMAIL_CREATE_EMAIL_DRAFT",
                        {
                            "user_id": "me",
                            "recipient_email": final_to,
                            "subject": final_subject,
                            "body": final_body,
                            "cc": split_recipients(final_cc),
                            "bcc": split_recipients(final_bcc),
                            "is_html": False,
                        },
                    )
                    if error:
                        raise RuntimeError(error)
                    if not isinstance(created, dict):
                        created = {}
                else:
                    from googleapiclient.discovery import build

                    gmail_service = build("gmail", "v1", credentials=creds)
                    created = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: (
                            gmail_service.users()
                            .drafts()
                            .create(userId="me", body={"message": {"raw": raw}})
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
                        "message": "This Gmail account needs additional permissions. Please re-authenticate in connector settings.",
                    }
                raise

            logger.info(f"Gmail draft created: id={created.get('id')}")

            kb_message_suffix = ""
            try:
                from app.services.gmail import GmailKBSyncService

                kb_service = GmailKBSyncService(db_session)
                draft_message = created.get("message", {})
                kb_result = await kb_service.sync_after_create(
                    message_id=draft_message.get("id", ""),
                    thread_id=draft_message.get("threadId", ""),
                    subject=final_subject,
                    sender="me",
                    date_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    body_text=final_body,
                    connector_id=actual_connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    draft_id=created.get("id"),
                )
                if kb_result["status"] == "success":
                    kb_message_suffix = " Your knowledge base has also been updated."
                else:
                    kb_message_suffix = " This draft will be added to your knowledge base in the next scheduled sync."
            except Exception as kb_err:
                logger.warning(f"KB sync after create failed: {kb_err}")
                kb_message_suffix = " This draft will be added to your knowledge base in the next scheduled sync."

            return {
                "status": "success",
                "draft_id": created.get("id"),
                "message": f"Successfully created Gmail draft with subject '{final_subject}'.{kb_message_suffix}",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error creating Gmail draft: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while creating the draft. Please try again.",
            }

    return create_gmail_draft
