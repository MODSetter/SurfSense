from dataclasses import asdict

from fastapi import APIRouter

from modules.resource_usage.dependencies import ResourceSamplerDep
from modules.resource_usage.schemas import ResourceUsageRead

router = APIRouter(prefix="/system", tags=["system"])


@router.get(
    "/usage", response_model=ResourceUsageRead, summary="Live machine and app usage"
)
def read_usage(sampler: ResourceSamplerDep) -> dict:
    """Polled while the panel is on screen; a `def` so the sample runs off the loop."""
    return asdict(sampler.sample())
