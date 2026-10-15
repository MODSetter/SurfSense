"""How a PDF operation says no: one sentence the agent can act on."""


class PdfRefusedError(Exception):
    """An operation that cannot be carried out on these PDFs, and why."""
