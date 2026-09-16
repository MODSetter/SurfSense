"""How a model should be prompted, derived from what is known about it."""

from modules.llm.profile.classify import classify
from modules.llm.profile.fingerprint import from_name, from_ollama, from_remote
from modules.llm.profile.types import Fingerprint, Line, Tier

__all__ = [
    "Fingerprint",
    "Line",
    "Tier",
    "classify",
    "from_name",
    "from_ollama",
    "from_remote",
]
