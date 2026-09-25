"""Measure what retrieval puts in front of the model, so a change to it is measured.

The chat eval hands the model its passages; this one exercises `retrieve()`
itself. It indexes a fixed corpus the way a user's library is indexed, asks
every query, and records where the answering passage landed.

    uv run scripts/run_retrieval_eval.py run --out ../../.progress/retrieval/baseline.jsonl
    uv run scripts/run_retrieval_eval.py summary <result files>

Needs the embedding model on disk: `uv run scripts/fetch_embedding_model.py`.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from retrieval_eval.cases import CORPUS_DIR, LOCAL_DIR
from retrieval_eval.fingerprint import embedder_identity, fingerprint

# Deliberately not imported from worker.ingestion.embedding, even though that
# is where it is defined: importing anything under `worker` pulls in
# shared.queue, which reads the settings at import time and caches them. That
# would freeze the data dir below before it is set, and the run would read the
# user's own library instead. Measured twice.
MODEL_DIR_NAME = "bge-small-en-v1.5"

# Before the first import that reads settings, as tests/conftest.py does. The
# ingest job opens its own engine from the configured data dir, so a run that
# left this alone would index into the user's own library: measured, it
# re-parsed the real one. The models stay where they are; only the database and
# its documents belong to this run.
_REAL = Path(os.environ.get("SURFSENSE_LOCAL_DATA_DIR") or Path.home() / ".surfsense")
os.environ.setdefault("SURFSENSE_LOCAL_MODELS_DIR", str(_REAL / "models"))
# Keyed by what was indexed, so a ranking change reuses the index and only a
# corpus or embedder change pays to build one.
CACHE_ROOT = Path.home() / ".surfsense-retrieval-eval"
_KEY = fingerprint(
    CORPUS_DIR,
    LOCAL_DIR / "corpus",
    embedder=embedder_identity(
        Path(os.environ["SURFSENSE_LOCAL_MODELS_DIR"]), MODEL_DIR_NAME
    ),
)
os.environ["SURFSENSE_LOCAL_DATA_DIR"] = str(CACHE_ROOT / _KEY)

from retrieval_eval.cases import load  # noqa: E402
from retrieval_eval.run import as_record, ask, index, open_index  # noqa: E402
from retrieval_eval.summary import summarize  # noqa: E402

from shared.config import get_storage_settings  # noqa: E402
from shared.db import import_models  # noqa: E402
from worker.ingestion.embedding import missing_embedding_files  # noqa: E402


def guard_data_dir() -> None:
    """Refuse to run against anything but this run's own directory.

    The settings are cached on first read, so an import added above these lines
    silently freezes the data dir at the default and points the whole run at
    the user's library. That has happened twice; this turns it into a failure
    rather than a puzzling score.
    """
    resolved = get_storage_settings().data_dir
    expected = CACHE_ROOT / _KEY
    if resolved != expected:
        raise ValueError(
            f"settings resolved the data dir to {resolved}, not {expected}; "
            "something imported above set it too early"
        )


def run(args: argparse.Namespace) -> None:
    guard_data_dir()
    missing = missing_embedding_files()
    if missing:
        raise ValueError(
            f"the embedding model is missing {missing}; "
            "run scripts/fetch_embedding_model.py"
        )
    corpus = load()
    print(f"{len(corpus.documents)} documents, {len(corpus.queries)} queries")
    opened = None if args.rebuild else open_index()
    if opened is None:
        print(f"indexing into {CACHE_ROOT / _KEY}")
        opened = index(corpus)
    else:
        print(f"reusing the index in {CACHE_ROOT / _KEY}")
    session, workspace_id, engine = opened
    try:
        results = ask(session, workspace_id, corpus)
    finally:
        session.close()
        engine.dispose()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for result in results:
            out.write(json.dumps(as_record(result), ensure_ascii=False) + "\n")
    for result in results:
        rank = result.ranking.rank
        print(f"  {result.query:34} {'rank ' + str(rank) if rank else 'not found'}")
    print()
    print(summarize([args.out]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    run_command = commands.add_parser(
        "run", help="index the corpus and ask every query"
    )
    run_command.add_argument(
        "--out", type=Path, required=True, help="one JSON line per query"
    )
    run_command.add_argument(
        "--rebuild",
        action="store_true",
        help="index again even though this corpus and embedder were indexed before",
    )

    summary_command = commands.add_parser("summary", help="compare result files")
    summary_command.add_argument("files", type=Path, nargs="+")

    args = parser.parse_args()
    if args.command == "summary":
        print(summarize(args.files))
        return 0
    # The corpus is indexed as documents, which map only once every model does.
    import_models()
    try:
        run(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
