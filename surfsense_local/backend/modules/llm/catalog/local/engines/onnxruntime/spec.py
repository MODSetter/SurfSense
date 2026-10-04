"""A curated embedder as the spec an index stores a snapshot of."""

from modules.embedding.spec import EmbedderSpec, Identified, PinnedFile, Source
from modules.llm.catalog.local.build import FileRole
from modules.llm.catalog.local.manifest import CuratedModel


def spec_for(model: CuratedModel) -> EmbedderSpec:
    """Its default build: the first, which is the only one a curated embedder
    lists, since another build would be another vector space."""
    if model.embedding is None:
        raise ValueError(f"{model.id} is not an embedding model")
    build = model.as_builds()[0]
    tokenizer = next(f for f in build.files if f.role is FileRole.TOKENIZER)
    embedding = model.embedding
    return EmbedderSpec(
        id=model.id,
        source=Source.CURATED,
        identified=Identified.MEASURED,
        repo=build.weights.repo,
        revision=build.weights.revision,
        # Named as they land: one folder per model, the upstream path dropped.
        weights=PinnedFile(path=build.weights.name, sha256=build.weights.sha256),
        tokenizer=PinnedFile(path=tokenizer.name, sha256=tokenizer.sha256),
        dimension=embedding.dimension,
        pooling=embedding.pooling,
        normalize=embedding.normalize,
        query_prefix=embedding.query_prefix,
        document_prefix=embedding.document_prefix,
        max_tokens=embedding.max_tokens,
        semantic_weight=embedding.semantic_weight,
        batch=embedding.batch,
    )
