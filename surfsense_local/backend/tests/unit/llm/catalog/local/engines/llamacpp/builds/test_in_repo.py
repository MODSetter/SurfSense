"""Which files in a repo make a build, and which quantization each is."""

import pytest

from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import (
    FileRole,
    ListedFile,
    builds_in,
    preferred_projector,
)
from modules.llm.catalog.local.quantization import quantization_label

pytestmark = pytest.mark.unit


def listed(path: str, size: int = 1_000, sha256: str | None = None) -> ListedFile:
    """One listing row, hashed unless a test says otherwise."""
    return ListedFile(path=path, size_bytes=size, sha256=sha256)


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("Qwen3-8B-Q4_K_M.gguf", "Q4_K_M"),
        ("Qwen3-8B-UD-Q4_K_XL.gguf", "UD-Q4_K_XL"),
        ("Qwen3-8B-UD-IQ1_S.gguf", "UD-IQ1_S"),
        ("Qwen3-Coder-30B-A3B-Instruct-UD-TQ1_0.gguf", "UD-TQ1_0"),
        ("gemma-4-E4B-it-BF16.gguf", "BF16"),
        ("BF16/Qwen3-32B-BF16-00001-of-00002.gguf", "BF16"),
        ("Q8_0/model-00001-of-00002.gguf", "Q8_0"),
        ("Qwen3-8B.gguf", "unknown"),
    ],
)
def test_the_label_is_the_quantizers_own_name(path: str, label: str) -> None:
    """`UD-` is kept: the preference order ranks UD-Q4_K_XL above Q4_K_M, and a
    label read as `Q4_K_XL` would never match it."""
    assert quantization_label(path) == label


def test_companions_are_never_offered_as_builds() -> None:
    """Companions are never offered as builds."""
    builds = builds_in(
        [
            listed("Qwen3.8-27B-Q4_K_M.gguf", 16_000),
            listed("imatrix_unsloth.gguf", 13_000),
            listed("MTP/mtp-Qwen3.8-27B-Q4_0.gguf", 1_300),
            listed("Qwen3.8-27B-draft-Q8_0.gguf", 900),
            listed("mmproj-F16.gguf", 600),
            listed("Qwen3.8-27B-Q4_K_M-be.gguf", 16_000),
            listed("README.md", 10),
        ]
    )

    assert [build.quantization for build in builds] == ["Q4_K_M"]


def test_a_split_build_is_every_part_or_nothing() -> None:
    """A split build is every part or nothing."""
    builds = builds_in(
        [
            listed("BF16/Qwen3-32B-BF16-00001-of-00002.gguf", 40),
            listed("BF16/Qwen3-32B-BF16-00002-of-00002.gguf", 25),
            listed("Q8_0/Qwen3-32B-Q8_0-00001-of-00002.gguf", 30),
        ]
    )

    (bf16,) = builds
    assert bf16.quantization == "BF16"
    assert [f.path for f in bf16.files] == [
        "BF16/Qwen3-32B-BF16-00001-of-00002.gguf",
        "BF16/Qwen3-32B-BF16-00002-of-00002.gguf",
    ]
    assert bf16.footprint_bytes == 65


def test_a_folder_that_is_not_a_quantization_is_not_a_build() -> None:
    """A folder that is not a quantization is not a build."""
    builds = builds_in(
        [
            listed("Qwen3-8B-Q4_K_M.gguf"),
            listed("distilled/Qwen3-8B-Q6_K.gguf"),
        ]
    )

    assert [build.quantization for build in builds] == ["Q4_K_M"]


def test_the_root_wins_a_quantization_both_places_hold() -> None:
    """The root wins a quantization both places hold."""
    builds = builds_in(
        [listed("Q4_K_M/Qwen3-8B-Q4_K_M.gguf"), listed("Qwen3-8B-Q4_K_M.gguf")]
    )

    assert [build.weights.path for build in builds] == ["Qwen3-8B-Q4_K_M.gguf"]


def test_every_build_carries_the_preferred_projector() -> None:
    """One projector serves every build of a model, so each build's file set and
    footprint includes it, and the downloader fetches it with the weights."""
    builds = builds_in(
        [
            listed("gemma-4-E4B-it-Q4_K_M.gguf", 4_977, "w1"),
            listed("gemma-4-E4B-it-Q8_0.gguf", 8_000, "w2"),
            listed("mmproj-F32.gguf", 1_912, "p32"),
            listed("mmproj-F16.gguf", 990, "p16"),
            listed("mmproj-BF16.gguf", 991, "pbf"),
        ]
    )

    for build in builds:
        assert build.projector is not None
        assert build.projector.path == "mmproj-F16.gguf"
        assert build.projector.role is FileRole.PROJECTOR
        assert build.footprint_bytes == build.weights.size_bytes + 990


def test_builds_are_listed_smallest_first() -> None:
    """Builds are listed smallest first."""
    builds = builds_in(
        [listed("m-Q8_0.gguf", 8), listed("m-Q2_K.gguf", 2), listed("m-Q4_K_M.gguf", 4)]
    )

    assert [build.quantization for build in builds] == ["Q2_K", "Q4_K_M", "Q8_0"]


def test_a_file_without_a_quantization_is_still_a_build() -> None:
    """A repo of one unlabelled model is a real repo; it has one build."""
    (build,) = builds_in([listed("tiny-model.gguf", 7)])

    assert build.quantization == "unknown"


def test_a_repos_projector_is_found_from_its_names_alone() -> None:
    """The rule the search list and a repo's builds share, so the two never
    disagree about whether a repo reads images."""
    names = [
        listed("gemma-3-4b-it-Q4_K_M.gguf"),
        listed("mmproj-F32.gguf"),
        listed("mmproj-model-f16.gguf"),
        listed("MTP/mmproj-drafter.gguf"),
        listed("imatrix_mmproj.gguf"),
    ]

    found = preferred_projector(names)

    assert found is not None and found.path == "mmproj-model-f16.gguf"
    assert preferred_projector([listed("gemma-3-1b-it-Q4_K_M.gguf")]) is None
