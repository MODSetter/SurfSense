"""``generate_image`` tool: a thin binding of the image generator's agent door."""

from app.artifacts.generation.access.agent import build_artifact_tool
from app.artifacts.generation.image.generator import ImageGenerator

_IMAGE_GENERATOR = ImageGenerator()


def create_generate_image_tool(
    workspace_id: int,
    db_session=None,
    image_gen_model_id_override: int | None = None,
):
    """Bind ``generate_image`` to a workspace; DB work uses a per-call session."""
    del db_session  # tool opens its own session per call
    return build_artifact_tool(
        _IMAGE_GENERATOR,
        workspace_id=workspace_id,
        image_gen_model_id_override=image_gen_model_id_override,
    )
