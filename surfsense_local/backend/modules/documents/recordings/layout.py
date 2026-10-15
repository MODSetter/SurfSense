"""Where a recording's transcript files live: under transcript/ in its document
folder, since the original must stay the only file there (original_file.py).

transcript/work/ holds what a job resumes from; transcript/segments.json is
written when the transcript is done, for seeking later.
"""

from dataclasses import dataclass
from pathlib import Path

TRANSCRIPT_FOLDER = "transcript"
WORK_FOLDER = "work"
SEGMENTS_NAME = "segments.json"


@dataclass(frozen=True)
class WorkFiles:
    folder: Path

    @property
    def audio(self) -> Path:
        """The recording decoded to 16 kHz mono 16-bit PCM, about 115 MB an
        hour; written as a `.part` beside it until the decoder is done."""
        return self.folder / "audio16k.raw"

    @property
    def plan(self) -> Path:
        return self.folder / "plan.json"

    @property
    def windows(self) -> Path:
        return self.folder / "windows.jsonl"

    @property
    def progress(self) -> Path:
        return self.folder / "progress.json"


def transcript_dir(document_dir: Path) -> Path:
    return document_dir / TRANSCRIPT_FOLDER


def work_files(document_dir: Path) -> WorkFiles:
    return WorkFiles(transcript_dir(document_dir) / WORK_FOLDER)


def segments_file(document_dir: Path) -> Path:
    return transcript_dir(document_dir) / SEGMENTS_NAME
