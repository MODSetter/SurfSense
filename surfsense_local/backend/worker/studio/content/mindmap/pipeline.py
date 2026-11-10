from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.content.mindmap import outline
from worker.studio.content.mindmap.outline import BRANCHES, CHILDREN
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.window_budget import REPLY_SHARE

# The reply's share of the 8,192-token window a local model loads at. Unconstrained,
# a model that repeats would otherwise write until the window is full.
REPLY_TOKENS = int(8_192 * REPLY_SHARE)

NO_BRANCHES = "The model wrote no usable branches. Try again, or choose a larger model."

__all__ = ["BRANCHES", "CHILDREN", "REPLY_TOKENS", "build", "prompt", "render"]


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    # No schema: the shape is the model's. A JSON map broke on Qwen3 4B in 9 of 9,
    # and a schema allowing any depth crashed llama-server at b11050.
    raw = generate.run_model(
        model, prompt(model.tier, user_prompt), sources, max_tokens=REPLY_TOKENS
    )
    return build(raw, sources)


def prompt(tier: Tier, user_prompt: str | None) -> str:
    return prompting.load(
        __package__, tier, focus=prompting.focus(user_prompt), ceiling=BRANCHES
    )


def build(raw: str, _sources: list[Source]) -> Built:
    # A markdown outline: an H1 root over nested bullets, which Markmap reads
    # directly on the client and which stays readable as plain text.
    title, lines = outline.read(raw)
    if not lines:
        raise ValueError(NO_BRANCHES)
    title = title or "Mind map"
    return Built(title=title, markdown="\n".join([f"# {title}", *lines]))
