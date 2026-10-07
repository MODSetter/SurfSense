"""Turn a verified upstream file into an install root, by how TDF packaged it."""

from pathlib import Path

from modules.runtime_packs.office.pin import Packaging


def unpack(packaging: Packaging, upstream: Path, into: Path) -> Path:
    """Unpack into the folder `into` and return the install root inside it."""
    if packaging is Packaging.WINDOWS_MSI:
        from modules.runtime_packs.office.unpack.windows_msi import unpack_msi

        return unpack_msi(upstream, into)
    if packaging is Packaging.MACOS_DMG:
        from modules.runtime_packs.office.unpack.macos_dmg import unpack_dmg

        return unpack_dmg(upstream, into)
    from modules.runtime_packs.office.unpack.linux_debs import unpack_debs

    return unpack_debs(upstream, into)
