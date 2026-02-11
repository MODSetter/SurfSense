import hashlib
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
        # Generate a unique page ID based on title for testing
        # This helps verify if edited args were used
        page_hash = hashlib.md5(title.encode()).hexdigest()[:8]
        
        # Return detailed response showing what was actually received
        return {
            "status": "success",
            "page_id": f"stub-page-{page_hash}",
            "title": title,
            "content_preview": content[:100] + "..." if len(content) > 100 else content,
            "content_length": len(content),
            "url": f"https://www.notion.so/stub-page-{page_hash}",
            "message": f"✅ Created Notion page '{title}' with {len(content)} characters",
        }

    return create_notion_page
