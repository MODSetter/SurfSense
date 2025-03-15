from notion_client import Client

class NotionHistoryConnector:
    def __init__(self, token):
        """
        Initialize the NotionPageFetcher with a token.
        
        Args:
            token (str): Notion integration token
        """
        self.notion = Client(auth=token)
    
    def get_all_pages(self, start_date=None, end_date=None):
        """
        Fetches all pages shared with your integration and their content.
        
        Args:
            start_date (str, optional): ISO 8601 date string (e.g., "2023-01-01T00:00:00Z")
            end_date (str, optional): ISO 8601 date string (e.g., "2023-12-31T23:59:59Z")
            
        Returns:
            list: List of dictionaries containing page data
        """
        # Build the filter for the search
        # Note: Notion API requires specific filter structure
        search_params = {}
        
        # Filter for pages only (not databases)
        search_params["filter"] = {
            "value": "page",
            "property": "object"
        }
        
        # Add date filters if provided
        if start_date or end_date:
            date_filter = {}
            
            if start_date:
                date_filter["on_or_after"] = start_date
            
            if end_date:
                date_filter["on_or_before"] = end_date
            
            # Add the date filter to the search params
            if date_filter:
                search_params["sort"] = {
                    "direction": "descending",
                    "timestamp": "last_edited_time"
                }
        
        # First, get a list of all pages the integration has access to
        search_results = self.notion.search(**search_params)
        
        pages = search_results["results"]
        all_page_data = []
        
        for page in pages:
            page_id = page["id"]
            
            # Get detailed page information
            page_content = self.get_page_content(page_id)
            
            all_page_data.append({
                "page_id": page_id,
                "title": self.get_page_title(page),
                "content": page_content
            })
        
        return all_page_data
    
    def get_page_title(self, page):
        """
        Extracts the title from a page object.
        
        Args:
            page (dict): Notion page object
            
        Returns:
            str: Page title or a fallback string
        """
        # Title can be in different properties depending on the page type
        if "properties" in page:
            # Try to find a title property
            for prop_name, prop_data in page["properties"].items():
                if prop_data["type"] == "title" and len(prop_data["title"]) > 0:
                    return " ".join([text_obj["plain_text"] for text_obj in prop_data["title"]])
        
        # If no title found, return the page ID as fallback
        return f"Untitled page ({page['id']})"
    
    def get_page_content(self, page_id):
        """
        Fetches the content (blocks) of a specific page.
        
        Args:
            page_id (str): The ID of the page to fetch
            
        Returns:
            list: List of processed blocks from the page
        """
        blocks = []
        has_more = True
        cursor = None
        
        # Paginate through all blocks
        while has_more:
            if cursor:
                response = self.notion.blocks.children.list(block_id=page_id, start_cursor=cursor)
            else:
                response = self.notion.blocks.children.list(block_id=page_id)
            
            blocks.extend(response["results"])
            has_more = response["has_more"]
            
            if has_more:
                cursor = response["next_cursor"]
        
        # Process nested blocks recursively
        processed_blocks = []
        for block in blocks:
            processed_block = self.process_block(block)
            processed_blocks.append(processed_block)
        
        return processed_blocks
    
    def process_block(self, block):
        """
        Processes a block and recursively fetches any child blocks.
        
        Args:
            block (dict): The block to process
            
        Returns:
            dict: Processed block with content and children
        """
        block_id = block["id"]
        block_type = block["type"]
        
        # Extract block content based on its type
        content = self.extract_block_content(block)
        
        # Check if block has children
        has_children = block.get("has_children", False)
        child_blocks = []
        
        if has_children:
            # Fetch and process child blocks
            children_response = self.notion.blocks.children.list(block_id=block_id)
            for child_block in children_response["results"]:
                child_blocks.append(self.process_block(child_block))
        
        return {
            "id": block_id,
            "type": block_type,
            "content": content,
            "children": child_blocks
        }
    
    def extract_block_content(self, block):
        """
        Extracts the content from a block based on its type.
        
        Args:
            block (dict): The block to extract content from
            
        Returns:
            str: Extracted content as a string
        """
        block_type = block["type"]
        
        # Different block types have different structures
        if block_type in block and "rich_text" in block[block_type]:
            return "".join([text_obj["plain_text"] for text_obj in block[block_type]["rich_text"]])
        elif block_type == "image":
            # Instead of returning the raw URL which may contain sensitive AWS credentials,
            # return a placeholder or reference to the image
            if "file" in block["image"]:
                # For Notion-hosted images (which use AWS S3 pre-signed URLs)
                return "[Notion Image]"
            elif "external" in block["image"]:
                # For external images, we can return a sanitized reference
                url = block["image"]["external"]["url"]
                # Only return the domain part of external URLs to avoid potential sensitive parameters
                try:
                    from urllib.parse import urlparse
                    parsed_url = urlparse(url)
                    return f"[External Image from {parsed_url.netloc}]"
                except:
                    return "[External Image]"
        elif block_type == "code":
            language = block["code"]["language"]
            code_text = "".join([text_obj["plain_text"] for text_obj in block["code"]["rich_text"]])
            return f"```{language}\n{code_text}\n```"
        elif block_type == "equation":
            return block["equation"]["expression"]
        # Add more block types as needed
        
        # Return empty string for unsupported block types
        return ""


# Example usage
# if __name__ == "__main__":
#     # Simple example of how to use this module
#     import argparse
    
#     parser = argparse.ArgumentParser(description="Fetch Notion pages using an integration token")
#     parser.add_argument("--token", help="Your Notion integration token")
#     parser.add_argument("--start-date", help="Start date in ISO format (e.g., 2023-01-01T00:00:00Z)")
#     parser.add_argument("--end-date", help="End date in ISO format (e.g., 2023-12-31T23:59:59Z)")
#     args = parser.parse_args()
    
#     token = args.token
#     if not token:
#         token = input("Enter your Notion integration token: ")
    
#     fetcher = NotionPageFetcher(token)
    
#     try:
#         pages = fetcher.get_all_pages(args.start_date, args.end_date)
#         print(f"Fetched {len(pages)} pages from Notion")
#         for page in pages:
#             print(f"- {page['title']}")
#     except Exception as e:
#         print(f"Error: {str(e)}")