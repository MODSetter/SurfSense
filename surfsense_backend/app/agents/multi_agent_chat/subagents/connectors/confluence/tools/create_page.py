import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agents.new_chat.tools.hitl import request_approval
from app.connectors.confluence_history import ConfluenceHistoryConnector
from app.services.confluence import ConfluenceToolMetadataService

logger = logging.getLogger(__name__)


def create_create_confluence_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    @tool
    async def create_confluence_page(
        title: str,
        content: str | None = None,
        space_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new page in Confluence.

        Use this tool when the user explicitly asks to create a new Confluence page.

        Args:
            title: Title of the page.
            content: Optional HTML/storage format content for the page body.
            space_id: Optional Confluence space ID to create the page in.

        Returns:
            Dictionary with status, page_id, and message.

            IMPORTANT:
            - If status is "rejected", do NOT retry.
            - If status is "insufficient_permissions", inform user to re-authenticate.
        """
        logger.info(f"create_confluence_page called: title='{title}'")

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Confluence tool not properly configured.",
            }

        try:
            metadata_service = ConfluenceToolMetadataService(db_session)
            context = await metadata_service.get_creation_context(
                search_space_id, user_id
            )

            if "error" in context:
                return {"status": "error", "message": context["error"]}

            accounts = context.get("accounts", [])
            if accounts and all(a.get("auth_expired") for a in accounts):
                return {
                    "status": "auth_error",
                    "message": "All connected Confluence accounts need re-authentication.",
                    "connector_type": "confluence",
                }

            result = request_approval(
                action_type="confluence_page_creation",
                tool_name="create_confluence_page",
                params={
                    "title": title,
                    "content": content,
                    "space_id": space_id,
                    "connector_id": connector_id,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_title = result.params.get("title", title)
            final_content = result.params.get("content", content) or ""
            final_space_id = result.params.get("space_id", space_id)
            final_connector_id = result.params.get("connector_id", connector_id)

            if not final_title or not final_title.strip():
                return {"status": "error", "message": "Page title cannot be empty."}
            if not final_space_id:
                return {"status": "error", "message": "A space must be selected."}

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            actual_connector_id = final_connector_id
            if actual_connector_id is None:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
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
                        "message": "No Confluence connector found.",
                    }
                actual_connector_id = connector.id
            else:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == actual_connector_id,
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
                    session=db_session, connector_id=actual_connector_id
                )
                api_result = await client.create_page(
                    space_id=final_space_id,
                    title=final_title,
                    body=final_content,
                )
                await client.close()
            except Exception as api_err:
                if (
                    "http 403" in str(api_err).lower()
                    or "status code 403" in str(api_err).lower()
                ):
                    try:
                        _conn = connector
                        _conn.config = {**_conn.config, "auth_expired": True}
                        flag_modified(_conn, "config")
                        await db_session.commit()
                    except Exception:
                        pass
                    return {
                        "status": "insufficient_permissions",
                        "connector_id": actual_connector_id,
                        "message": "This Confluence account needs additional permissions. Please re-authenticate in connector settings.",
                    }
                raise

            page_id = str(api_result.get("id", ""))
            page_links = (
                api_result.get("_links", {}) if isinstance(api_result, dict) else {}
            )
            page_url = ""
            if page_links.get("base") and page_links.get("webui"):
                page_url = f"{page_links['base']}{page_links['webui']}"

            kb_message_suffix = ""
            try:
                from app.services.confluence import ConfluenceKBSyncService

                kb_service = ConfluenceKBSyncService(db_session)
                kb_result = await kb_service.sync_after_create(
                    page_id=page_id,
                    page_title=final_title,
                    space_id=final_space_id,
                    body_content=final_content,
                    connector_id=actual_connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                )
                if kb_result["status"] == "success":
                    kb_message_suffix = " Your knowledge base has also been updated."
                else:
                    kb_message_suffix = " This page will be added to your knowledge base in the next scheduled sync."
            except Exception as kb_err:
                logger.warning(f"KB sync after create failed: {kb_err}")
                kb_message_suffix = " This page will be added to your knowledge base in the next scheduled sync."

            return {
                "status": "success",
                "page_id": page_id,
                "page_url": page_url,
                "message": f"Confluence page '{final_title}' created successfully.{kb_message_suffix}",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error creating Confluence page: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while creating the page.",
            }

    return create_confluence_page
