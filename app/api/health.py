from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.providers import get_provider
from app.providers.base import PlanProvider
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Verifica que el servicio responde",
    description="Informa el proveedor y el modelo configurados, sin llamar al proveedor: el smoke test del CD "
    "falla si en staging corre el simulado (`fake`).",
)
def get_health(provider: Annotated[PlanProvider, Depends(get_provider)]):
    return {
        "status": "ok",
        "service": "nutria-ia",
        "provider": provider.name,
        "model": provider.model,
        "timestamp": datetime.now(UTC).isoformat(),
    }
