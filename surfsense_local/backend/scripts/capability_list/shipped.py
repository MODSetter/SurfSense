"""The list the app ships, read and written the one way both writers share."""

import json

from modules.llm.capability.measured.loader import SHIPPED
from modules.llm.capability.measured.schema import CapabilityList


def read_shipped() -> CapabilityList:
    """Strict, unlike the app's loader: a writer must not start from an empty list."""
    return CapabilityList.model_validate_json(SHIPPED.read_text(encoding="utf-8"))


def write_shipped(rows: CapabilityList) -> None:
    SHIPPED.write_text(
        json.dumps(rows.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
