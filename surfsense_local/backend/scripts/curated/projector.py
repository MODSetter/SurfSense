"""Find the vision projector that belongs with a build.

Authoring time only. A vision model ships its projector as a separate file in
the same repo, and llama.cpp's fitter does not count it, so the manifest has to
name it for the launch path to reserve room.
"""

import httpx

API = "https://huggingface.co/api/models"

# Highest fidelity first. A projector is small beside the weights, so the cost of
# the largest is a rounding error against the quality of what it feeds the model.
_PREFERRED = ("f16", "bf16", "f32", "q8_0")


def find_projector(client: httpx.Client, repo: str) -> tuple[str, int] | None:
    """The projector file in `repo` and its size, or None for a text model."""
    reply = client.get(f"{API}/{repo}/tree/main", timeout=60)
    reply.raise_for_status()

    candidates = [
        row
        for row in reply.json()
        if row["path"].endswith(".gguf") and "mmproj" in row["path"].lower()
    ]
    if not candidates:
        return None

    def rank(row: dict) -> tuple[int, int]:
        name = row["path"].lower()
        precision = next(
            (i for i, token in enumerate(_PREFERRED) if token in name), len(_PREFERRED)
        )
        # Shortest name breaks a tie, the same rule find_variant uses.
        return precision, len(row["path"])

    chosen = min(candidates, key=rank)
    return chosen["path"], chosen["size"]
