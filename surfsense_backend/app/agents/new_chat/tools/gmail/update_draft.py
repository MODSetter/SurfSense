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


def create_update_gmail_draft_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def update_gmail_draft(
        draft_subject_or_id: str,
        body: str,
        to: str | None = None,
        subject: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing Gmail draft.

        Use when the user asks to modify, edit, or add content to an existing
        email draft. This replaces the draft content with the new version.
        The user will be able to review and edit the content before it is applied.

        If the user simply wants to "edit" a draft without specifying exact changes,
        generate the body yourself using your best understanding of the conversation
        context. The user will review and can freely edit the content in the approval
        card before confirming.

        IMPORTANT: This tool is ONLY for modifying Gmail draft content, NOT for
        deleting/trashing drafts (use trash_gmail_email instead), Notion pages,
        calendar events, or any other content type.

        Args:
            draft_subject_or_id: The exact subject line of the draft to update
                (as it appears in Gmail drafts).
            body: The full updated body content for the draft. Generate this
                  yourself based on the user's request and conversation context.
            to: Optional new recipient email address (keeps original if omitted).
            subject: Optional new subject line (keeps original if omitted).
            cc: Optional CC recipient(s), comma-separated.
            bcc: Optional BCC recipient(s), comma-separated.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - draft_id: Gmail draft ID (if success)
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined the action.
              Respond with a brief acknowledgment and do NOT retry or suggest alternatives.
            - If status is "not_found", relay the exact message to the user and ask them
              to verify the draft subject or check if it has been indexed.
            - If status is "insufficient_permissions", the connector lacks the required OAuth scope.
              Inform the user they need to re-authenticate and do NOT retry the action.

        Examples:
            - "Update the Kurseong Plan draft with the new itinerary details"
            - "Edit my draft about the project proposal and change the recipient"
            - "Let me edit the meeting notes draft" (call with current body content so user can edit in the approval card)
        """
        logger.info(
            f"update_gmail_draft called: draft_subject_or_id='{draft_subject_or_id}'"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Gmail tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = GmailToolMetadataService(db_session)
            context = await metadata_service.get_update_context(
                search_space_id, user_id, draft_subject_or_id
            )

            if "error" in context:
                error_msg = context["error"]
                if "not found" in error_msg.lower():
                    logger.warning(f"Draft not found: {error_msg}")
                    return {"status": "not_found", "message": error_msg}
                logger.error(f"Failed to fetch update context: {error_msg}")
                return {"status": "error", "message": error_msg}

            account = context.get("account", {})
            if account.get("auth_expired"):
                logger.warning(
                    "Gmail account %s has expired authentication",
                    account.get("id"),
                )
                return {
                    "status": "auth_error",
                    "message": "The Gmail account for this draft needs re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "gmail",
                }

            email = context["email"]
            message_id = email["message_id"]
            document_id = email.get("document_id")
            connector_id_from_context = account["id"]
            draft_id_from_context = context.get("draft_id")

            original_subject = email.get("subject", draft_subject_or_id)
            final_subject_default = subject if subject else original_subject
            final_to_default = to if to else ""

            logger.info(
                f"Requesting approval for updating Gmail draft: '{original_subject}' "
                f"(message_id={message_id}, draft_id={draft_id_from_context})"
            )
            result = request_approval(
                action_type="gmail_draft_update",
                tool_name="update_gmail_draft",
                params={
                    "message_id": message_id,
                    "draft_id": draft_id_from_context,
                    "to": final_to_default,
                    "subject": final_subject_default,
                    "body": body,
                    "cc": cc,
                    "bcc": bcc,
                    "connector_id": connector_id_from_context,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. The draft was not updated. Do not ask again or suggest alternatives.",
                }

            final_to = result.params.get("to", final_to_default)
            final_subject = result.params.get("subject", final_subject_default)
            final_body = result.params.get("body", body)
            final_cc = result.params.get("cc", cc)
            final_bcc = result.params.get("bcc", bcc)
            final_connector_id = result.params.get(
                "connector_id", connector_id_from_context
            )
            final_draft_id = result.params.get("draft_id", draft_id_from_context)

            if not final_connector_id:
                return {
                    "status": "error",
                    "message": "No connector found for this draft.",
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
                f"Updating Gmail draft: subject='{final_subject}', connector={final_connector_id}"
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

            # Resolve draft_id if not already available
            if not final_draft_id:
                logger.info(
                    f"draft_id not in metadata, looking up via drafts.list for message_id={message_id}"
                )
                if is_composio_gmail:
                    final_draft_id = await _find_composio_draft_id_by_message(
                        connector, user_id, message_id
                    )
                else:
                    from googleapiclient.discovery import build

                    gmail_service = build("gmail", "v1", credentials=creds)
                    final_draft_id = await _find_draft_id_by_message(
                        gmail_service, message_id
                    )

            if not final_draft_id:
                return {
                    "status": "error",
                    "message": (
                        "Could not find this draft in Gmail. "
                        "It may have already been sent or deleted."
                    ),
                }

            message = MIMEText(final_body)
            if final_to:
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

                    updated, error = await execute_composio_gmail_tool(
                        connector,
                        user_id,
                        "GMAIL_UPDATE_DRAFT",
                        {
                            "user_id": "me",
                            "draft_id": final_draft_id,
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
                    if not isinstance(updated, dict):
                        updated = {}
                else:
                    from googleapiclient.discovery import build

                    gmail_service = build("gmail", "v1", credentials=creds)
                    updated = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: (
                            gmail_service.users()
                            .drafts()
                            .update(
                                userId="me",
                                id=final_draft_id,
                                body={"message": {"raw": raw}},
                            )
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
                if isinstance(api_err, HttpError) and api_err.resp.status == 404:
                    return {
                        "status": "error",
                        "message": "Draft no longer exists in Gmail. It may have been sent or deleted.",
                    }
                raise

            logger.info(f"Gmail draft updated: id={updated.get('id')}")

            kb_message_suffix = ""
            if document_id:
                try:
                    from sqlalchemy.future import select as sa_select
                    from sqlalchemy.orm.attributes import flag_modified

                    from app.db import Document

                    doc_result = await db_session.execute(
                        sa_select(Document).filter(Document.id == document_id)
                    )
                    document = doc_result.scalars().first()
                    if document:
                        document.source_markdown = final_body
                        document.title = final_subject
                        meta = dict(document.document_metadata or {})
                        meta["subject"] = final_subject
                        meta["draft_id"] = updated.get("id", final_draft_id)
                        updated_msg = updated.get("message", {})
                        if updated_msg.get("id"):
                            meta["message_id"] = updated_msg["id"]
                        document.document_metadata = meta
                        flag_modified(document, "document_metadata")
                        await db_session.commit()
                        kb_message_suffix = (
                            " Your knowledge base has also been updated."
                        )
                        logger.info(
                            f"KB document {document_id} updated for draft {final_draft_id}"
                        )
                    else:
                        kb_message_suffix = " This draft will be fully updated in your knowledge base in the next scheduled sync."
                except Exception as kb_err:
                    logger.warning(f"KB update after draft edit failed: {kb_err}")
                    await db_session.rollback()
                    kb_message_suffix = " This draft will be fully updated in your knowledge base in the next scheduled sync."

            return {
                "status": "success",
                "draft_id": updated.get("id"),
                "message": f"Successfully updated Gmail draft with subject '{final_subject}'.{kb_message_suffix}",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error updating Gmail draft: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while updating the draft. Please try again.",
            }

    return update_gmail_draft


async def _find_draft_id_by_message(gmail_service: Any, message_id: str) -> str | None:
    """Look up a draft's ID by its message ID via the Gmail API."""
    try:
        page_token = None
        while True:
            kwargs: dict[str, Any] = {"userId": "me", "maxResults": 100}
            if page_token:
                kwargs["pageToken"] = page_token

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda kwargs=kwargs: (
                    gmail_service.users().drafts().list(**kwargs).execute()
                ),
            )

            for draft in response.get("drafts", []):
                if draft.get("message", {}).get("id") == message_id:
                    return draft["id"]

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return None
    except Exception as e:
        logger.warning(f"Failed to look up draft by message_id: {e}")
        return None


async def _find_composio_draft_id_by_message(
    connector: Any, user_id: str, message_id: str
) -> str | None:
    from app.agents.new_chat.tools.gmail.composio_helpers import (
        execute_composio_gmail_tool,
    )

    page_token = ""
    while True:
        params: dict[str, Any] = {
            "user_id": "me",
            "max_results": 100,
            "verbose": False,
        }
        if page_token:
            params["page_token"] = page_token

        data, error = await execute_composio_gmail_tool(
            connector, user_id, "GMAIL_LIST_DRAFTS", params
        )
        if error or not isinstance(data, dict):
            return None

        for draft in data.get("drafts", []):
            if draft.get("message", {}).get("id") == message_id:
                return draft.get("id")

        page_token = data.get("nextPageToken") or data.get("next_page_token") or ""
        if not page_token:
            return None
