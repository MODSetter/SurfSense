"""Read one audio model's folder at its repo's commit and write its entry."""

from typing import Any

import httpx

from local_manifest.audiocpp.assemble import entry_for, pinned_builds
from local_manifest.audiocpp.entry import AudioEntry
from local_manifest.hub import RESOLVE, repo_at_revision
from local_manifest.unreadable import UnreadableBuildError
from modules.llm.catalog.local.engines.audiocpp.evidence import audio_family
from modules.llm.gguf import TruncatedHeaderError

# weights path -> the audio.cpp release a person voiced a podcast turn with
VALIDATED: dict[str, str] = {
    "Kokoro-82M-GGUF/kokoro-82m-q8_0.gguf": "v0.8.2",
    "Supertonic-3-GGUF/supertonic-3-f16.gguf": "v0.8.2",
    "KittenTTS-GGUF/kitten-tts-mini-0.8-orig.gguf": "v0.8.2",
}

# The family sits in the first 400 bytes; the header runs to tens of megabytes.
_READS = (64 * 1024, 1024 * 1024)


async def refresh(client: httpx.AsyncClient, entry: AudioEntry) -> dict[str, Any]:
    snapshot = await repo_at_revision(client, entry.repo)
    builds = pinned_builds(entry, snapshot)
    default = builds[0].weights
    url = RESOLVE.format(repo=entry.repo, revision=snapshot.revision, path=default.path)
    family = None
    for size in _READS:
        reply = await client.get(url, headers={"Range": f"bytes=0-{size - 1}"})
        reply.raise_for_status()
        try:
            family = audio_family(reply.content)
            break
        except TruncatedHeaderError:
            continue
    if family is None:
        raise UnreadableBuildError(
            f"{entry.repo}: {default.path} names no audio.cpp family"
        )
    written = entry_for(entry, snapshot, builds, family, VALIDATED)
    print(
        f"  {entry.name:22s} {snapshot.revision[:8]}  {len(builds):2d} builds, "
        f"default {builds[0].quantization}, {family}"
    )
    return written
