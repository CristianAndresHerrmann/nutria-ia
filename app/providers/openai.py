import logging
from typing import get_args

import openai
from openai.types.shared import ReasoningEffort

from app.providers.base import (
    ProviderFailureError,
    ProviderOutput,
    ProviderTimeoutError,
)
from app.providers.schema import RESPONSE_SCHEMA
from app.schemas.plan_proposal import PlanProposalRequest

logger = logging.getLogger(__name__)

# Los que declara el SDK; qué valores acepta cada modelo lo decide la API.
REASONING_LEVELS = get_args(get_args(ReasoningEffort)[0])

_FORMAT = {"type": "json_schema", "name": "plan_proposal", "schema": RESPONSE_SCHEMA, "strict": True}


def build_client(api_key: str, timeout_seconds: float) -> openai.AsyncOpenAI:
    # Sin reintentos del SDK: el tiempo límite es uno para toda la generación, y el
    # reintento lo decide el profesional (RNF-02).
    return openai.AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)


class OpenAIProvider:
    """Adaptador de la Responses API de OpenAI. Envía solo el prompt, nunca la
    solicitud (RNF-07)."""

    name = "openai"

    def __init__(self, model: str, reasoning_level: str, client: openai.AsyncOpenAI):
        if reasoning_level not in REASONING_LEVELS:
            raise ValueError(f"AI_REASONING_LEVEL inválido para openai: {reasoning_level!r}")
        self.model = model
        self._reasoning_level = reasoning_level
        self._client = client

    async def generate(self, prompt: str, request: PlanProposalRequest) -> ProviderOutput:
        try:
            response = await self._client.responses.create(
                model=self.model,
                input=prompt,
                reasoning={"effort": self._reasoning_level},
                text={"format": _FORMAT},
                # Por defecto la Responses API guarda la respuesta en OpenAI (RNF-07).
                store=False,
            )
        except openai.APITimeoutError as exc:
            logger.warning("openai timeout")
            raise ProviderTimeoutError("OpenAI no respondió a tiempo") from exc
        except openai.APIError as exc:
            status = getattr(exc, "status_code", None)
            logger.warning("openai error=%s status=%s", type(exc).__name__, status)
            raise ProviderFailureError(f"OpenAI falló: {type(exc).__name__}") from exc

        if not response.output_text:
            # Sin texto no hay nada que validar: rechazo del modelo o respuesta fallida.
            logger.warning("openai sin texto status=%s refusal=%s", response.status, _refused(response))
            raise ProviderFailureError("OpenAI respondió sin texto")

        usage = response.usage
        return ProviderOutput(
            text=response.output_text,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
        )


def _refused(response) -> bool:
    return any(
        content.type == "refusal"
        for output in response.output
        if output.type == "message"
        for content in output.content
    )
