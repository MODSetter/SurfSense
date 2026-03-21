import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.confluence_history import ConfluenceHistoryConnector
from app.services.confluence import ConfluenceToolMetadataService

logger = logging.getLogger(__name__)


def create_delete_confluence_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    @tool
    async def delete_confluence_page(
        page_title_or_id: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Delete a Confluence page.

        Use this tool when the user asks to delete or remove a Confluence page.

        Args:
            page_title_or_id: The page title or ID to identify the page.
            delete_from_kb: Whether to also remove from the knowledge base.

        Returns:
            Dictionary with status, message, and deleted_from_kb.

            IMPORTANT:
            - If status is "rejected", do NOT retry.
            - If status is "not_found", relay the message to the user.
            - If status is "insufficient_permissions", inform user to re-authenticate.
        """
        logger.info(
            f"delete_confluence_page called: page_title_or_id='{page_title_or_id}'"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Confluence tool not properly configured.",
            }

        try:
            metadata_service = ConfluenceToolMetadataService(db_session)
            context = await metadata_service.get_deletion_context(
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
            page_title = page_data.get("page_title", "")
            document_id = page_data["document_id"]
            connector_id_from_context = context.get("account", {}).get("id")

            approval = interrupt(
                {
                    "type": "confluence_page_deletion",
                    "action": {
                        "tool": "delete_confluence_page",
                        "params": {
                            "page_id": page_id,
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
                return {"status": "error", "message": "No approval decision received"}

            decision = decisions[0]
            decision_type = decision.get("type") or decision.get("decision_type")

            if decision_type == "reject":
                return {
                    "status": "rejected",
                    "message": "User declined. The page was not deleted.",
                }

            final_params: dict[str, Any] = {}
            edited_action = decision.get("edited_action")
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_page_id = final_params.get("page_id", page_id)
            final_connector_id = final_params.get(
                "connector_id", connector_id_from_context
            )
            final_delete_from_kb = final_params.get("delete_from_kb", delete_from_kb)

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
                await client.delete_page(final_page_id)
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
                except Exception as e:
                    logger.error(f"Failed to delete document from KB: {e}")
                    await db_session.rollback()

            message = f"Confluence page '{page_title}' deleted successfully."
            if deleted_from_kb:
                message += " Also removed from the knowledge base."

            return {
                "status": "success",
                "page_id": final_page_id,
                "deleted_from_kb": deleted_from_kb,
                "message": message,
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error deleting Confluence page: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while deleting the page.",
            }

    return delete_confluence_page
