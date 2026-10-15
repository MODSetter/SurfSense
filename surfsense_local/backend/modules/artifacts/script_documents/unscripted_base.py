"""Why a render cannot continue an artifact another tool made, and what changes it instead.

A revised copy and a converted PDF keep versions but no script, and Studio
offers neither a Refine, so the refusal names the tool that does change them.
"""

from typing import Any

from modules.artifacts.converted_documents.conversion import conversion_of
from modules.artifacts.revised_copies.revision import revision_of


def unscripted_refusal(artifact_id: int, metadata: dict[str, Any] | None) -> str | None:
    """The refusal for a revised copy or a converted PDF; None for any other artifact."""
    if revision_of(metadata) is not None:
        return (
            f"Artifact {artifact_id} is a revised copy of the user's file and keeps "
            "no script. Change it with surfsense_revise_document with artifact_id "
            f"{artifact_id}."
        )
    conversion = conversion_of(metadata)
    if conversion is None:
        return None
    origin = (
        f"artifact {conversion.artifact_id}"
        if conversion.artifact_id is not None
        else f"source {conversion.document_id}"
    )
    return (
        f"Artifact {artifact_id} is a PDF converted from {origin} and keeps no "
        "script. Change the Word document or deck it came from, then convert the "
        "new version with surfsense_convert_document."
    )
