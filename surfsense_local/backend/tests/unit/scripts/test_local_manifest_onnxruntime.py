"""An embedding model's manifest entry: its weights and tokenizer pinned from the
repo at a commit, and what its index needs from the reviewed entry."""

import pytest
from local_manifest.onnxruntime.assemble import entry_for, pinned_builds
from local_manifest.onnxruntime.entry import EmbeddingEntry
from local_manifest.recorded import RepoAtRevision
from local_manifest.unreadable import UnreadableBuildError

from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.catalog.local.manifest import SCHEMA_VERSION, LocalManifest

pytestmark = pytest.mark.unit

# onnx-community/granite-embedding-97m-multilingual-r2-ONNX, read on 1 Oct 2026.
REV = "536a9f241cb3f02a9c5995a1e708c784bd274859"
ENTRY = EmbeddingEntry(
    id="granite-embedding-97m-multilingual-r2",
    name="Granite Embedding 97M Multilingual",
    family="Granite Embedding",
    publisher="IBM",
    description="Search across more than 50 languages.",
    license="apache-2.0",
    source_repo="ibm-granite/granite-embedding-97m-multilingual-r2",
    repo="onnx-community/granite-embedding-97m-multilingual-r2-ONNX",
    builds=(("F32", "onnx/model.onnx"),),
    embedding={
        "dimension": 384,
        "pooling": "cls",
        "normalize": True,
        "max_tokens": 512,
        "semantic_weight": 0.85,
        "batch": 32,
    },
)
SNAPSHOT = RepoAtRevision(
    ENTRY.repo,
    REV,
    "feature-extraction",
    (
        ListedFile(
            "onnx/model.onnx",
            390004608,
            "68e592b160673d30250824c1116bc6ab33f70efb22b97c9e1d7ce1e69c1c9d70",
        ),
        ListedFile(
            "onnx/model_int8.onnx",
            97858099,
            "704c1ebca5fbb7cd83ced41827658ac4c9990c64f7f2874d22b78044e5022e22",
        ),
        ListedFile(
            "tokenizer.json",
            25301671,
            "51947676cae1f991fa51c6b9a24e14ee5460e5f0b9f692f13bb3159829d1592a",
        ),
        ListedFile("config.json", 1215, None),
    ),
    None,
)


def test_a_build_is_its_weights_and_the_repos_tokenizer() -> None:
    """The entry names the weights; the tokenizer is the repo's own."""
    (build,) = pinned_builds(ENTRY, SNAPSHOT)

    assert [(f.role.value, f.path) for f in build.files] == [
        ("weights", "onnx/model.onnx"),
        ("tokenizer", "tokenizer.json"),
    ]
    assert all(f.revision == REV and f.sha256 for f in build.files)


def test_a_file_the_listing_does_not_hash_is_refused() -> None:
    """A download it cannot check would be trusted blind."""
    unhashed = RepoAtRevision(
        SNAPSHOT.repo,
        REV,
        SNAPSHOT.pipeline_tag,
        tuple(
            ListedFile(f.path, f.size_bytes, None) if f.path == "tokenizer.json" else f
            for f in SNAPSHOT.listing
        ),
        None,
    )

    with pytest.raises(UnreadableBuildError):
        pinned_builds(ENTRY, unhashed)


def test_the_written_entry_loads_as_an_embedding_model() -> None:
    """The architecture is the repo's config's, the rest the reviewed entry's."""
    written = entry_for(ENTRY, SNAPSHOT, pinned_builds(ENTRY, SNAPSHOT), "modernbert")

    manifest = LocalManifest.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "refreshed_at": "2026-10-01",
            "models": [written],
        }
    )
    (model,) = manifest.models
    assert model.evidence.architecture == "modernbert"
    assert model.embedding is not None
    assert model.embedding.semantic_weight == 0.85
