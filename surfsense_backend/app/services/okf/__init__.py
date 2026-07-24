"""Open Knowledge Format (OKF v0.1) serialization for the SurfSense KB.

Single source of truth for turning documents and folders into OKF concepts,
``index.md`` listings and ``log.md`` logs. Pure KB-layer functions; every
consumer (ZIP export, REST, MCP, agents) calls in.

The OKF-native model: ``Document`` rows are canonical, and frontmatter is
*derived* from their columns on read (never stored), so rows are conformant by
construction. Chunks and embeddings are a *derived*, rebuildable search
projection - never a source of truth.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

from app.services.okf.serializer import (
    INDEX_FILENAME,
    LOG_FILENAME,
    ConceptRef,
    LogEntry,
    SubdirRef,
    build_frontmatter,
    document_to_concept,
    folder_to_index,
    folder_to_log,
    render_frontmatter,
)
from app.services.okf.type_mapping import okf_resource, okf_type
from app.services.okf.validator import (
    RECOMMENDED_FRONTMATTER_KEYS,
    REQUIRED_FRONTMATTER_KEYS,
    is_conformant_concept,
    parse_frontmatter,
    validate_bundle,
    validate_concept,
)

__all__ = [
    "INDEX_FILENAME",
    "LOG_FILENAME",
    "ConceptRef",
    "LogEntry",
    "SubdirRef",
    "build_frontmatter",
    "document_to_concept",
    "folder_to_index",
    "folder_to_log",
    "render_frontmatter",
    "okf_resource",
    "okf_type",
    "RECOMMENDED_FRONTMATTER_KEYS",
    "REQUIRED_FRONTMATTER_KEYS",
    "is_conformant_concept",
    "parse_frontmatter",
    "validate_bundle",
    "validate_concept",
]
