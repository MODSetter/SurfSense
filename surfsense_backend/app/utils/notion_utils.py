"""Utility functions for processing Notion blocks and content."""


def extract_all_block_ids(blocks_list):
    ids = []
    for block in blocks_list:
        if isinstance(block, dict) and "id" in block:
            ids.append(block["id"])
        if isinstance(block, dict) and block.get("children"):
            ids.extend(extract_all_block_ids(block["children"]))
    return ids


def process_blocks(blocks, level=0):
    result = ""
    for block in blocks:
        block_type = block.get("type")
        block_content = block.get("content", "")
        children = block.get("children", [])

        # Add indentation based on level
        indent = "  " * level

        # Format based on block type
        if block_type in ["paragraph", "text"]:
            result += f"{indent}{block_content}\n\n"
        elif block_type in ["heading_1", "header"]:
            result += f"{indent}# {block_content}\n\n"
        elif block_type == "heading_2":
            result += f"{indent}## {block_content}\n\n"
        elif block_type == "heading_3":
            result += f"{indent}### {block_content}\n\n"
        elif block_type == "bulleted_list_item":
            result += f"{indent}* {block_content}\n"
        elif block_type == "numbered_list_item":
            result += f"{indent}1. {block_content}\n"
        elif block_type == "to_do":
            result += f"{indent}- [ ] {block_content}\n"
        elif block_type == "toggle":
            result += f"{indent}> {block_content}\n"
        elif block_type == "code":
            result += f"{indent}```\n{block_content}\n```\n\n"
        elif block_type == "quote":
            result += f"{indent}> {block_content}\n\n"
        elif block_type == "callout":
            result += f"{indent}> **Note:** {block_content}\n\n"
        elif block_type == "image":
            result += f"{indent}![Image]({block_content})\n\n"
        else:
            # Default for other block types
            if block_content:
                result += f"{indent}{block_content}\n\n"

        # Process children recursively
        if children:
            result += process_blocks(children, level + 1)

    return result
