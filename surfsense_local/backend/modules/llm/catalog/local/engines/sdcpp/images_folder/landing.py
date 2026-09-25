"""Where each file of an image build lands in sd-server's folder."""

from modules.llm.catalog.local.build import BuildFile, FileRole

SHARED = "shared"


def landing(file: BuildFile) -> str:
    """Weights keep their own name. A VAE, a text encoder or a projector lands
    once in shared/, prefixed with its hash: several models use the same one,
    and two different files can have the same name."""
    if file.role is FileRole.WEIGHTS or file.sha256 is None:
        return file.name
    return f"{SHARED}/{file.sha256[:12]}-{file.name}"
