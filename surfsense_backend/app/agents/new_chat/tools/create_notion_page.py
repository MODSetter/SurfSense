from typing import Any

from langchain_core.tools import tool


def create_create_notion_page_tool():
    @tool
    async def create_notion_page(
        title: str,
        content: str,
    ) -> dict[str, Any]:
        """Create a new page in Notion with the given title and content.

        Use this tool when the user asks you to create, save, or publish
        something to Notion. The page will be created in the user's
        configured Notion workspace.

        Args:
            title: The title of the Notion page.
            content: The markdown content for the page body.
        """
        return {
            "status": "success",
            "page_id": "stub-page-id-12345",
            "title": title,
            "url": "https://www.notion.so/stub-page-12345",
        }

    return create_notion_page
