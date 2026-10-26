from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.providers import get_provider
from app.providers.base import PlanProvider
from app.schemas.plan_proposal import (
    GenerationErrorResponse,
    PlanProposalRequest,
    PlanProposalResponse,
)
from app.services.plan_proposal import generate_plan_proposal

router = APIRouter()


@router.post(
    "/plan-proposals",
    response_model=PlanProposalResponse,
    summary="Genera una propuesta de plan alimentario",
    description="Recibe el contexto anonimizado del paciente y devuelve una propuesta por tipo de comida, "
    "con opciones e ítems que referencian el catálogo enviado. La propuesta no está validada clínicamente: "
    "la valida el motor de reglas del backend y la revisa el profesional.",
    responses={
        502: {
            "model": GenerationErrorResponse,
            "description": "PROVIDER_ERROR (falla del proveedor) o INVALID_PROVIDER_OUTPUT (la respuesta no "
            "respeta el contrato). Recuperable: se puede reintentar.",
        },
        504: {
            "model": GenerationErrorResponse,
            "description": "PROVIDER_TIMEOUT: el proveedor no respondió a tiempo. Recuperable: se puede reintentar.",
        },
    },
)
async def create_plan_proposal(
    request: PlanProposalRequest,
    provider: Annotated[PlanProvider, Depends(get_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return await generate_plan_proposal(request, provider, settings.provider_timeout_seconds)
