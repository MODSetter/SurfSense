"""The embedder a run indexes with: bge, or a curated one by manifest id."""

from modules.embedding.bundled import BGE
from modules.embedding.spec import EmbedderSpec
from modules.llm.catalog.local.engines.onnxruntime.spec import spec_for
from modules.llm.catalog.local.manifest import load_local_manifest


def embedder_spec(model_id: str) -> EmbedderSpec:
    if model_id == BGE.id:
        return BGE
    for model in load_local_manifest().models:
        if model.id == model_id and model.embedding is not None:
            return spec_for(model)
    raise ValueError(f"no curated embedder named {model_id}")
