"""The preset llama-server reads at startup. Rewriting it is what makes a new file
reachable: Electron restarts the router on every change.
"""

import logging
from collections.abc import Sequence
from pathlib import Path

from modules.llm.catalog.local.engines.llamacpp.models_folder.scan import (
    DownloadedModel,
)
from modules.llm.catalog.local.engines.llamacpp.support import (
    projector_fits_model,
    projector_reads_images,
)
from modules.llm.fit import HardwareBudget, plan_load
from modules.llm.hardware import fit_target_mib
from modules.llm.providers.llamacpp import PRESET_FILE, ModelPreset, write_presets

logger = logging.getLogger(__name__)


def write_preset(
    models_dir: Path,
    installed: Sequence[DownloadedModel],
    budget: HardwareBudget,
    live: HardwareBudget,
) -> None:
    presets = []
    for model in installed:
        if model.shape is None:
            # Unreadable: skipping costs this model, failing would leave the
            # runtime dead over a file nobody asked it to load.
            logger.warning("skipping unreadable model %s", model.path.name)
            continue
        projector = model.projector if _pairs(model) else None
        mmproj_bytes = projector.stat().st_size if projector else 0
        plan = plan_load(
            model.shape,
            model.weights_bytes,
            budget,
            live=live,
            mmproj_bytes=mmproj_bytes,
        )
        presets.append(
            ModelPreset(
                model_id=model.model_id,
                path=str(model.path),
                n_ctx=plan.n_ctx,
                precision=plan.precision,
                fit_target_mib=fit_target_mib(mmproj_bytes),
                mmproj_path=str(projector) if projector else None,
            )
        )
    write_presets(models_dir / PRESET_FILE, presets)


def _pairs(model: DownloadedModel) -> bool:
    """The recorded or name-matched projector, only when it sees and fits."""
    return (
        model.projector is not None
        and projector_reads_images(model.projector_kv)
        and projector_fits_model(model.projector_kv, model.model_kv)
    )
