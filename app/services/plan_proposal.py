"""Generación de la propuesta de plan.

Arma el prompt, llama al proveedor y valida la respuesta contra el contrato. No
accede a la base ni aplica reglas clínicas: eso es del backend (DA-01).
"""

import asyncio
import logging
import time

from pydantic import ValidationError

from app.errors import GenerationError
from app.prompts import PLAN_PROPOSAL_TEMPLATE_VERSION, render_plan_prompt
from app.providers.base import (
    PlanProvider,
    ProviderFailureError,
    ProviderOutput,
    ProviderTimeoutError,
)
from app.schemas.plan_proposal import (
    ContractViolation,
    GenerationErrorBody,
    GenerationErrorCode,
    GenerationErrorDetails,
    GenerationErrorResponse,
    GenerationInfo,
    PlanProposal,
    PlanProposalRequest,
    PlanProposalResponse,
)

logger = logging.getLogger(__name__)

_ERRORS = {
    GenerationErrorCode.provider_timeout: (504, "El proveedor de IA no respondió a tiempo"),
    GenerationErrorCode.provider_error: (502, "El proveedor de IA falló al generar la propuesta"),
    GenerationErrorCode.invalid_provider_output: (
        502,
        "La respuesta del proveedor de IA no respeta el contrato de la propuesta",
    ),
}


async def generate_plan_proposal(
    request: PlanProposalRequest,
    provider: PlanProvider,
    timeout_seconds: float,
    template_version: str = PLAN_PROPOSAL_TEMPLATE_VERSION,
) -> PlanProposalResponse:
    prompt = render_plan_prompt(request, template_version)
    started = time.perf_counter()

    try:
        output = await asyncio.wait_for(provider.generate(prompt, request), timeout=timeout_seconds)
    except (TimeoutError, ProviderTimeoutError):
        raise _error(
            GenerationErrorCode.provider_timeout, _generation(provider, template_version, started)
        ) from None
    except ProviderFailureError:
        raise _error(GenerationErrorCode.provider_error, _generation(provider, template_version, started)) from None

    generation = _generation(provider, template_version, started, output)
    try:
        proposal = PlanProposal.model_validate_json(output.text, strict=True)
    except ValidationError as exc:
        violations = [
            ContractViolation(loc=list(error["loc"]), msg=error["msg"])
            for error in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise _error(GenerationErrorCode.invalid_provider_output, generation, violations) from None

    violations = proposal.violations_against(request)
    if violations:
        raise _error(GenerationErrorCode.invalid_provider_output, generation, violations)

    _trace("success", generation)
    return PlanProposalResponse(proposal=proposal, generation=generation)


def _generation(
    provider: PlanProvider, template_version: str, started: float, output: ProviderOutput | None = None
) -> GenerationInfo:
    return GenerationInfo(
        provider=provider.name,
        model=provider.model,
        template_version=template_version,
        duration_ms=round((time.perf_counter() - started) * 1000),
        input_tokens=output.input_tokens if output else None,
        output_tokens=output.output_tokens if output else None,
        reasoning_tokens=output.reasoning_tokens if output else None,
        raw_response=output.text if output else None,
    )


def _error(
    code: GenerationErrorCode, generation: GenerationInfo, violations: list[ContractViolation] | None = None
) -> GenerationError:
    _trace(code.value, generation)
    status_code, message = _ERRORS[code]
    body = GenerationErrorResponse(
        error=GenerationErrorBody(
            code=code,
            message=message,
            details=GenerationErrorDetails(generation=generation, errors=violations),
        )
    )
    return GenerationError(status_code, body)


def _trace(result: str, generation: GenerationInfo) -> None:
    # Solo metadatos: el contexto enviado y la respuesta los persiste el backend en
    # ai_generation, junto al plan.
    logger.info(
        "plan_proposal result=%s provider=%s model=%s template_version=%s duration_ms=%d "
        "input_tokens=%s output_tokens=%s reasoning_tokens=%s",
        result,
        generation.provider,
        generation.model,
        generation.template_version,
        generation.duration_ms,
        generation.input_tokens,
        generation.output_tokens,
        generation.reasoning_tokens,
    )
