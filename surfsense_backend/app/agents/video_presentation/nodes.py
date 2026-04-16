import asyncio
import contextlib
import json
import math
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from ffmpeg.asyncio import FFmpeg
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from litellm import aspeech

from app.config import config as app_config
from app.services.kokoro_tts_service import get_kokoro_tts_service
from app.services.llm_service import get_agent_llm
from app.utils.content_utils import extract_text_content, strip_markdown_fences

from .configuration import Configuration
from .prompts import (
    DEFAULT_DURATION_IN_FRAMES,
    FPS,
    REFINE_SCENE_SYSTEM_PROMPT,
    REMOTION_SCENE_SYSTEM_PROMPT,
    THEME_PRESETS,
    build_scene_generation_user_prompt,
    build_theme_assignment_user_prompt,
    get_slide_generation_prompt,
    get_theme_assignment_system_prompt,
    pick_theme_and_mode_fallback,
)
from .state import (
    PresentationSlides,
    SlideAudioResult,
    SlideContent,
    SlideSceneCode,
    State,
)
from .utils import get_voice_for_provider

MAX_REFINE_ATTEMPTS = 3


async def create_presentation_slides(
    state: State, config: RunnableConfig
) -> dict[str, Any]:
    """Parse source content into structured presentation slides using LLM."""

    configuration = Configuration.from_runnable_config(config)
    search_space_id = configuration.search_space_id
    user_prompt = configuration.user_prompt

    llm = await get_agent_llm(state.db_session, search_space_id)
    if not llm:
        error_message = f"No LLM configured for search space {search_space_id}"
        print(error_message)
        raise RuntimeError(error_message)

    prompt = get_slide_generation_prompt(user_prompt)

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(
            content=f"<source_content>{state.source_content}</source_content>"
        ),
    ]

    llm_response = await llm.ainvoke(messages)
    content = strip_markdown_fences(extract_text_content(llm_response.content))

    try:
        presentation = PresentationSlides.model_validate(json.loads(content))
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"Direct JSON parsing failed, trying fallback approach: {e!s}")

        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                parsed_data = json.loads(json_str)
                presentation = PresentationSlides.model_validate(parsed_data)
                print("Successfully parsed presentation slides using fallback approach")
            else:
                error_message = f"Could not find valid JSON in LLM response. Raw response: {content}"
                print(error_message)
                raise ValueError(error_message)

        except (json.JSONDecodeError, TypeError, ValueError) as e2:
            error_message = f"Error parsing LLM response (fallback also failed): {e2!s}"
            print(f"Error parsing LLM response: {e2!s}")
            print(f"Raw response: {content}")
            raise

    return {"slides": presentation.slides}


async def create_slide_audio(state: State, config: RunnableConfig) -> dict[str, Any]:
    """Generate TTS audio for each slide.

    Each slide's speaker_transcripts are generated as individual TTS chunks,
    then concatenated with ffmpeg (matching the POC in RemotionTets/api/tts).
    """

    session_id = str(uuid.uuid4())
    temp_dir = Path("temp_audio")
    temp_dir.mkdir(exist_ok=True)
    output_dir = Path("video_presentation_audio")
    output_dir.mkdir(exist_ok=True)

    slides = state.slides or []
    voice = get_voice_for_provider(app_config.TTS_SERVICE, speaker_id=0)
    ext = "wav" if app_config.TTS_SERVICE == "local/kokoro" else "mp3"

    async def _generate_tts_chunk(text: str, chunk_path: str) -> str:
        """Generate a single TTS chunk and write it to *chunk_path*."""
        if app_config.TTS_SERVICE == "local/kokoro":
            kokoro_service = await get_kokoro_tts_service(lang_code="a")
            await kokoro_service.generate_speech(
                text=text,
                voice=voice,
                speed=1.0,
                output_path=chunk_path,
            )
        else:
            kwargs: dict[str, Any] = {
                "model": app_config.TTS_SERVICE,
                "api_key": app_config.TTS_SERVICE_API_KEY,
                "voice": voice,
                "input": text,
                "max_retries": 2,
                "timeout": 600,
            }
            if app_config.TTS_SERVICE_API_BASE:
                kwargs["api_base"] = app_config.TTS_SERVICE_API_BASE

            response = await aspeech(**kwargs)
            with open(chunk_path, "wb") as f:
                f.write(response.content)

        return chunk_path

    async def _concat_with_ffmpeg(chunk_paths: list[str], output_file: str) -> None:
        """Concatenate multiple audio chunks into one file using async ffmpeg."""
        ffmpeg = FFmpeg().option("y")
        for chunk in chunk_paths:
            ffmpeg = ffmpeg.input(chunk)

        filter_parts = [f"[{i}:0]" for i in range(len(chunk_paths))]
        filter_str = (
            "".join(filter_parts) + f"concat=n={len(chunk_paths)}:v=0:a=1[outa]"
        )
        ffmpeg = ffmpeg.option("filter_complex", filter_str)
        ffmpeg = ffmpeg.output(output_file, map="[outa]")
        await ffmpeg.execute()

    async def generate_audio_for_slide(slide: SlideContent) -> SlideAudioResult:
        has_transcripts = (
            slide.speaker_transcripts and len(slide.speaker_transcripts) > 0
        )

        if not has_transcripts:
            print(
                f"Slide {slide.slide_number}: no speaker_transcripts, "
                f"using default duration ({DEFAULT_DURATION_IN_FRAMES} frames)"
            )
            return SlideAudioResult(
                slide_number=slide.slide_number,
                audio_file="",
                duration_seconds=DEFAULT_DURATION_IN_FRAMES / FPS,
                duration_in_frames=DEFAULT_DURATION_IN_FRAMES,
            )

        output_file = str(output_dir / f"{session_id}_slide_{slide.slide_number}.{ext}")

        chunk_paths: list[str] = []
        try:
            chunk_paths = [
                str(
                    temp_dir
                    / f"{session_id}_slide_{slide.slide_number}_chunk_{i}.{ext}"
                )
                for i in range(len(slide.speaker_transcripts))
            ]

            for i, text in enumerate(slide.speaker_transcripts):
                print(
                    f"  Slide {slide.slide_number} chunk {i + 1}/"
                    f"{len(slide.speaker_transcripts)}: "
                    f'"{text[:60]}..."'
                )

            await asyncio.gather(
                *[
                    _generate_tts_chunk(text, path)
                    for text, path in zip(
                        slide.speaker_transcripts, chunk_paths, strict=False
                    )
                ]
            )

            if len(chunk_paths) == 1:
                shutil.move(chunk_paths[0], output_file)
            else:
                print(
                    f"  Concatenating {len(chunk_paths)} chunks for slide "
                    f"{slide.slide_number} with ffmpeg"
                )
                await _concat_with_ffmpeg(chunk_paths, output_file)

            duration_seconds = await _get_audio_duration(output_file)
            duration_in_frames = math.ceil(duration_seconds * FPS)

            return SlideAudioResult(
                slide_number=slide.slide_number,
                audio_file=output_file,
                duration_seconds=duration_seconds,
                duration_in_frames=max(duration_in_frames, DEFAULT_DURATION_IN_FRAMES),
            )

        except Exception as e:
            print(f"Error generating audio for slide {slide.slide_number}: {e!s}")
            raise
        finally:
            for p in chunk_paths:
                with contextlib.suppress(OSError):
                    os.remove(p)

    tasks = [generate_audio_for_slide(slide) for slide in slides]
    audio_results = await asyncio.gather(*tasks)

    audio_results_sorted = sorted(audio_results, key=lambda r: r.slide_number)

    print(
        f"Generated audio for {len(audio_results_sorted)} slides "
        f"(total duration: {sum(r.duration_seconds for r in audio_results_sorted):.1f}s)"
    )

    return {"slide_audio_results": audio_results_sorted}


async def _get_audio_duration(file_path: str) -> float:
    """Get audio duration in seconds using ffprobe (via python-ffmpeg).

    Falls back to file-size estimation if ffprobe fails.
    """
    try:
        import subprocess

        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0 and stdout.strip():
            return float(stdout.strip())
    except Exception as e:
        print(f"ffprobe failed for {file_path}: {e!s}, using file-size estimation")

    try:
        file_size = os.path.getsize(file_path)
        if file_path.endswith(".wav"):
            return file_size / (16000 * 2)
        else:
            return file_size / 16000
    except Exception:
        return DEFAULT_DURATION_IN_FRAMES / FPS


async def _assign_themes_with_llm(
    llm, slides: list[SlideContent]
) -> dict[int, tuple[str, str]]:
    """Ask the LLM to assign a theme+mode to each slide in one call.

    Returns a dict mapping slide_number → (theme, mode).
    Falls back to round-robin if the LLM response can't be parsed.
    """
    total = len(slides)
    slide_summaries = [
        {
            "slide_number": s.slide_number,
            "title": s.title,
            "subtitle": s.subtitle or "",
            "background_explanation": s.background_explanation or "",
        }
        for s in slides
    ]

    system = get_theme_assignment_system_prompt()
    user = build_theme_assignment_user_prompt(slide_summaries)

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=user),
            ]
        )

        text = strip_markdown_fences(extract_text_content(response.content))

        assignments = json.loads(text)
        valid_themes = set(THEME_PRESETS)
        result: dict[int, tuple[str, str]] = {}
        for entry in assignments:
            sn = entry.get("slide_number")
            theme = entry.get("theme", "").upper()
            mode = entry.get("mode", "dark").lower()
            if sn and theme in valid_themes and mode in ("dark", "light"):
                result[sn] = (theme, mode)

        if len(result) == total:
            print(
                "LLM theme assignment: "
                + ", ".join(f"S{sn}={t}/{m}" for sn, (t, m) in sorted(result.items()))
            )
            return result

        print(
            f"LLM returned {len(result)}/{total} valid assignments, "
            "filling gaps with fallback"
        )
        for s in slides:
            if s.slide_number not in result:
                result[s.slide_number] = pick_theme_and_mode_fallback(
                    s.slide_number - 1, total
                )
        return result

    except Exception as e:
        print(f"LLM theme assignment failed ({e!s}), using fallback")
        return {
            s.slide_number: pick_theme_and_mode_fallback(s.slide_number - 1, total)
            for s in slides
        }


async def assign_slide_themes(state: State, config: RunnableConfig) -> dict[str, Any]:
    """Assign a theme preset + dark/light mode to every slide via a single LLM call.

    Runs in parallel with audio generation since it only needs slide metadata.
    """
    configuration = Configuration.from_runnable_config(config)
    search_space_id = configuration.search_space_id

    llm = await get_agent_llm(state.db_session, search_space_id)
    if not llm:
        raise RuntimeError(f"No LLM configured for search space {search_space_id}")

    slides = state.slides or []
    assignments = await _assign_themes_with_llm(llm, slides)
    return {"slide_theme_assignments": assignments}


async def generate_slide_scene_codes(
    state: State, config: RunnableConfig
) -> dict[str, Any]:
    """Generate Remotion component code for each slide using LLM.

    Reads pre-assigned themes from state (produced by the parallel
    assign_slide_themes node) and generates scene code concurrently.
    """

    configuration = Configuration.from_runnable_config(config)
    search_space_id = configuration.search_space_id

    llm = await get_agent_llm(state.db_session, search_space_id)
    if not llm:
        raise RuntimeError(f"No LLM configured for search space {search_space_id}")

    slides = state.slides or []
    audio_results = state.slide_audio_results or []

    audio_map: dict[int, SlideAudioResult] = {r.slide_number: r for r in audio_results}
    total_slides = len(slides)

    theme_assignments = state.slide_theme_assignments or {}

    async def _generate_scene_for_slide(slide: SlideContent) -> SlideSceneCode:
        audio = audio_map.get(slide.slide_number)
        duration = audio.duration_in_frames if audio else DEFAULT_DURATION_IN_FRAMES

        theme, mode = theme_assignments.get(
            slide.slide_number,
            pick_theme_and_mode_fallback(slide.slide_number - 1, total_slides),
        )

        user_prompt = build_scene_generation_user_prompt(
            slide_number=slide.slide_number,
            total_slides=total_slides,
            title=slide.title,
            subtitle=slide.subtitle,
            content_in_markdown=slide.content_in_markdown,
            background_explanation=slide.background_explanation,
            duration_in_frames=duration,
            theme=theme,
            mode=mode,
        )

        messages = [
            SystemMessage(content=REMOTION_SCENE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        print(
            f"Generating scene code for slide {slide.slide_number}/{total_slides}: "
            f'"{slide.title}" ({duration} frames)'
        )

        llm_response = await llm.ainvoke(messages)
        code, scene_title = _extract_code_and_title(
            extract_text_content(llm_response.content)
        )

        code = await _refine_if_needed(llm, code, slide.slide_number)

        print(f"Scene code ready for slide {slide.slide_number} ({len(code)} chars)")

        return SlideSceneCode(
            slide_number=slide.slide_number,
            code=code,
            title=scene_title or slide.title,
        )

    scene_codes = list(
        await asyncio.gather(*[_generate_scene_for_slide(s) for s in slides])
    )

    return {"slide_scene_codes": scene_codes}


def _extract_code_and_title(content: str) -> tuple[str, str | None]:
    """Extract code and optional title from LLM response.

    The LLM may return a JSON object like the POC's structured output:
      { "code": "...", "title": "..." }
    Or it may return raw code (with optional markdown fences).

    Returns (code, title) where title may be None.
    """
    text = strip_markdown_fences(content)

    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "code" in parsed:
                return parsed["code"], parsed.get("title")
        except (json.JSONDecodeError, ValueError):
            pass

        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            try:
                parsed = json.loads(text[json_start:json_end])
                if isinstance(parsed, dict) and "code" in parsed:
                    return parsed["code"], parsed.get("title")
            except (json.JSONDecodeError, ValueError):
                pass

    return text, None


async def _refine_if_needed(llm, code: str, slide_number: int) -> str:
    """Attempt basic syntax validation and auto-repair via LLM if needed.

    Raises RuntimeError if the code is still invalid after MAX_REFINE_ATTEMPTS,
    matching the POC's behavior where a failed slide aborts the pipeline.
    """
    error = _basic_syntax_check(code)
    if error is None:
        return code

    for attempt in range(1, MAX_REFINE_ATTEMPTS + 1):
        print(
            f"Slide {slide_number}: syntax issue (attempt {attempt}/{MAX_REFINE_ATTEMPTS}): {error}"
        )

        messages = [
            SystemMessage(content=REFINE_SCENE_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Here is the broken Remotion component code:\n\n{code}\n\n"
                    f"Compilation error:\n{error}\n\nFix the code."
                )
            ),
        ]

        response = await llm.ainvoke(messages)
        code, _ = _extract_code_and_title(extract_text_content(response.content))

        error = _basic_syntax_check(code)
        if error is None:
            print(f"Slide {slide_number}: fixed on attempt {attempt}")
            return code

    raise RuntimeError(
        f"Slide {slide_number} failed to compile after {MAX_REFINE_ATTEMPTS} "
        f"refine attempts. Last error: {error}"
    )


def _basic_syntax_check(code: str) -> str | None:
    """Run a lightweight syntax check on the generated code.

    Full Babel-based compilation happens on the frontend. This backend check
    catches the most common LLM code-generation mistakes so the refine loop
    can fix them before persisting.

    Returns an error description or None if the code looks valid.
    """
    if not code or not code.strip():
        return "Empty code"

    if "export" not in code and "MyComposition" not in code:
        return "Missing exported component (expected 'export const MyComposition')"

    brace_count = 0
    paren_count = 0
    bracket_count = 0
    for ch in code:
        if ch == "{":
            brace_count += 1
        elif ch == "}":
            brace_count -= 1
        elif ch == "(":
            paren_count += 1
        elif ch == ")":
            paren_count -= 1
        elif ch == "[":
            bracket_count += 1
        elif ch == "]":
            bracket_count -= 1

        if brace_count < 0:
            return "Unmatched closing brace '}'"
        if paren_count < 0:
            return "Unmatched closing parenthesis ')'"
        if bracket_count < 0:
            return "Unmatched closing bracket ']'"

    if brace_count != 0:
        return f"Unbalanced braces: {brace_count} unclosed"
    if paren_count != 0:
        return f"Unbalanced parentheses: {paren_count} unclosed"
    if bracket_count != 0:
        return f"Unbalanced brackets: {bracket_count} unclosed"

    if "useCurrentFrame" not in code:
        return "Missing useCurrentFrame() — required for Remotion animations"

    if "AbsoluteFill" not in code:
        return "Missing AbsoluteFill — required as the root layout component"

    return None
