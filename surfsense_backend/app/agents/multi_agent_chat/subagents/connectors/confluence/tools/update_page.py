import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agents.new_chat.tools.hitl import request_approval
from app.connectors.confluence_history import ConfluenceHistoryConnector
from app.services.confluence import ConfluenceToolMetadataService

logger = logging.getLogger(__name__)


def create_update_confluence_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    @tool
    async def update_confluence_page(
        page_title_or_id: str,
        new_title: str | None = None,
        new_content: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing Confluence page.

        Use this tool when the user asks to modify or edit a Confluence page.

        Args:
            page_title_or_id: The page title or ID to identify the page.
            new_title: Optional new title for the page.
            new_content: Optional new HTML/storage format content.

        Returns:
            Dictionary with status and message.

            IMPORTANT:
            - If status is "rejected", do NOT retry.
            - If status is "not_found", relay the message to the user.
            - If status is "insufficient_permissions", inform user to re-authenticate.
        """
        logger.info(
            f"update_confluence_page called: page_title_or_id='{page_title_or_id}'"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Confluence tool not properly configured.",
            }

        try:
            metadata_service = ConfluenceToolMetadataService(db_session)
            context = await metadata_service.get_update_context(
                search_space_id, user_id, page_title_or_id
            )

            if "error" in context:
                error_msg = context["error"]
                if context.get("auth_expired"):
                    return {
                        "status": "auth_error",
                        "message": error_msg,
                        "connector_id": context.get("connector_id"),
                        "connector_type": "confluence",
                    }
                if "not found" in error_msg.lower():
                    return {"status": "not_found", "message": error_msg}
                return {"status": "error", "message": error_msg}

            page_data = context["page"]
            page_id = page_data["page_id"]
            current_title = page_data["page_title"]
            current_body = page_data.get("body", "")
            current_version = page_data.get("version", 1)
            document_id = page_data.get("document_id")
            connector_id_from_context = context.get("account", {}).get("id")

            result = request_approval(
                action_type="confluence_page_update",
                tool_name="update_confluence_page",
                params={
                    "page_id": page_id,
                    "document_id": document_id,
                    "new_title": new_title,
                    "new_content": new_content,
                    "version": current_version,
                    "connector_id": connector_id_from_context,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_page_id = result.params.get("page_id", page_id)
            final_title = result.params.get("new_title", new_title) or current_title
            final_content = result.params.get("new_content", new_content)
            if final_content is None:
                final_content = current_body
            final_version = result.params.get("version", current_version)
            final_connector_id = result.params.get(
                "connector_id", connector_id_from_context
            )
            final_document_id = result.params.get("document_id", document_id)

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            if not final_connector_id:
                return {
                    "status": "error",
                    "message": "No connector found for this page.",
                }

            result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == final_connector_id,
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
                )
            )
            connector = result.scalars().first()
            if not connector:
                return {
                    "status": "error",
                    "message": "Selected Confluence connector is invalid.",
                }

            try:
                client = ConfluenceHistoryConnector(
                    session=db_session, connector_id=final_connector_id
                )
                api_result = await client.update_page(
                    page_id=final_page_id,
                    title=final_title,
                    body=final_content,
                    version_number=final_version + 1,
                )
                await client.close()
            except Exception as api_err:
                if (
                    "http 403" in str(api_err).lower()
                    or "status code 403" in str(api_err).lower()
                ):
                    try:
                        connector.config = {**connector.config, "auth_expired": True}
                        flag_modified(connector, "config")
                        await db_session.commit()
                    except Exception:
                        pass
                    return {
                        "status": "insufficient_permissions",
                        "connector_id": final_connector_id,
                        "message": "This Confluence account needs additional permissions. Please re-authenticate in connector settings.",
                    }
                raise

            page_links = (
                api_result.get("_links", {}) if isinstance(api_result, dict) else {}
            )
            page_url = ""
            if page_links.get("base") and page_links.get("webui"):
                page_url = f"{page_links['base']}{page_links['webui']}"

            kb_message_suffix = ""
            if final_document_id:
                try:
                    from app.services.confluence import ConfluenceKBSyncService

                    kb_service = ConfluenceKBSyncService(db_session)
                    kb_result = await kb_service.sync_after_update(
                        document_id=final_document_id,
                        page_id=final_page_id,
                        user_id=user_id,
                        search_space_id=search_space_id,
                    )
                    if kb_result["status"] == "success":
                        kb_message_suffix = (
                            " Your knowledge base has also been updated."
                        )
                    else:
                        kb_message_suffix = (
                            " The knowledge base will be updated in the next sync."
                        )
                except Exception as kb_err:
                    logger.warning(f"KB sync after update failed: {kb_err}")
                    kb_message_suffix = (
                        " The knowledge base will be updated in the next sync."
                    )

            return {
                "status": "success",
                "page_id": final_page_id,
                "page_url": page_url,
                "message": f"Confluence page '{final_title}' updated successfully.{kb_message_suffix}",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error updating Confluence page: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while updating the page.",
            }

    return update_confluence_page
