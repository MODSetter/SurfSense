import json

from app.artifacts.verification.formats.registry import get_format_adapter
from app.artifacts.verification.formats.video import check_video
from app.sandbox import ExecResult


class ProbeSession:
    session_id = "sandbox-1"

    def __init__(self, *, audio=True, levels=40, stddev=20.0, expected_duration=None):
        self.audio = audio
        self.levels = levels
        self.stddev = stddev
        self.expected_duration = expected_duration

    async def run_command(self, command):
        if command.startswith("ffprobe"):
            streams = [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "duration": "3.0",
                    "nb_read_packets": "90",
                }
            ]
            if self.audio:
                streams.append(
                    {
                        "codec_type": "audio",
                        "duration": "3.0",
                        "nb_read_packets": "120",
                    }
                )
            return ExecResult(
                json.dumps({"format": {"duration": "3.0"}, "streams": streams}),
                0,
            )
        if command.startswith("test -f"):
            return (
                ExecResult(
                    json.dumps({"expected_duration_seconds": self.expected_duration}),
                    0,
                )
                if self.expected_duration is not None
                else ExecResult("", 1)
            )
        if command.startswith("ffmpeg"):
            return ExecResult(
                json.dumps({"levels": self.levels, "stddev": self.stddev}), 0
            )
        if command.startswith("sha256sum"):
            return ExecResult(f"{'a' * 64}  /workspace/out.mp4", 0)
        raise AssertionError(command)


async def test_video_adapter_probes_in_sandbox_and_requires_audio():
    adapter = get_format_adapter("/workspace/out.mp4")
    assert adapter.name == "video"
    assert adapter.requires_visual_review is False
    assert adapter.sandbox_check is check_video

    result = await check_video(ProbeSession(audio=False), "/workspace/out.mp4")

    assert result.primary_sha256 == "a" * 64
    assert result.structural.findings == (
        "Video must contain exactly one narration audio stream",
    )


async def test_video_adapter_rejects_single_color_frame():
    result = await check_video(ProbeSession(levels=1, stddev=0), "/workspace/out.mp4")

    assert "single-color" in result.structural.findings[0]


async def test_video_adapter_accepts_narrated_nonblank_mp4():
    result = await check_video(ProbeSession(), "/workspace/out.mp4")

    assert result.structural.clean


async def test_video_adapter_rejects_truncated_segment_concat():
    result = await check_video(ProbeSession(expected_duration=5), "/workspace/out.mp4")

    assert "rendered segments" in result.structural.findings[0]
