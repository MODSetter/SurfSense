"""Ask ggml what this machine has.

**The scan runs from the directory of the running executable, not the directory
the libraries were loaded from.** Verified on a machine with a working RTX 3050,
same process otherwise: run from elsewhere it reports zero devices, run from the
library directory it reports two. Loading by absolute path does not help, and
`GGML_BACKEND_PATH` is not an escape hatch because it expects a file.

The failure is silent and indistinguishable from a genuinely GPU-less machine,
so the working directory is set around the call rather than assumed.
"""

import ctypes
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from modules.llm.hardware.devices import Device, DeviceType
from modules.llm.hardware.libraries import load

# chdir is process-global. The probe runs once at startup and its result is
# cached, so the window is short, but it still has to be exclusive.
_CWD_LOCK = threading.Lock()


@contextmanager
def _working_directory(directory: Path):
    with _CWD_LOCK:
        previous = Path.cwd()
        os.chdir(directory)
        try:
            yield
        finally:
            os.chdir(previous)


def probe_devices(library_dir: Path) -> list[Device]:
    """Every device ggml can see, in ggml's own preference order.

    An empty list means ggml found nothing, which is not the same as the machine
    having nothing. `gpu_crosscheck` is what tells those apart.
    """
    libraries = load(library_dir)
    with _working_directory(library_dir):
        libraries.core.ggml_backend_load_all()
        # The Metal shader compile happens here, not in load_all: measured at
        # 19 s cold and about 45 ms warm on an M2. Warm this call, not that one.
        count = libraries.core.ggml_backend_dev_count()

        devices = []
        for index in range(count):
            handle = libraries.core.ggml_backend_dev_get(index)
            free, total = ctypes.c_size_t(), ctypes.c_size_t()
            libraries.base.ggml_backend_dev_memory(
                handle, ctypes.byref(free), ctypes.byref(total)
            )
            devices.append(
                Device(
                    name=libraries.base.ggml_backend_dev_name(handle).decode(),
                    description=libraries.base.ggml_backend_dev_description(
                        handle
                    ).decode(),
                    type=DeviceType.parse(libraries.base.ggml_backend_dev_type(handle)),
                    total_bytes=total.value,
                    free_bytes=free.value,
                )
            )
    return devices
