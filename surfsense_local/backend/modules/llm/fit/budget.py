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

    @property
    def resident_bytes(self) -> int:
        """What a model must fit inside to run at full speed.

        Without a GPU there is no device to be resident in, and the processor's
        own memory is both where the model runs and all there is, so the two
        questions below collapse into one answer.
        """
        return self.usable_vram_bytes if self.has_gpu else self.ram_available_bytes

    @property
    def refusal_bytes(self) -> int:
        """What physics allows at all. Only this refuses a model.

        On unified memory the device and the host are the same chips, so this is
        host memory alone and never a sum with the device: adding the two counts
        one memory twice, which is what gave an 8 GB Mac a 10.3 GB threshold.

        Host memory rather than the device's own figure, because Metal's working
        set bounds what Metal will allocate, not what the machine can hold.
        Measured: a 1.7B at 40960 projected 6032 MiB against a 5460 MiB working
        set, and llama.cpp ran it with 23 of 29 layers on the CPU backend, which
        reads the same chips without that ceiling.

        On a discrete card the two really are separate pools, and spilling from
        one into the other is what the middle state means.
        """
        if not self.has_gpu:
            return self.ram_available_bytes
        if self.uma:
            return self.ram_available_bytes
        return self.usable_vram_bytes + self.ram_available_bytes
