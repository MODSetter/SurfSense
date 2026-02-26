from app.prompts import SUMMARY_PROMPT_TEMPLATE
from app.utils.document_converters import optimize_content_for_context_window


async def summarize_document(
    source_markdown: str, llm, metadata: dict | None = None
) -> str:
    """Generate a text summary of a document using an LLM, prefixed with metadata when provided."""
    model_name = getattr(llm, "model", "gpt-3.5-turbo")
    optimized_content = optimize_content_for_context_window(
        source_markdown, metadata, model_name
    )

    summary_chain = SUMMARY_PROMPT_TEMPLATE | llm
    content_with_metadata = (
        f"<DOCUMENT><DOCUMENT_METADATA>\n\n{metadata}\n\n</DOCUMENT_METADATA>"
        f"\n\n<DOCUMENT_CONTENT>\n\n{optimized_content}\n\n</DOCUMENT_CONTENT></DOCUMENT>"
    )
    summary_result = await summary_chain.ainvoke({"document": content_with_metadata})
    summary_content = summary_result.content

    if metadata:
        metadata_parts = ["# DOCUMENT METADATA"]
        for key, value in metadata.items():
            if value:
                metadata_parts.append(f"**{key.replace('_', ' ').title()}:** {value}")
        metadata_section = "\n".join(metadata_parts)
        return f"{metadata_section}\n\n# DOCUMENT SUMMARY\n\n{summary_content}"

    return summary_content
