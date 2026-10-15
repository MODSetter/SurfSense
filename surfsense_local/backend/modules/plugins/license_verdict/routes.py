"""`POST /plugins/license/check`: the paid plugins' license verdict, asked of the plugin host now."""

from fastapi import APIRouter, status

from api.dependencies import SessionDep
from modules.plugins.license_verdict.license_refresh import refresh_license_verdict

# Included before `/plugins/{id}/...`, which would otherwise take `license` for an id.
router = APIRouter(prefix="/plugins/license", tags=["plugins"])


@router.post(
    "/check",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Ask whether the license unlocks the paid plugins",
)
async def check_license(session: SessionDep, if_stale: bool = False) -> None:
    """After a license change, at once; on opening Plugins, `if_stale`, once in five minutes."""
    await refresh_license_verdict(session, if_stale=if_stale)
