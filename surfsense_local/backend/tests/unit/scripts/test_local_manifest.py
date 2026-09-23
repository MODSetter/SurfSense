"""The local manifest is a repo at a commit, read and pinned, never typed."""

import pytest
from local_manifest.assemble import UnreadableBuildError, entry_for, pinned_builds
from local_manifest.entries import ENTRIES, Entry
from local_manifest.guard import losses
from local_manifest.recorded import RepoAtRevision

from modules.llm.catalog.local.builds import ListedFile
from modules.llm.catalog.local.manifest import SCHEMA_VERSION, LocalManifest
from modules.llm.gguf import read_header_prefix
from tests.unit.llm.gguf.build import BOOL, STRING, UINT32, array, gguf, kv, tensor

pytestmark = pytest.mark.unit

REV = "b" * 40
ENTRY = Entry(
    id="gemma-3-4b",
    name="Gemma 3 4B",
    family="Gemma 3",
    publisher="Google",
    description="Small chat model that reads images",
    license="gemma",
    source_repo="google/gemma-3-4b-it",
    repo="unsloth/gemma-3-4b-it-GGUF",
    upstream_repo="google/gemma-3-4b-it",
)


def listed(path: str, size: int, sha: str | None = "c" * 64) -> ListedFile:
    """One listing row, hashed unless a test says otherwise."""
    return ListedFile(path, size, sha)


def snapshot(*files: ListedFile, params=None) -> RepoAtRevision:
    """The recorded repo at one commit."""
    return RepoAtRevision(ENTRY.repo, REV, "image-text-to-text", files, params)


MODEL_HEADER = read_header_prefix(
    gguf(
        [
            kv("general.architecture", STRING, "gemma3"),
            kv("gemma3.block_count", UINT32, 34),
            kv("gemma3.context_length", UINT32, 131072),
            kv("gemma3.embedding_length", UINT32, 2560),
            kv("gemma3.feed_forward_length", UINT32, 10240),
            kv("gemma3.attention.head_count", UINT32, 8),
            kv("gemma3.attention.head_count_kv", UINT32, 4),
            kv("gemma3.attention.key_length", UINT32, 256),
            kv("gemma3.attention.value_length", UINT32, 256),
            kv("tokenizer.chat_template", STRING, "{% if tools %}{% endif %}system"),
            array("tokenizer.ggml.tokens", STRING, ["a", "b"]),
        ],
        [tensor("blk.0.attn_q.weight", [2560, 1_000_000])],
    )
)


def projector_header(width: int = 2560, vision: bool = True):
    """A projector header of a given width."""
    return read_header_prefix(
        gguf(
            [
                kv("general.type", STRING, "mmproj"),
                kv("general.architecture", STRING, "clip"),
                kv("clip.has_vision_encoder", BOOL, vision),
                kv("clip.vision.projection_dim", UINT32, width),
            ]
        )
    )


REPO = snapshot(
    listed("gemma-3-4b-it-Q4_K_M.gguf", 2_490),
    listed("gemma-3-4b-it-UD-Q4_K_XL.gguf", 2_540),
    listed("gemma-3-4b-it-IQ1_S.gguf", 900),
    listed("gemma-3-4b-it-TQ1_0.gguf", 800),
    listed("mmproj-F16.gguf", 850),
    listed("imatrix_unsloth.gguf", 13),
)


def written(snap=REPO, projector=None, validated=None) -> dict:
    """The entry the refresh would write for a repo."""
    builds = pinned_builds(snap)
    return entry_for(
        ENTRY,
        snap,
        builds,
        MODEL_HEADER,
        projector or projector_header(),
        validated or {},
    )


def test_every_build_in_the_preference_order_is_pinned_and_nothing_else() -> None:
    """Every build in the preference order is pinned and nothing else."""
    labels = [b.quantization for b in pinned_builds(REPO)]

    assert labels == ["Q4_K_M", "UD-Q4_K_XL"]


def test_the_entry_validates_against_the_app_schema() -> None:
    """The entry validates against the app schema."""
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "refreshed_at": "2026-09-23",
        "models": [written()],
    }

    (model,) = LocalManifest.model_validate(manifest).models
    assert model.evidence.architecture == "gemma3"
    assert model.context == 131072
    assert model.template.tools is True


def test_the_parameter_count_comes_from_the_tensor_table() -> None:
    """The parameter count comes from the tensor table."""
    assert written()["evidence"]["parameters_b"] == 2.56


def test_a_projector_carries_its_own_gguf_keys() -> None:
    """A projector carries its own gguf keys."""
    projector = written()["builds"][0]["files"][-1]

    assert projector["role"] == "projector"
    assert projector["gguf"]["clip.has_vision_encoder"] is True
    assert projector["revision"] == REV


def test_a_projector_for_another_model_is_refused() -> None:
    """A projector for another model is refused."""
    with pytest.raises(UnreadableBuildError):
        written(projector=projector_header(width=3840))


def test_a_projector_that_cannot_see_is_refused() -> None:
    """A projector that cannot see is refused."""
    with pytest.raises(UnreadableBuildError):
        written(projector=projector_header(vision=False))


def test_a_file_without_a_hash_is_refused() -> None:
    """A file without a hash is refused."""
    with pytest.raises(UnreadableBuildError):
        pinned_builds(snapshot(listed("gemma-3-4b-it-Q4_K_M.gguf", 2_490, sha=None)))


def test_the_publishers_sampling_is_recorded_with_its_origin() -> None:
    """The publishers sampling is recorded with its origin."""
    snap = snapshot(
        listed("gemma-3-4b-it-Q4_K_M.gguf", 2_490),
        params={"temperature": 1.0, "top_k": 64},
    )

    sampling = entry_for(ENTRY, snap, pinned_builds(snap), MODEL_HEADER, None, {})[
        "sampling"
    ]
    assert sampling["origin"] == f"{ENTRY.repo}@{REV}/params"
    assert sampling["non_thinking"] == {"temperature": 1.0, "top_k": 64}


def test_validation_is_recorded_per_build() -> None:
    """Validation is recorded per build."""
    entry = written(validated={"gemma-3-4b-it-UD-Q4_K_XL.gguf": "b6500"})

    assert [b["validated"]["llama_cpp"] for b in entry["builds"]] == [None, "b6500"]


def test_a_refresh_that_drops_a_model_or_build_is_named() -> None:
    """A refresh that drops a model or build is named."""
    before = {
        "models": [
            {
                "id": "a",
                "builds": [{"quantization": "Q4_K_M"}, {"quantization": "Q8_0"}],
            },
            {"id": "b", "builds": []},
        ]
    }
    after = {"models": [{"id": "a", "builds": [{"quantization": "Q4_K_M"}]}]}

    assert losses(before, after) == ["a lost Q8_0", "model b disappeared"]


def test_the_list_is_most_preferred_first() -> None:
    """The list is most preferred first."""
    names = [entry.name for entry in ENTRIES]

    assert names[0] == "Qwen3 32B"
    assert names[-1] == "Qwen3 0.6B"
