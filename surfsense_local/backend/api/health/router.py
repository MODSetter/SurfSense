from fastapi import APIRouter, status

from api.health.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
)
async def read_health() -> HealthResponse:
    """Report that the API process is up and accepting requests."""
    return HealthResponse(status="ok")
