import sys


def check_vision_runtime() -> None:
    """Fail fast when a frozen worker dropped Docling's lazy vision imports."""
    import torchvision
    from transformers import AutoImageProcessor

    sys.stdout.write(
        f"vision imports OK ({AutoImageProcessor.__name__}, "
        f"torchvision {torchvision.__version__})\n"
    )


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    if sys.argv[1:] == ["--check-vision-runtime"]:
        check_vision_runtime()
    elif len(sys.argv) == 3 and sys.argv[1] == "--run-document-script":
        # Ahead of the consumer's imports: a script process loads no queue,
        # database or settings.
        from worker.document_script.child import main

        main(sys.argv[2])
    elif len(sys.argv) == 2:
        from worker.consumer import consume

        consume(sys.argv[1])
    else:
        sys.exit("usage: worker.py <ingest|studio|plugins>")
