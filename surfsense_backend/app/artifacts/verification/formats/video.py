"""Fast, provider-independent checks for a rendered MP4."""

from __future__ import annotations

import json
import math
import re
import shlex
from typing import Any

from app.sandbox import SandboxSession

from .base import SandboxCheckResult, StructuralCheckResult

_WIDTH = 1920
_HEIGHT = 1080
_DURATION_TOLERANCE_SECONDS = 0.5
_MIN_FRAME_LEVELS = 4
_MIN_FRAME_STDDEV = 1.0
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def reject_buffered_video_check(_: bytes) -> StructuralCheckResult:
    raise RuntimeError("Video verification must run inside the sandbox")


async def _run(session: SandboxSession, command: str, label: str) -> str:
    result = await session.run_command(command)
    if not result.ok:
        raise ValueError(f"Video {label} failed")
    return result.output.strip()


def _positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 0 else None


async def _expected_duration(session: SandboxSession, path: str) -> float | None:
    sidecar = f"{path}.segments.json"
    result = await session.run_command(
        f"test -f {shlex.quote(sidecar)} && cat -- {shlex.quote(sidecar)}"
    )
    if not result.ok or not result.output.strip():
        return None
    try:
        data = json.loads(result.output)
        if "expected_duration_seconds" in data:
            expected = _positive_float(data["expected_duration_seconds"])
            if expected is not None:
                return expected
            raise ValueError("Video segment metadata is invalid")
        durations = data.get("segment_durations_seconds")
        if isinstance(durations, list) and durations:
            values = [_positive_float(value) for value in durations]
            if all(value is not None for value in values):
                return sum(value for value in values if value is not None)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    raise ValueError("Video segment metadata is invalid")


async def check_video(session: SandboxSession, path: str) -> SandboxCheckResult:
    """Probe an MP4 in place; only compact metadata crosses the trust boundary."""
    quoted = shlex.quote(path)
    findings: list[str] = []
    probe_text = await _run(
        session,
        "ffprobe -v error -count_packets -of json -show_entries "
        "format=duration:stream=codec_type,width,height,duration,nb_read_packets "
        f"{quoted}",
        "probe",
    )
    try:
        probe = json.loads(probe_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Video probe returned invalid metadata") from exc

    duration = _positive_float(probe.get("format", {}).get("duration"))
    if duration is None:
        findings.append("Video duration must be greater than zero")

    streams = probe.get("streams")
    if not isinstance(streams, list):
        streams = []
    video_streams = [
        stream for stream in streams if stream.get("codec_type") == "video"
    ]
    audio_streams = [
        stream for stream in streams if stream.get("codec_type") == "audio"
    ]
    if len(video_streams) != 1:
        findings.append("Video must contain exactly one video stream")
    elif (
        video_streams[0].get("width") != _WIDTH
        or video_streams[0].get("height") != _HEIGHT
    ):
        findings.append(f"Video resolution must be {_WIDTH}x{_HEIGHT}")
    if len(audio_streams) != 1:
        findings.append("Video must contain exactly one narration audio stream")
    else:
        audio_stream = audio_streams[0]
        try:
            audio_packets = int(audio_stream.get("nb_read_packets", 0))
        except (TypeError, ValueError):
            audio_packets = 0
        if audio_packets <= 0:
            findings.append("Video narration audio is empty")
        audio_duration = _positive_float(audio_stream.get("duration"))
        if (
            duration is not None
            and audio_duration is not None
            and duration - audio_duration > _DURATION_TOLERANCE_SECONDS
        ):
            findings.append("Video narration ends before the video")

    expected_duration = await _expected_duration(session, path)
    if (
        expected_duration is not None
        and duration is not None
        and abs(duration - expected_duration) > _DURATION_TOLERANCE_SECONDS
    ):
        findings.append("Video duration does not match its rendered segments")

    if duration is not None:
        frame_stats_text = await _run(
            session,
            "ffmpeg -v error "
            f"-ss {duration / 2:.6f} -i {quoted} -frames:v 1 "
            '-vf "scale=64:36,format=gray" -f rawvideo - | '
            "python3 -c 'import json,statistics,sys; "
            "d=sys.stdin.buffer.read(); "
            'print(json.dumps({"levels":len(set(d)),'
            '"stddev":statistics.pstdev(d) if d else 0}))\'',
            "frame sanity check",
        )
        try:
            frame_stats = json.loads(frame_stats_text)
            if (
                int(frame_stats["levels"]) < _MIN_FRAME_LEVELS
                or float(frame_stats["stddev"]) < _MIN_FRAME_STDDEV
            ):
                findings.append("Video sampled frame is blank or single-color")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Video frame check returned invalid metadata") from exc

    primary_sha256 = (await _run(session, f"sha256sum -- {quoted}", "hash")).split(
        maxsplit=1
    )[0]
    if not _SHA256_RE.fullmatch(primary_sha256):
        raise ValueError("Video hash returned invalid metadata")

    return SandboxCheckResult(
        structural=StructuralCheckResult(tuple(findings)),
        primary_sha256=primary_sha256,
    )
