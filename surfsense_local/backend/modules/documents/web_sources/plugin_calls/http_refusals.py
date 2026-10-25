"""A plugin call's failure as the API answers it; the dialog words each `code` itself."""

from fastapi import HTTPException, status

from modules.documents.web_sources.plugin_calls.plugin_access import LicenseRefusedError
from modules.documents.web_sources.plugin_calls.plugin_call import (
    PluginUnavailableError,
    ToolRefusedError,
)


def as_http(error: Exception) -> HTTPException:
    if isinstance(error, LicenseRefusedError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "code": "license_refused",
                "reason": error.reason,
                "message": "Adding sources from the web needs a SurfSense license.",
            },
        )
    if isinstance(error, PluginUnavailableError):
        return HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            {"code": "plugin_unavailable", "message": str(error)},
        )
    if isinstance(error, ToolRefusedError):
        return HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            {"code": "plugin_refused", "message": str(error)},
        )
    raise error
