class ManifestError(ValueError):
    """Every error at once, so an author fixes a manifest in one pass."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors
