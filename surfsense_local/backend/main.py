import sys

from api.server import serve


def check_retrieval_runtime() -> None:
    """Fail fast when a frozen API dropped retrieval's lazy imports.

    Chat retrieval reaches numpy, tokenizers, and onnxruntime only on the first
    query, so a spec that excludes too much still boots and answers /health.
    """
    import onnxruntime
    from tokenizers import Tokenizer

    # The first-query entry point, imported the way retrieval reaches it.
    from modules.embedding.encoder import embed

    sys.stdout.write(
        f"retrieval imports OK (onnxruntime {onnxruntime.__version__}, "
        f"{Tokenizer.__name__}, {embed.__name__})\n"
    )


def probe_devices(library_dir: str) -> int:
    """List this machine's ggml devices, one per line, and exit.

    The frozen build has no interpreter to run `-m` with, so the device probe
    re-executes this binary behind this flag. Losing it does not break anything
    visibly: the parent falls back to probing in process and the answer stays
    correct, while a GPU driver moves back into the API process and, on a Mac,
    a 19 second shader compile with it.
    """
    from modules.llm.hardware.probe_script import main

    return main([library_dir])


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments == ["--check-retrieval-runtime"]:
        check_retrieval_runtime()
    elif arguments[:1] == ["--probe-devices"]:
        # Matched on the flag rather than on the whole shape, so a malformed
        # probe is an error instead of falling through and starting a server
        # that nothing is waiting on and nothing will stop.
        if len(arguments) != 2:
            sys.stderr.write("usage: --probe-devices <library-dir>\n")
            sys.exit(2)
        sys.exit(probe_devices(arguments[1]))
    elif arguments == ["--going-back-options"]:
        from shared.going_back.command_line import print_options

        sys.exit(print_options())
    elif arguments[:1] == ["--go-back"]:
        # Matched on the flag, as above: a malformed one must not start a server.
        if arguments[1:] not in (["undo"], ["restore"]):
            sys.stderr.write("usage: --go-back <undo|restore>\n")
            sys.exit(2)
        from shared.going_back.command_line import go_back

        sys.exit(go_back(arguments[1]))
    else:
        serve()
