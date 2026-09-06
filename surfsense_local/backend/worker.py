import sys

from worker.consumer import consume


def check_vision_runtime() -> None:
    """Fail fast when a frozen worker dropped Docling's lazy vision imports."""
    import torchvision
    from transformers import AutoImageProcessor

    sys.stdout.write(
        f"vision imports OK ({AutoImageProcessor.__name__}, "
        f"torchvision {torchvision.__version__})\n"
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--check-vision-runtime"]:
        check_vision_runtime()
    else:
        consume()
