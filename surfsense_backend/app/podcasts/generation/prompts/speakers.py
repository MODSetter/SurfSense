"""Render a spec's speaker roster for prompts.

The drafting prompts must reference speakers by the exact ``slot`` the renderer
expects, so this is the single place that formats that roster — keeping the
slot contract identical across every prompt that mentions speakers.
"""

from __future__ import annotations

from app.podcasts.schemas import PodcastSpec


def render_speaker_roster(spec: PodcastSpec) -> str:
    lines = [
        f"- slot {speaker.slot} — {speaker.name} (role: {speaker.role.value})"
        for speaker in spec.speakers
    ]
    return "\n".join(lines)
