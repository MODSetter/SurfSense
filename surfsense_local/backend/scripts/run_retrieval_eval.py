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
import shutil
import sys
import tempfile
from pathlib import Path

# Before the first import that reads settings, as tests/conftest.py does. The
# ingest job opens its own engine from the configured data dir, so a run that
# left this alone would index into the user's own library: measured, it
# re-parsed the real one. Keep the models where they are, since only the
# database and its documents belong to this run.
_WORK = Path(tempfile.mkdtemp(prefix="retrieval-eval-"))
_REAL = Path(os.environ.get("SURFSENSE_LOCAL_DATA_DIR") or Path.home() / ".surfsense")
os.environ.setdefault("SURFSENSE_LOCAL_MODELS_DIR", str(_REAL / "models"))
os.environ["SURFSENSE_LOCAL_DATA_DIR"] = str(_WORK)

from retrieval_eval.cases import load  # noqa: E402
from retrieval_eval.run import as_record, ask, index  # noqa: E402
from retrieval_eval.summary import summarize  # noqa: E402

from shared.db import import_models  # noqa: E402
from worker.ingestion.embedding import missing_embedding_files  # noqa: E402


def run(args: argparse.Namespace) -> None:
    missing = missing_embedding_files()
    if missing:
        raise ValueError(
            f"the embedding model is missing {missing}; "
            "run scripts/fetch_embedding_model.py"
        )
    corpus = load()
    print(f"{len(corpus.documents)} documents, {len(corpus.queries)} queries")
    session, workspace_id, engine = index(corpus)
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
    finally:
        shutil.rmtree(_WORK, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
