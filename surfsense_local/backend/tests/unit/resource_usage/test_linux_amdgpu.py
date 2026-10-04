"""AMD cards on Linux: the card from sysfs, each process's share from DRM fdinfo.

The trees below are what amdgpu populates, built in a temporary directory. The
fd links are injected, because a symlink into /dev needs no privilege on Linux
and does on Windows.
"""

import pytest

from modules.resource_usage.gpu.linux.amdgpu import AmdgpuReader

pytestmark = pytest.mark.unit

GIB = 1024**3
SLOT = "0000:03:00.0"


def card(
    drm,
    index: int,
    *,
    total: int,
    used: int,
    busy: int | None = 7,
    name: str | None = None,
):
    """One amdgpu card in a fake sysfs, with the files the kernel writes."""
    device = drm / f"card{index}" / "device"
    device.mkdir(parents=True)
    (device / "mem_info_vram_total").write_text(f"{total}\n")
    (device / "mem_info_vram_used").write_text(f"{used}\n")
    (device / "slot").write_text(SLOT)
    if busy is not None:
        (device / "gpu_busy_percent").write_text(f"{busy}\n")
    if name is not None:
        (device / "product_name").write_text(f"{name}\n")


def fdinfo(proc, pid: int, fd: int, text: str) -> None:
    """One open descriptor of a process, with its fdinfo text."""
    folder = proc / str(pid) / "fdinfo"
    folder.mkdir(parents=True, exist_ok=True)
    (proc / str(pid) / "fd").mkdir(exist_ok=True)
    (proc / str(pid) / "fd" / str(fd)).write_text("")
    (folder / str(fd)).write_text(text)


def client(client_id: int, vram_kib: int) -> str:
    """fdinfo for a DRM client of the card, holding `vram_kib` of its memory."""
    return (
        "pos:\t0\nflags:\t02100002\n"
        "drm-driver:\tamdgpu\n"
        f"drm-pdev:\t{SLOT}\n"
        f"drm-client-id:\t{client_id}\n"
        f"drm-memory-vram:\t{vram_kib} KiB\n"
        "drm-memory-gtt:\t2048 KiB\n"
    )


def reader(tmp_path, links: dict[str, str]) -> AmdgpuReader:
    """A reader over the fake trees, with fd links and the PCI slot injected."""
    return AmdgpuReader(
        tmp_path / "drm",
        tmp_path / "proc",
        fd_target=lambda path: links.get(
            f"{path.parent.parent.name}/{path.name}", "/dev/null"
        ),
        slot_of=lambda device: (device / "slot").read_text(),
    )


def test_a_card_reads_its_memory_and_busy_figure(tmp_path) -> None:
    """The totals and busy percent come straight from sysfs."""
    card(
        tmp_path / "drm", 0, total=16 * GIB, used=9 * GIB, name="AMD Radeon RX 7800 XT"
    )

    (reading,) = reader(tmp_path, {}).read(set())

    assert reading.name == "AMD Radeon RX 7800 XT"
    assert (reading.total_bytes, reading.used_bytes) == (16 * GIB, 9 * GIB)
    assert reading.busy_percent == 7.0


def test_a_process_share_is_its_drm_clients_on_that_card(tmp_path) -> None:
    """A dup'd descriptor is the same client twice and is counted once."""
    card(tmp_path / "drm", 0, total=16 * GIB, used=9 * GIB)
    proc = tmp_path / "proc"
    fdinfo(proc, 4242, 7, client(12, 4 * 1024 * 1024))
    fdinfo(proc, 4242, 8, client(12, 4 * 1024 * 1024))
    fdinfo(proc, 4242, 9, client(13, 1024 * 1024))
    fdinfo(proc, 4242, 3, "pos:\t0\nflags:\t02\n")
    links = {
        "4242/7": "/dev/dri/renderD128",
        "4242/8": "/dev/dri/renderD128",
        "4242/9": "/dev/dri/card0",
    }

    (reading,) = reader(tmp_path, links).read({4242})

    assert reading.process_bytes == {4242: 5 * GIB}


def test_an_integrated_carve_out_is_not_listed(tmp_path) -> None:
    """A Ryzen APU's BIOS reservation is 512 MB by default."""
    card(tmp_path / "drm", 0, total=512 * 1024**2, used=300 * 1024**2)

    assert reader(tmp_path, {}).read(set()) == []


def test_connectors_and_render_nodes_are_not_cards(tmp_path) -> None:
    """card0-DP-1 is a display connector; only cardN is a device."""
    drm = tmp_path / "drm"
    card(drm, 0, total=16 * GIB, used=GIB)
    (drm / "card0-DP-1").mkdir()
    (drm / "renderD128").mkdir()

    assert len(reader(tmp_path, {}).read(set())) == 1


def test_a_card_without_a_busy_file_reads_unknown(tmp_path) -> None:
    """Older kernels have no gpu_busy_percent, and no product_name either."""
    card(tmp_path / "drm", 0, total=16 * GIB, used=GIB, busy=None)

    (reading,) = reader(tmp_path, {}).read(set())

    assert reading.busy_percent is None
    assert reading.name == "AMD GPU"
