from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection
from modules.llm.selectable import SLOTS

# A ChatGPT plan's token reaches POST /v1/responses only: no images, speech,
# video or embeddings, whatever model is named.
_SERVES_BY_AUTH: dict[str, tuple[ModelType, ...]] = {
    "chatgpt": (ModelType.TEXT_GEN,),
}

def served_by(auth_kind: str) -> tuple[ModelType, ...]:
    """The model types a connection signed in this way can fill.

    The one rule: selection, resolution, the model tests, and every picker
    through `ConnectionRead.serves`, read it here and nowhere else.
    """
    return _SERVES_BY_AUTH.get(auth_kind, SLOTS)


def connection_serves(connection: ProviderConnection) -> tuple[ModelType, ...]:
    return served_by(connection.auth_kind)
