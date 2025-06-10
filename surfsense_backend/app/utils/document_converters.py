import hashlib


async def convert_element_to_markdown(element) -> str:
    """
    Convert an Unstructured element to markdown format based on its category.

    Args:
        element: The Unstructured API element object

    Returns:
        str: Markdown formatted string
    """
    element_category = element.metadata["category"]
    content = element.page_content

    if not content:
        return ""

    markdown_mapping = {
        "Formula": lambda x: f"```math\n{x}\n```",
        "FigureCaption": lambda x: f"*Figure: {x}*",
        "NarrativeText": lambda x: f"{x}\n\n",
        "ListItem": lambda x: f"- {x}\n",
        "Title": lambda x: f"# {x}\n\n",
        "Address": lambda x: f"> {x}\n\n",
        "EmailAddress": lambda x: f"`{x}`",
        "Image": lambda x: f"![{x}]({x})",
        "PageBreak": lambda x: "\n---\n",
        "Table": lambda x: f"```html\n{element.metadata['text_as_html']}\n```",
        "Header": lambda x: f"## {x}\n\n",
        "Footer": lambda x: f"*{x}*\n\n",
        "CodeSnippet": lambda x: f"```\n{x}\n```",
        "PageNumber": lambda x: f"*Page {x}*\n\n",
        "UncategorizedText": lambda x: f"{x}\n\n"
    }

    converter = markdown_mapping.get(element_category, lambda x: x)
    return converter(content)


async def convert_document_to_markdown(elements):
    """
    Convert all document elements to markdown.

    Args:
        elements: List of Unstructured API elements

    Returns:
        str: Complete markdown document
    """
    markdown_parts = []

    for element in elements:
        markdown_text = await convert_element_to_markdown(element)
        if markdown_text:
            markdown_parts.append(markdown_text)

    return "".join(markdown_parts)


def convert_chunks_to_langchain_documents(chunks):
    """
    Convert chunks from hybrid search results to LangChain Document objects.

    Args:
        chunks: List of chunk dictionaries from hybrid search results

    Returns:
        List of LangChain Document objects
    """
    try:
        from langchain_core.documents import Document as LangChainDocument
    except ImportError:
        raise ImportError(
            "LangChain is not installed. Please install it with `pip install langchain langchain-core`"
        )

    langchain_docs = []

    for chunk in chunks:
        # Extract content from the chunk
        content = chunk.get("content", "")

        # Create metadata dictionary
        metadata = {
            "chunk_id": chunk.get("chunk_id"),
            "score": chunk.get("score"),
            "rank": chunk.get("rank") if "rank" in chunk else None,
        }

        # Add document information to metadata
        if "document" in chunk:
            doc = chunk["document"]
            metadata.update({
                "document_id": doc.get("id"),
                "document_title": doc.get("title"),
                "document_type": doc.get("document_type"),
            })

            # Add document metadata if available
            if "metadata" in doc:
                # Prefix document metadata keys to avoid conflicts
                doc_metadata = {f"doc_meta_{k}": v for k,
                                v in doc.get("metadata", {}).items()}
                metadata.update(doc_metadata)

                # Add source URL if available in metadata
                if "url" in doc.get("metadata", {}):
                    metadata["source"] = doc["metadata"]["url"]
                elif "sourceURL" in doc.get("metadata", {}):
                    metadata["source"] = doc["metadata"]["sourceURL"]

        # Ensure source_id is set for citation purposes
        # Use document_id as the source_id if available
        if "document_id" in metadata:
            metadata["source_id"] = metadata["document_id"]

        # Update content for citation mode - format as XML with explicit source_id
        new_content = f"""
        <document>
            <metadata>
                <source_id>{metadata.get("source_id", metadata.get("document_id", "unknown"))}</source_id>
            </metadata>
            <content>
                <text>
                    {content}
                </text>
            </content>
        </document>
        """

        # Create LangChain Document
        langchain_doc = LangChainDocument(
            page_content=new_content,
            metadata=metadata
        )

        langchain_docs.append(langchain_doc)

    return langchain_docs


def generate_content_hash(content: str, search_space_id: int) -> str:
    """Generate SHA-256 hash for the given content combined with search space ID."""
    combined_data = f"{search_space_id}:{content}"
    return hashlib.sha256(combined_data.encode('utf-8')).hexdigest()
