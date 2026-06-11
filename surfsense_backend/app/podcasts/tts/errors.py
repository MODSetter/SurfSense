"""Failures raised by the TTS layer."""

from __future__ import annotations


class TextToSpeechError(RuntimeError):
    """A provider failed to synthesise a segment.

    Raised for both configuration faults (an unusable voice reference) and
    provider faults (the upstream call errored or returned no audio), so the
    renderer can fail the segment without unwrapping provider-specific
    exceptions.
    """
