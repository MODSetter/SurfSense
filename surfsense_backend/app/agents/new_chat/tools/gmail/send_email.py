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


def create_send_gmail_email_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def send_gmail_email(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        bcc: str | None = None,
    ) -> dict[str, Any]:
        """Send an email via Gmail.

        Use when the user explicitly asks to send an email. This sends the
        email immediately - it cannot be unsent.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Email body content.
            cc: Optional CC recipient(s), comma-separated.
            bcc: Optional BCC recipient(s), comma-separated.

        Returns:
            Dictionary with:
            - status: "success", "rejected", or "error"
            - message_id: Gmail message ID (if success)
            - thread_id: Gmail thread ID (if success)
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined the action.
              Respond with a brief acknowledgment and do NOT retry or suggest alternatives.
            - If status is "insufficient_permissions", the connector lacks the required OAuth scope.
              Inform the user they need to re-authenticate and do NOT retry the action.

        Examples:
            - "Send an email to alice@example.com about the meeting"
            - "Email Bob the project update"
        """
        logger.info(f"send_gmail_email called: to='{to}', subject='{subject}'")

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
                f"Requesting approval for sending Gmail email: to='{to}', subject='{subject}'"
            )
            result = request_approval(
                action_type="gmail_email_send",
                tool_name="send_gmail_email",
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
                    "message": "User declined. The email was not sent. Do not ask again or suggest alternatives.",
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
                f"Sending Gmail email: to='{final_to}', subject='{final_subject}', connector={actual_connector_id}"
            )

            if (
                connector.connector_type
                == SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR
            ):
                from app.utils.google_credentials import build_composio_credentials

                cca_id = connector.config.get("composio_connected_account_id")
                if cca_id:
                    creds = build_composio_credentials(cca_id)
                else:
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

            from googleapiclient.discovery import build

            gmail_service = build("gmail", "v1", credentials=creds)

            message = MIMEText(final_body)
            message["to"] = final_to
            message["subject"] = final_subject
            if final_cc:
                message["cc"] = final_cc
            if final_bcc:
                message["bcc"] = final_bcc
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            try:
                sent = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: (
                        gmail_service.users()
                        .messages()
                        .send(userId="me", body={"raw": raw})
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

            logger.info(
                f"Gmail email sent: id={sent.get('id')}, threadId={sent.get('threadId')}"
            )

            kb_message_suffix = ""
            try:
                from app.services.gmail import GmailKBSyncService

                kb_service = GmailKBSyncService(db_session)
                kb_result = await kb_service.sync_after_create(
                    message_id=sent.get("id", ""),
                    thread_id=sent.get("threadId", ""),
                    subject=final_subject,
                    sender="me",
                    date_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    body_text=final_body,
                    connector_id=actual_connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                )
                if kb_result["status"] == "success":
                    kb_message_suffix = " Your knowledge base has also been updated."
                else:
                    kb_message_suffix = " This email will be added to your knowledge base in the next scheduled sync."
            except Exception as kb_err:
                logger.warning(f"KB sync after send failed: {kb_err}")
                kb_message_suffix = " This email will be added to your knowledge base in the next scheduled sync."

            return {
                "status": "success",
                "message_id": sent.get("id"),
                "thread_id": sent.get("threadId"),
                "message": f"Successfully sent email to '{final_to}' with subject '{final_subject}'.{kb_message_suffix}",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error sending Gmail email: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while sending the email. Please try again.",
            }

    return send_gmail_email
