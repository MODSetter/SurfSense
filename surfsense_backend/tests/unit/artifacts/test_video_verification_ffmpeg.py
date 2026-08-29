import asyncio
import json
import shlex
import shutil

import pytest

from app.artifacts.verification.formats.video import check_video
from app.sandbox import ExecResult

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are required",
)


class LocalCommandSession:
    session_id = "local-ffmpeg"

    async def run_command(self, command):
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await process.communicate()
        return ExecResult(output.decode(), process.returncode or 0)


async def _make_fixture(path, *, black=False, audio=True):
    video_source = (
        "color=c=black:s=1920x1080:r=30" if black else "testsrc2=s=1920x1080:r=30"
    )
    audio_input = "-f lavfi -i sine=frequency=440:sample_rate=48000" if audio else ""
    audio_codec = "-c:a aac -shortest" if audio else "-an"
    command = (
        f"ffmpeg -y -v error -f lavfi -i {shlex.quote(video_source)} "
        f"{audio_input} -t 1 -c:v libx264 -preset ultrafast -pix_fmt yuv420p "
        f"{audio_codec} {shlex.quote(str(path))}"
    )
    result = await LocalCommandSession().run_command(command)
    assert result.ok, result.output


async def test_real_ffmpeg_video_fixtures_cover_structural_gate(tmp_path):
    valid = tmp_path / "valid.mp4"
    black = tmp_path / "black.mp4"
    mute = tmp_path / "mute.mp4"
    await _make_fixture(valid)
    await _make_fixture(black, black=True)
    await _make_fixture(mute, audio=False)
    session = LocalCommandSession()

    assert (await check_video(session, str(valid))).structural.clean
    assert "single-color" in " ".join(
        (await check_video(session, str(black))).structural.findings
    )
    assert "narration audio" in " ".join(
        (await check_video(session, str(mute))).structural.findings
    )

    (tmp_path / "valid.mp4.segments.json").write_text(
        json.dumps({"expected_duration_seconds": 3})
    )
    assert "rendered segments" in " ".join(
        (await check_video(session, str(valid))).structural.findings
    )
