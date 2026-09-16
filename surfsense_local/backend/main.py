import sys

from api.server import serve


def check_retrieval_runtime() -> None:
    """Fail fast when a frozen API dropped retrieval's lazy imports.

    Chat retrieval reaches numpy, tokenizers, and onnxruntime only on the first
    query, so a spec that excludes too much still boots and answers /health.
    """
    import onnxruntime
    from tokenizers import Tokenizer

    # The first-query entry point, imported the way retrieval reaches it: this
    # walks worker.ingestion's package init through chonkie, whose optional
    # transformers and pandas imports are what api.spec excludes.
    from worker.ingestion.embedding import embed

    sys.stdout.write(
        f"retrieval imports OK (onnxruntime {onnxruntime.__version__}, "
        f"{Tokenizer.__name__}, {embed.__name__})\n"
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--check-retrieval-runtime"]:
        check_retrieval_runtime()
    else:
        serve()
