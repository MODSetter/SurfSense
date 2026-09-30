"""Fields an author must not write: a release stamps them."""

WHY = {
    "version": "remove it, the release sets a plugin's version",
    "sdk": "remove it, a plugin runs on the SurfSense release it shipped with or newer",
}


def errors_for_fields_the_release_sets(declared: dict) -> list[str]:
    return [f"{field}: {why}" for field, why in WHY.items() if field in declared]
