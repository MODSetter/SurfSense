"""Where the Office pack lives on disk, shared by the API and every worker."""

from pathlib import Path

from shared.config import get_storage_settings


def office_dir() -> Path:
    return get_storage_settings().data_dir / "runtime" / "office"


def versions_dir() -> Path:
    """One folder per unpacked version; a folder is complete once it has its name."""
    return office_dir() / "versions"


def downloads_dir() -> Path:
    """The upstream file while it downloads; kept as `.part` for a resume."""
    return office_dir() / "downloads"


def installed_record() -> Path:
    """Names the unpacked version in use."""
    return office_dir() / "installed.json"


def confirmed_record() -> Path:
    """The user's own LibreOffice, once they confirmed it in Settings."""
    return office_dir() / "use-installed.json"


def offer_dismissed_record() -> Path:
    """Present once the user dismissed the offer to turn it on, or turned it on; outlives a removal."""
    return office_dir() / "offer-dismissed.json"


def profile_slot() -> Path:
    """The one profile: one run at a time, so one profile, warm after its first run."""
    return office_dir() / "profiles" / "slot-0"


def run_lock() -> Path:
    """Held by whichever process runs LibreOffice: one at a time, app-wide."""
    return office_dir() / "run.lock"
