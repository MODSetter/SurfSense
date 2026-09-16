from importlib.resources import files
from string import Template

from modules.llm.profile import Tier


def load(package: str, tier: Tier, *, case: str = "", **slots: object) -> str:
    """The prompt a case ships for one tier, with its slots filled.

    Slots are `$name`, since every prompt carries a JSON schema whose braces
    must reach the model as written. A package hosting two cases names each of
    them in a subfolder.
    """
    parts = ("prompts", case, f"{tier}.md") if case else ("prompts", f"{tier}.md")
    text = files(package).joinpath(*parts).read_text(encoding="utf-8").strip()
    try:
        return Template(text).substitute(slots)
    except KeyError as missing:
        raise ValueError(
            f"{package}/{'/'.join(parts)} wants a slot nobody filled: {missing}"
        ) from missing
