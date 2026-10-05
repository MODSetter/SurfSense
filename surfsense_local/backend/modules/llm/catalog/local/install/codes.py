"""What an install event says, as a code the interface has its own words for.

Every event still carries its English sentence, which the interface shows for a
code it does not know. Keep in sync with `install-text.ts` in the frontend.
"""

from enum import StrEnum


class InstallCode(StrEnum):
    QUEUED = "queued"
    CHECKING = "checking"
    PREPARING_DOWNLOAD = "preparing_download"
    DOWNLOADING = "downloading"
    CHECKING_RETRIEVAL = "checking_retrieval"
    PREPARING_RUNTIME = "preparing_runtime"
    LOADING_MODEL = "loading_model"
    LOADING_IMAGE_SUPPORT = "loading_image_support"
    LOADING_DRAFT_MODEL = "loading_draft_model"
    SELECTING = "selecting"
    READY = "ready"
    READY_AFTER_RESTART = "ready_after_restart"
    CANCELLED = "cancelled"
    # How an install fails.
    FAILED = "failed"
    FILE_GONE = "file_gone"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    # Why one is refused before any byte moves.
    NOT_ENOUGH_DISK = "not_enough_disk"
    TOO_BIG = "too_big"
    NOT_A_MODEL = "not_a_model"
    NO_ENGINE = "no_engine"
