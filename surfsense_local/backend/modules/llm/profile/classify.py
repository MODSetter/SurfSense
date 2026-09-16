from modules.llm.profile.types import Fingerprint, Line, Tier

# Under the first a model loses accuracy when asked to follow a scaffold; between
# the two it follows one and gains from it; past the second it writes better from
# judgement than from steps.
COMPACT_MAX_B = 7.0
CAPABLE_MAX_B = 100.0


def classify(fingerprint: Fingerprint) -> Tier:
    """Which of the three prompts this model gets."""
    if fingerprint.params_b is not None:
        return _by_size(fingerprint.params_b)
    if fingerprint.vendor is not None:
        return Tier.FRONTIER
    if fingerprint.line is not None:
        return Tier.FRONTIER if fingerprint.line is Line.FLAGSHIP else Tier.CAPABLE
    # A hosted endpoint runs models too large for a laptop; Ollama runs the laptop.
    return Tier.COMPACT if fingerprint.provider == "ollama" else Tier.CAPABLE


def _by_size(params_b: float) -> Tier:
    if params_b < COMPACT_MAX_B:
        return Tier.COMPACT
    if params_b < CAPABLE_MAX_B:
        return Tier.CAPABLE
    return Tier.FRONTIER
