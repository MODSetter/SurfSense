"""The summary's shape: part C of docs/contracts/05-desktop-telemetry.md, every value an enum."""

from typing import Literal

from pydantic import BaseModel

Turns = Literal["0", "1-9", "10-49", "50+", "unknown"]
ModelSource = Literal["none", "local", "remote", "both", "unknown"]
Sources = Literal["0", "1-9", "10-99", "100-999", "1000+", "unknown"]
StudioOutputs = Literal["0", "1-4", "5+", "unknown"]
PluginCalls = Literal["0", "1-9", "10+", "unknown"]
OnboardingStep = Literal[
    "not_started",
    "model_chosen",
    "model_ready",
    "first_source",
    "first_answer",
    "unknown",
]
RamGb = Literal["<8", "8-15", "16-31", "32-63", "64+"]
Gpu = Literal["nvidia", "amd", "intel", "apple", "none", "unknown"]
VramGb = Literal["0", "<4", "4-7", "8-11", "12-23", "24+", "unknown"]
GpuRuntime = Literal["reachable", "unreachable", "none", "unknown"]
UiLanguage = Literal["en", "ja", "de", "other"]


class WeekRead(BaseModel):
    chat_turns: Turns
    agent_turns: Turns
    model_source: ModelSource
    sources: Sources
    studio_outputs: StudioOutputs
    plugin_calls: PluginCalls
    onboarding: OnboardingStep


class HardwareRead(BaseModel):
    ram_gb: RamGb
    gpu: Gpu
    vram_gb: VramGb
    # Whether the model runtime can use the card the OS sees.
    gpu_runtime: GpuRuntime


class UsageSummaryRead(BaseModel):
    week: WeekRead
    # None only when this machine's memory cannot be read.
    hardware: HardwareRead | None
    ui_language: UiLanguage
