"""Refuse a download while the user's chosen models folder is not connected."""

from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.catalog.local.install.plan import InstallRefusedError
from shared.config import get_storage_settings


def refuse_while_storage_is_missing() -> None:
    if get_storage_settings().model_storage_unavailable:
        raise InstallRefusedError(
            "The drive with your models folder isn't connected. "
            "Connect it and restart SurfSense to download models.",
            InstallCode.MODEL_STORAGE_UNAVAILABLE,
        )
