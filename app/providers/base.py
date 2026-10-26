from dataclasses import dataclass
from typing import Protocol

from app.schemas.plan_proposal import PlanProposalRequest


@dataclass(frozen=True)
class ProviderOutput:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderError(Exception):
    """Falla de la llamada al proveedor. El servicio la traduce a un error controlado."""


class ProviderTimeoutError(ProviderError):
    pass


class ProviderFailureError(ProviderError):
    pass


class PlanProvider(Protocol):
    """Interfaz común de generación: cambiar de proveedor queda acotado a una
    implementación nueva y a la configuración (riesgo 5).

    Un proveedor real usa solo `prompt`; `request` es para el simulado, que arma la
    propuesta a partir del contexto ya validado.
    """

    name: str
    model: str

    async def generate(self, prompt: str, request: PlanProposalRequest) -> ProviderOutput: ...
