"""The models SurfSense uses where other apps keep them, as the runtime sees them.

Each is read again from its own header whenever the folder is, so a file its
app deleted, moved or replaced leaves the runtime's preset at the next
rewrite. Its record stays: a file on a drive that is away comes back with it.
"""

from pathlib import Path

from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.engines.llamacpp.elsewhere.candidate import Candidate
from modules.llm.catalog.local.engines.llamacpp.elsewhere.find import (
    FoundModel,
    judge,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.found_in import FoundIn
from modules.llm.catalog.local.engines.llamacpp.elsewhere.record import (
    InPlace,
    read_record,
)
from modules.llm.catalog.local.engines.llamacpp.models_folder.scan import (
    DownloadedModel,
)


def in_place_models(models_dir: Path) -> list[DownloadedModel]:
    models = []
    for used in read_record(models_dir).models:
        found = read_again(used)
        if found is None:
            continue
        models.append(
            DownloadedModel(
                model_id=used.model_id,
                path=found.path,
                weights_bytes=found.weights_bytes,
                shape=found.shape,
                classification=classify(found.label.architecture),
                template=found.template,
                record=None,
                projector=found.projector,
                projector_kv=dict(found.projector_kv),
                model_kv=dict(found.model_kv),
                found_in=found_in(found),
            )
        )
    return models


def found_in(found: FoundModel) -> FoundIn:
    return FoundIn(
        app=found.app.value,
        path=str(found.path),
        source=found.source,
        name=found.label.name,
        architecture=found.label.architecture,
        parameters=found.label.parameters,
        quantization=found.label.quantization,
    )


def read_again(used: InPlace) -> FoundModel | None:
    """The recorded file as its header reads now, or None once it cannot be used."""
    # `judge` checks every part is still there, as it does for any file.
    outcome = judge(
        Candidate(
            used.app,
            Path(used.path),
            tuple(Path(part) for part in used.parts),
            projector=Path(used.projector) if used.projector else None,
            name=used.name,
            source=used.source,
        )
    )
    return outcome if isinstance(outcome, FoundModel) else None
