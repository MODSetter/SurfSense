"""Why no renewed license file was imported, as the code `POST /license/refresh` answers."""

from modules.egress.service import EgressDeniedError


class RefreshFailedError(Exception):
    def __init__(self, code: str, refusal: EgressDeniedError | None = None) -> None:
        super().__init__(code)
        self.code = code
        # For `refresh_egress_blocked`: the host to allow, so the UI can ask about it.
        self.refusal = refusal
