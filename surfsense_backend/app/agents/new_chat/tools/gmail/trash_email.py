import asyncio
import logging
from datetime import datetime
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.gmail import GmailToolMetadataService

logger = logging.getLogger(__name__)


def create_trash_gmail_email_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def trash_gmail_email(
        email_subject_or_id: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Move an email or draft to trash in Gmail.

        Use when the user asks to delete, remove, or trash an email or draft.

        Args:
            email_subject_or_id: The exact subject line or message ID of the
                email to trash (as it appears in the inbox).
            delete_from_kb: Whether to also remove the email from the knowledge base.
                           Default is False.
                           Set to True to remove from both Gmail and knowledge base.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - message_id: Gmail message ID (if success)
            - deleted_from_kb: whether the document was removed from the knowledge base
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined. Respond with a brief
              acknowledgment and do NOT retry or suggest alternatives.
            - If status is "not_found", relay the exact message to the user and ask them
              to verify the email subject or check if it has been indexed.
            - If status is "insufficient_permissions", the connector lacks the required OAuth scope.
              Inform the user they need to re-authenticate and do NOT retry this tool.
        Examples:
            - "Delete the email about 'Meeting Cancelled'"
            - "Trash the email from Bob about the project"
        """
        logger.info(
            f"trash_gmail_email called: email_subject_or_id='{email_subject_or_id}', delete_from_kb={delete_from_kb}"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Gmail tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = GmailToolMetadataService(db_session)
            context = await metadata_service.get_trash_context(
                search_space_id, user_id, email_subject_or_id
            )

            if "error" in context:
                error_msg = context["error"]
                if "not found" in error_msg.lower():
                    logger.warning(f"Email not found: {error_msg}")
                    return {"status": "not_found", "message": error_msg}
                logger.error(f"Failed to fetch trash context: {error_msg}")
                return {"status": "error", "message": error_msg}

            account = context.get("account", {})
            if account.get("auth_expired"):
                logger.warning(
                    "Gmail account %s has expired authentication",
                    account.get("id"),
                )
                return {
                    "status": "auth_error",
                    "message": "The Gmail account for this email needs re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "gmail",
                }

            email = context["email"]
            message_id = email["message_id"]
            document_id = email.get("document_id")
            connector_id_from_context = context["account"]["id"]

            if not message_id:
                return {
                    "status": "error",
                    "message": "Message ID is missing from the indexed document. Please re-index the email and try again.",
                }

            logger.info(
                f"Requesting approval for trashing Gmail email: '{email_subject_or_id}' (message_id={message_id}, delete_from_kb={delete_from_kb})"
            )
            approval = interrupt(
                {
                    "type": "gmail_email_trash",
                    "action": {
                        "tool": "trash_gmail_email",
                        "params": {
                            "message_id": message_id,
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
                    "message": "User declined. The email was not trashed. Do not ask again or suggest alternatives.",
                }

            edited_action = decision.get("edited_action")
            final_params: dict[str, Any] = {}
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_message_id = final_params.get("message_id", message_id)
            final_connector_id = final_params.get(
                "connector_id", connector_id_from_context
            )
            final_delete_from_kb = final_params.get("delete_from_kb", delete_from_kb)

            if not final_connector_id:
                return {
                    "status": "error",
                    "message": "No connector found for this email.",
                }

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            _gmail_types = [
                SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
                SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
            ]

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

            logger.info(
                f"Trashing Gmail email: message_id='{final_message_id}', connector={final_connector_id}"
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

            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: (
                        gmail_service.users()
                        .messages()
                        .trash(userId="me", id=final_message_id)
                        .execute()
                    ),
                )
            except Exception as api_err:
                from googleapiclient.errors import HttpError

                if isinstance(api_err, HttpError) and api_err.resp.status == 403:
                    logger.warning(
                        f"Insufficient permissions for connector {connector.id}: {api_err}"
                    )
                    try:
                        from sqlalchemy.orm.attributes import flag_modified

                        if not connector.config.get("auth_expired"):
                            connector.config = {
                                **connector.config,
                                "auth_expired": True,
                            }
                            flag_modified(connector, "config")
                            await db_session.commit()
                    except Exception:
                        logger.warning(
                            "Failed to persist auth_expired for connector %s",
                            connector.id,
                            exc_info=True,
                        )
                    return {
                        "status": "insufficient_permissions",
                        "connector_id": connector.id,
                        "message": "This Gmail account needs additional permissions. Please re-authenticate in connector settings.",
                    }
                raise

            logger.info(f"Gmail email trashed: message_id={final_message_id}")

            trash_result: dict[str, Any] = {
                "status": "success",
                "message_id": final_message_id,
                "message": f"Successfully moved email '{email.get('subject', email_subject_or_id)}' to trash.",
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
                    trash_result["warning"] = (
                        f"Email trashed, but failed to remove from knowledge base: {e!s}"
                    )

            trash_result["deleted_from_kb"] = deleted_from_kb
            if deleted_from_kb:
                trash_result["message"] = (
                    f"{trash_result.get('message', '')} (also removed from knowledge base)"
                )

            return trash_result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error trashing Gmail email: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while trashing the email. Please try again.",
            }

    return trash_gmail_email
