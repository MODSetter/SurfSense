"""One device's memory, never a sum across devices."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HardwareBudget:
    """What a single device offers, and what the runtime will decline to use.

    `fit_reserve_bytes` is llama.cpp's own margin rather than an estimate of it:
    `fit_params_target` defaults to one GiB per device and is settable through
    `--fit-target`, so this is a number we pass in, not one we predict.
    """

    device_free_bytes: int
    device_total_bytes: int
    fit_reserve_bytes: int
    ram_available_bytes: int
    uma: bool
    has_gpu: bool

    @property
    def usable_vram_bytes(self) -> int:
        """What --fit will actually place layers in."""
        return max(0, self.device_free_bytes - self.fit_reserve_bytes)
