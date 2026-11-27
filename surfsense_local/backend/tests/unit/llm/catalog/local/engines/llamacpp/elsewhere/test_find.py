"""Finding the chat models other apps downloaded, in each app's own layout.

Every folder here is built in tmp_path the way its app writes it. What is found
is read from each file's header, so a projector, an embedder or a format the
bundled runtime cannot load is never offered as something to chat with; files
are only read, never written.
"""

import os
from pathlib import Path

import pytest

from modules.llm.catalog.local.engines.llamacpp.elsewhere import tree as tree_module
from modules.llm.catalog.local.engines.llamacpp.elsewhere.candidate import Candidate
from modules.llm.catalog.local.engines.llamacpp.elsewhere.find import (
    find_models,
    judge,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import (
    App,
    Layout,
    Place,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.runs_here import (
    UnusableCode,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.tree import in_tree
from tests.unit.llm.catalog.local.engines.llamacpp.elsewhere.files import (
    chat_model_bytes,
    ollama_store,
    write_chat_model,
    write_embedder,
    write_projector,
)
from tests.unit.llm.gguf.build import STRING, UINT32, kv

pytestmark = pytest.mark.unit


def _ollama(root: Path) -> Place:
    return Place(App.OLLAMA, root, Layout.OLLAMA)


def _tree(app: App, root: Path, depth: int = 3) -> Place:
    return Place(app, root, Layout.TREE, depth=depth)


def _hub(root: Path) -> Place:
    return Place(App.HUGGING_FACE, root, Layout.HUB_CACHE)


def _snapshot(hub: Path, repo: str, commit: str = "a" * 40) -> Path:
    org, name = repo.split("/")
    folder = hub / f"models--{org}--{name}"
    (folder / "refs").mkdir(parents=True, exist_ok=True)
    snapshot = folder / "snapshots" / commit
    snapshot.mkdir(parents=True, exist_ok=True)
    return snapshot


# Ollama ---------------------------------------------------------------------


def test_an_ollama_model_is_found_by_the_tag_its_user_pulled(tmp_path: Path) -> None:
    """The manifest names the blob, and the tag is what a person would look for."""
    blob, _ = ollama_store(tmp_path, "qwen3", "8b", chat_model_bytes())

    found = find_models([_ollama(tmp_path)]).models

    assert [(m.app, m.label.name, m.path) for m in found] == [
        (App.OLLAMA, "qwen3:8b", blob)
    ]
    assert found[0].label.quantization == "Q4_K_M"
    assert found[0].weights_bytes == blob.stat().st_size


def test_ollama_names_a_users_model_and_a_hub_pull_as_ollama_does(
    tmp_path: Path,
) -> None:
    """A namespaced model keeps its namespace, and a hub pull its host, as `ollama list` shows."""
    ollama_store(
        tmp_path, "mymodel", "latest", chat_model_bytes(name="A"), namespace="ana"
    )
    ollama_store(
        tmp_path,
        "Qwen3-8B-GGUF",
        "Q4_K_M",
        chat_model_bytes(name="B"),
        host="hf.co",
        namespace="unsloth",
    )

    names = sorted(m.label.name for m in find_models([_ollama(tmp_path)]).models)

    assert names == ["ana/mymodel:latest", "hf.co/unsloth/Qwen3-8B-GGUF:Q4_K_M"]


def test_two_tags_of_one_blob_are_one_model_named_by_the_specific_tag(
    tmp_path: Path,
) -> None:
    """`latest` and `8b` naming one blob are one model, called by the tag that says which."""
    model = chat_model_bytes()
    ollama_store(tmp_path, "qwen3", "latest", model)
    ollama_store(tmp_path, "qwen3", "8b", model)

    found = find_models([_ollama(tmp_path)]).models

    assert [m.label.name for m in found] == ["qwen3:8b"]


def test_an_ollama_projector_layer_is_paired_as_ollama_recorded_it(
    tmp_path: Path,
) -> None:
    """A vision model's projector layer is the projector, as Ollama itself pairs them."""
    projector_file = write_projector(tmp_path / "p.gguf", width=4096)
    _, projector = ollama_store(
        tmp_path / "ollama",
        "llava",
        "7b",
        chat_model_bytes(architecture="llama", embedding=4096),
        projector=projector_file.read_bytes(),
    )

    (found,) = find_models([_ollama(tmp_path / "ollama")]).models

    assert found.projector == projector


def test_an_ollama_manifest_whose_blob_is_gone_is_not_offered(tmp_path: Path) -> None:
    """A manifest whose blob was pruned, or that is not JSON, is passed over quietly."""
    blob, _ = ollama_store(tmp_path, "qwen3", "8b", chat_model_bytes())
    blob.unlink()
    (tmp_path / "manifests" / "registry.ollama.ai" / "library" / "x").mkdir()
    (tmp_path / "manifests" / "registry.ollama.ai" / "library" / "x" / "1").write_text(
        "not json"
    )

    finding = find_models([_ollama(tmp_path)])

    assert finding.models == ()
    assert finding.skipped == ()


def test_ollamas_own_formats_are_reported_and_not_offered(tmp_path: Path) -> None:
    """Architectures named Ollama's way and vision inside the weights are said, not offered."""
    ollama_store(tmp_path, "gpt-oss", "20b", chat_model_bytes(architecture="gptoss"))
    ollama_store(
        tmp_path,
        "gemma3",
        "4b",
        chat_model_bytes(
            architecture="gemma3",
            tensors=[
                ("token_embd.weight", [4096, 3]),
                ("v.blk.0.attn_q.weight", [8, 8]),
            ],
        ),
    )

    finding = find_models([_ollama(tmp_path)])

    assert finding.models == ()
    assert sorted((s.name, s.unusable.code) for s in finding.skipped) == [
        ("gemma3:4b", UnusableCode.VISION_INSIDE),
        ("gpt-oss:20b", UnusableCode.UNKNOWN_ARCHITECTURE),
    ]


# LM Studio ------------------------------------------------------------------


def test_an_lm_studio_model_is_found_with_the_projector_in_its_folder(
    tmp_path: Path,
) -> None:
    """A publisher/repo folder gives its projector to the build beside it."""
    repo = tmp_path / "lmstudio-community" / "gemma-3-4b-it-GGUF"
    model = write_chat_model(
        repo / "gemma-3-4b-it-Q4_K_M.gguf", architecture="gemma3", embedding=2560
    )
    projector = write_projector(repo / "mmproj-model-f16.gguf", width=2560)

    (found,) = find_models([_tree(App.LM_STUDIO, tmp_path)]).models

    assert (found.app, found.path, found.projector) == (App.LM_STUDIO, model, projector)
    assert found.source == "lmstudio-community/gemma-3-4b-it-GGUF"


def test_a_projector_for_another_width_is_not_paired(tmp_path: Path) -> None:
    """A projector whose header names another model's width stays unpaired."""
    repo = tmp_path / "pub" / "repo"
    write_chat_model(repo / "model-Q4_K_M.gguf", embedding=4096)
    write_projector(repo / "mmproj-f16.gguf", width=2560)

    (found,) = find_models([_tree(App.LM_STUDIO, tmp_path)]).models

    assert found.projector is None


# Hugging Face cache -----------------------------------------------------------


def test_a_hugging_face_download_is_found_under_its_repo(tmp_path: Path) -> None:
    """A hub snapshot's model and projector are found, named for their repo."""
    snapshot = _snapshot(tmp_path, "unsloth/Qwen3.5-4B-GGUF")
    model = write_chat_model(
        snapshot / "Qwen3.5-4B-UD-Q4_K_XL.gguf", architecture="qwen35", embedding=2560
    )
    projector = write_projector(snapshot / "mmproj-F16.gguf", width=2560)

    (found,) = find_models([_hub(tmp_path)]).models

    assert (found.app, found.path, found.projector) == (
        App.HUGGING_FACE,
        model,
        projector,
    )
    assert found.source == "unsloth/Qwen3.5-4B-GGUF"
    assert found.label.quantization == "UD-Q4_K_XL"


def test_the_hub_cache_offers_the_revision_its_main_ref_names(tmp_path: Path) -> None:
    """Only the commit `refs/main` names is offered, not every older snapshot."""
    old = _snapshot(tmp_path, "unsloth/Qwen3-8B-GGUF", "1" * 40)
    new = _snapshot(tmp_path, "unsloth/Qwen3-8B-GGUF", "2" * 40)
    write_chat_model(old / "Qwen3-8B-Q4_K_M.gguf")
    current = write_chat_model(new / "Qwen3-8B-Q4_K_M.gguf")
    (tmp_path / "models--unsloth--Qwen3-8B-GGUF" / "refs" / "main").write_text("2" * 40)

    assert [m.path for m in find_models([_hub(tmp_path)]).models] == [current]


@pytest.mark.skipif(
    os.name == "nt", reason="symlinks need a privilege Windows rarely grants"
)
def test_a_hub_file_linked_to_its_blob_is_found_once(tmp_path: Path) -> None:
    """A snapshot file symlinked into blobs is one model, found by its snapshot path."""
    folder = tmp_path / "models--unsloth--Qwen3-8B-GGUF"
    blob = write_chat_model(folder / "blobs" / ("f" * 64))
    snapshot = _snapshot(tmp_path, "unsloth/Qwen3-8B-GGUF")
    (snapshot / "Qwen3-8B-Q4_K_M.gguf").symlink_to(blob)

    found = find_models([_hub(tmp_path)]).models

    assert [m.path for m in found] == [snapshot / "Qwen3-8B-Q4_K_M.gguf"]


# llama.cpp, Jan, GPT4All and an added folder ------------------------------------


def test_a_model_llama_cpp_saved_in_its_old_cache_is_found(tmp_path: Path) -> None:
    """A flat file in llama.cpp's own older cache is found."""
    model = write_chat_model(tmp_path / "unsloth_Qwen3-8B-GGUF_Qwen3-8B-Q4_K_M.gguf")

    found = find_models([_tree(App.LLAMA_CPP, tmp_path, depth=1)]).models

    assert [(m.app, m.path) for m in found] == [(App.LLAMA_CPP, model)]


def test_a_jan_model_is_found_and_its_embedder_is_reported(tmp_path: Path) -> None:
    """Jan's chat model is named by its folder; its embedder is said and not offered."""
    model = write_chat_model(tmp_path / "Jan-v3.5-4B-Q4_K_XL" / "model.gguf", name=None)
    write_embedder(tmp_path / "sentence-transformer-mini" / "model.gguf")

    finding = find_models([_tree(App.JAN, tmp_path, depth=2)])

    assert [(m.path, m.label.name) for m in finding.models] == [
        (model, "Jan-v3.5-4B-Q4_K_XL")
    ]
    assert [(s.name, s.unusable.code) for s in finding.skipped] == [
        ("all-MiniLM-L6-v2", "embedder")
    ]


def test_a_gpt4all_model_is_found_in_its_flat_folder(tmp_path: Path) -> None:
    """A GGUF in GPT4All's folder is found."""
    model = write_chat_model(
        tmp_path / "Llama-3.2-3B-Instruct-Q4_0.gguf", architecture="llama"
    )

    found = find_models([_tree(App.GPT4ALL, tmp_path, depth=1)]).models

    assert [(m.app, m.path) for m in found] == [(App.GPT4ALL, model)]


def test_an_added_folder_is_read_as_deep_as_its_place_allows(tmp_path: Path) -> None:
    """A tree is read to its depth and never into a hidden folder."""
    shallow = write_chat_model(tmp_path / "a" / "b" / "shallow-Q4_K_M.gguf")
    write_chat_model(tmp_path / "a" / "b" / "c" / "d" / "deep-Q4_K_M.gguf")
    write_chat_model(tmp_path / ".hidden" / "secret-Q4_K_M.gguf")

    found = find_models([_tree(App.FOLDER, tmp_path, depth=3)]).models

    assert [m.path for m in found] == [shallow]


# Every place --------------------------------------------------------------------


def test_surfsenses_own_models_folder_is_never_offered_back(tmp_path: Path) -> None:
    """SurfSense's own folder is listed already, so it is never found again."""
    # Not a hidden folder, which a tree would pass over anyway: a moved one.
    own = tmp_path / "SurfSense" / "models"
    write_chat_model(own / "Qwen3-8B-UD-Q4_K_XL.gguf")

    finding = find_models([_tree(App.FOLDER, tmp_path, depth=4)], exclude=[own])

    assert finding.models == ()


def test_one_file_reached_from_two_places_is_one_model(tmp_path: Path) -> None:
    """The same file reached through two places is found once, by the first."""
    model = write_chat_model(tmp_path / "pub" / "repo" / "m-Q4_K_M.gguf")

    found = find_models(
        [_tree(App.LM_STUDIO, tmp_path), _tree(App.FOLDER, tmp_path / "pub")]
    ).models

    assert [(m.app, m.path) for m in found] == [(App.LM_STUDIO, model)]


def test_a_split_build_is_one_model_of_every_part(tmp_path: Path) -> None:
    """A split build is offered from its first part, sized by all of them."""
    first = write_chat_model(tmp_path / "big-Q4_K_M-00001-of-00002.gguf", split=(0, 2))
    second = write_chat_model(tmp_path / "big-Q4_K_M-00002-of-00002.gguf", split=(1, 2))

    (found,) = find_models([_tree(App.FOLDER, tmp_path)]).models

    assert (found.path, found.parts) == (first, (first, second))
    assert found.weights_bytes == first.stat().st_size + second.stat().st_size


def test_a_split_build_missing_a_part_is_reported(tmp_path: Path) -> None:
    """A split build with a part missing would not load, so it is said and not offered."""
    write_chat_model(tmp_path / "big-Q4_K_M-00001-of-00003.gguf", split=(0, 3))
    write_chat_model(tmp_path / "big-Q4_K_M-00002-of-00003.gguf", split=(1, 3))

    finding = find_models([_tree(App.FOLDER, tmp_path)])

    assert finding.models == ()
    assert [s.unusable.code for s in finding.skipped] == [UnusableCode.MISSING_PARTS]


def test_a_file_whose_path_the_runtime_cannot_be_given_is_reported(
    tmp_path: Path,
) -> None:
    """A path the preset would cut at `#` is said and not offered."""
    write_chat_model(tmp_path / "models #2" / "m-Q4_K_M.gguf")

    finding = find_models([_tree(App.FOLDER, tmp_path)])

    assert finding.models == ()
    assert [s.unusable.code for s in finding.skipped] == [UnusableCode.PATH]


def test_a_file_that_is_not_a_gguf_is_passed_over_quietly(tmp_path: Path) -> None:
    """A file that only ends in .gguf is not a model, and not worth a line."""
    (tmp_path / "half-downloaded.gguf").write_bytes(b"GGUF\x03\x00")
    (tmp_path / "notes.gguf").write_text("hello")

    finding = find_models([_tree(App.FOLDER, tmp_path)])

    assert (finding.models, finding.skipped) == ((), ())


def test_a_place_that_does_not_exist_finds_nothing(tmp_path: Path) -> None:
    """An app that is not installed costs nothing and reports nothing."""
    finding = find_models(
        [
            _ollama(tmp_path / "nope"),
            _hub(tmp_path / "nope"),
            _tree(App.JAN, tmp_path / "nope"),
        ]
    )

    assert (finding.models, finding.skipped) == ((), ())


def test_finding_changes_nothing_on_disk(tmp_path: Path) -> None:
    """Looking writes nothing: every file and folder keeps its size and time."""
    ollama_store(tmp_path / "ollama", "qwen3", "8b", chat_model_bytes())
    snapshot = _snapshot(tmp_path / "hub", "unsloth/Qwen3-8B-GGUF")
    write_chat_model(snapshot / "Qwen3-8B-Q4_K_M.gguf")
    before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob("*")}

    find_models([_ollama(tmp_path / "ollama"), _hub(tmp_path / "hub")])

    after = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob("*")}
    assert after == before


# Files no reader expected ----------------------------------------------------------


def test_one_malformed_header_costs_that_file_and_not_the_scan(tmp_path: Path) -> None:
    """A value of the wrong type anywhere in one header must not stop the others
    being found: that file is unreadable, and passed over like any other."""
    good = write_chat_model(tmp_path / "good-Q4_K_M.gguf")
    (tmp_path / "bad-shape-Q4_K_M.gguf").write_bytes(
        chat_model_bytes(block_count=kv("qwen3.block_count", STRING, "many"))
    )
    (tmp_path / "bad-part-Q4_K_M.gguf").write_bytes(
        chat_model_bytes(
            extra=[kv("split.no", STRING, "first"), kv("split.count", UINT32, 2)]
        )
    )

    finding = find_models([_tree(App.FOLDER, tmp_path)])

    assert [m.path for m in finding.models] == [good]


def test_a_file_that_trips_the_reader_is_judged_unreadable(tmp_path: Path) -> None:
    """What a pick of the same file is refused with."""
    bad = tmp_path / "bad-Q4_K_M.gguf"
    bad.write_bytes(chat_model_bytes(block_count=kv("qwen3.block_count", STRING, "x")))

    outcome = judge(Candidate(App.FOLDER, bad, (bad,)))

    assert outcome.unusable.code is UnusableCode.UNREADABLE


# Every part of a split ---------------------------------------------------------------


def test_a_split_saved_under_one_file_name_is_reported_with_parts_missing(
    tmp_path: Path,
) -> None:
    """llama.cpp finds a split's other parts by their names, so a first part
    saved as `model.gguf` cannot load whatever sits beside it."""
    write_chat_model(tmp_path / "model.gguf", split=(0, 2))

    finding = find_models([_tree(App.FOLDER, tmp_path)])

    assert finding.models == ()
    assert [s.unusable.code for s in finding.skipped] == [UnusableCode.MISSING_PARTS]


def test_a_split_whose_names_count_fewer_parts_than_its_header_is_reported(
    tmp_path: Path,
) -> None:
    """The header is the authority on how many parts there are."""
    write_chat_model(tmp_path / "big-Q4_K_M-00001-of-00002.gguf", split=(0, 3))
    write_chat_model(tmp_path / "big-Q4_K_M-00002-of-00002.gguf", split=(1, 3))

    finding = find_models([_tree(App.FOLDER, tmp_path)])

    assert finding.models == ()
    assert [s.unusable.code for s in finding.skipped] == [UnusableCode.MISSING_PARTS]


def test_a_part_gone_since_the_listing_makes_the_split_missing(tmp_path: Path) -> None:
    """Judged again before use, a split whose later part was deleted is refused."""
    write_chat_model(tmp_path / "big-Q4_K_M-00001-of-00002.gguf", split=(0, 2))
    second = write_chat_model(tmp_path / "big-Q4_K_M-00002-of-00002.gguf", split=(1, 2))
    (found,) = find_models([_tree(App.FOLDER, tmp_path)]).models
    second.unlink()

    outcome = judge(Candidate(found.app, found.path, found.parts))

    assert outcome.unusable.code is UnusableCode.MISSING_PARTS


# The entry budget ----------------------------------------------------------------------


def test_a_model_read_before_the_budget_ran_out_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The walk stops at its budget, but keeps what it had already read."""
    monkeypatch.setattr(tree_module, "_MOST_ENTRIES", 6)
    model = write_chat_model(tmp_path / "a-Q4_K_M.gguf")
    for n in range(6):
        (tmp_path / f"note-{n}.txt").write_text("x")

    assert [c.path for c in in_tree(tmp_path, App.FOLDER, depth=0)] == [model]


def test_a_huge_folder_is_listed_no_further_than_the_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder a person adds may be a whole drive: entries past the budget are
    never read, let alone held and sorted."""
    monkeypatch.setattr(tree_module, "_MOST_ENTRIES", 5)
    for n in range(50):
        (tmp_path / f"f{n:02}.txt").write_text("x")
    listed: list[str] = []
    real_scandir = os.scandir

    class Counted:
        def __init__(self, path: str) -> None:
            self._listing = real_scandir(path)

        def __enter__(self) -> "Counted":
            return self

        def __exit__(self, *_: object) -> None:
            self._listing.close()

        def __iter__(self):
            for entry in self._listing:
                listed.append(entry.name)
                yield entry

    monkeypatch.setattr(tree_module.os, "scandir", Counted)

    in_tree(tmp_path, App.FOLDER, depth=0)

    assert len(listed) <= 6
