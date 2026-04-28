"""Shared XML builder for KB documents.

Produces the citation-friendly XML used by every read of a knowledge-base
document (lazy-loaded by :class:`KBPostgresBackend` and synthetic anonymous
files). The XML carries a ``<chunk_index>`` near the top so the LLM can jump
directly to matched-chunk line ranges via ``read_file(offset=…, limit=…)``.

Extracted from the original ``knowledge_search.py`` so the backend, the
priority middleware, and any future renderer share a single implementation.
"""

from __future__ import annotations

import json
from typing import Any


def build_document_xml(
    document: dict[str, Any],
    matched_chunk_ids: set[int] | None = None,
) -> str:
    """Build citation-friendly XML with a ``<chunk_index>`` for smart seeking.

    Args:
        document: Dict shape produced by hybrid search / lazy-load helpers.
            Expected keys: ``document`` (with ``id``, ``title``,
            ``document_type``, ``metadata``) and ``chunks``
            (list of ``{chunk_id, content}``).
        matched_chunk_ids: Optional set of chunk IDs to flag as
            ``matched="true"`` in the chunk index.
    """
    matched = matched_chunk_ids or set()

    doc_meta = document.get("document") or {}
    metadata = (doc_meta.get("metadata") or {}) if isinstance(doc_meta, dict) else {}
    document_id = doc_meta.get("id", document.get("document_id", "unknown"))
    document_type = doc_meta.get("document_type", document.get("source", "UNKNOWN"))
    title = doc_meta.get("title") or metadata.get("title") or "Untitled Document"
    url = (
        metadata.get("url") or metadata.get("source") or metadata.get("page_url") or ""
    )
    metadata_json = json.dumps(metadata, ensure_ascii=False)

    metadata_lines: list[str] = [
        "<document>",
        "<document_metadata>",
        f"  <document_id>{document_id}</document_id>",
        f"  <document_type>{document_type}</document_type>",
        f"  <title><![CDATA[{title}]]></title>",
        f"  <url><![CDATA[{url}]]></url>",
        f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>",
        "</document_metadata>",
        "",
    ]

    chunks = document.get("chunks") or []
    chunk_entries: list[tuple[int | None, str]] = []
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            chunk_content = str(chunk.get("content", "")).strip()
            if not chunk_content:
                continue
            if chunk_id is None:
                xml = f"  <chunk><![CDATA[{chunk_content}]]></chunk>"
            else:
                xml = f"  <chunk id='{chunk_id}'><![CDATA[{chunk_content}]]></chunk>"
            chunk_entries.append((chunk_id, xml))

    index_overhead = 1 + len(chunk_entries) + 1 + 1 + 1
    first_chunk_line = len(metadata_lines) + index_overhead + 1

    current_line = first_chunk_line
    index_entry_lines: list[str] = []
    for cid, xml_str in chunk_entries:
        num_lines = xml_str.count("\n") + 1
        end_line = current_line + num_lines - 1
        matched_attr = ' matched="true"' if cid is not None and cid in matched else ""
        if cid is not None:
            index_entry_lines.append(
                f'  <entry chunk_id="{cid}" lines="{current_line}-{end_line}"{matched_attr}/>'
            )
        else:
            index_entry_lines.append(
                f'  <entry lines="{current_line}-{end_line}"{matched_attr}/>'
            )
        current_line = end_line + 1

    lines = metadata_lines.copy()
    lines.append("<chunk_index>")
    lines.extend(index_entry_lines)
    lines.append("</chunk_index>")
    lines.append("")
    lines.append("<document_content>")
    for _, xml_str in chunk_entries:
        lines.append(xml_str)
    lines.extend(["</document_content>", "</document>"])
    return "\n".join(lines)


__all__ = ["build_document_xml"]
