"""
Base functionality and shared imports for document processors.
"""


from langchain_community.document_transformers import MarkdownifyTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import Chunk, Document
from app.prompts import SUMMARY_PROMPT_TEMPLATE

# Initialize markdown transformer
md = MarkdownifyTransformer()


async def check_duplicate_document(
    session: AsyncSession, content_hash: str
) -> Document | None:
    """
    Check if a document with the given content hash already exists.

    Args:
        session: Database session
        content_hash: Hash of the document content

    Returns:
        Existing document if found, None otherwise
    """
    existing_doc_result = await session.execute(
        select(Document).where(Document.content_hash == content_hash)
    )
    return existing_doc_result.scalars().first()


async def create_document_chunks(content: str) -> list[Chunk]:
    """
    Create chunks from document content.

    Args:
        content: Document content to chunk

    Returns:
        List of Chunk objects with embeddings
    """
    return [
        Chunk(
            content=chunk.text,
            embedding=config.embedding_model_instance.embed(chunk.text),
        )
        for chunk in config.chunker_instance.chunk(content)
    ]


async def generate_document_summary(
    content: str, user_llm, document_title: str = ""
) -> tuple[str, list[float]]:
    """
    Generate summary and embedding for document content.

    Args:
        content: Document content
        user_llm: User's LLM instance
        document_title: Optional document title for context

    Returns:
        Tuple of (summary_content, summary_embedding)
    """
    summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
    summary_result = await summary_chain.ainvoke({"document": content})
    summary_content = summary_result.content
    summary_embedding = config.embedding_model_instance.embed(summary_content)

    return summary_content, summary_embedding
