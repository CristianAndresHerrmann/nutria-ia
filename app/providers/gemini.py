import logging

import httpx
import httpx2
from google import genai
from google.genai import errors, types

from app.providers.base import (
    ProviderFailureError,
    ProviderOutput,
    ProviderTimeoutError,
)
from app.providers.schema import response_schema
from app.schemas.plan_proposal import PlanProposalRequest

logger = logging.getLogger(__name__)

# Gemini responde 400 con los `maxItems` anidados del contrato (comidas × opciones ×
# ítems): demasiados estados para su decodificación restringida. Los límites los sigue
# exigiendo la validación del servicio.
RESPONSE_SCHEMA = response_schema(exclude=frozenset({"maxItems"}))

# Qué valores acepta cada modelo lo decide la API (Gemini 3.8 Flash no admite `minimal`).
REASONING_LEVELS = ("minimal", "low", "medium", "high")

# El SDK deja pasar sin envolver los errores de transporte, de httpx o de httpx2 según
# el cliente que use.
_TIMEOUT_ERRORS = (httpx.TimeoutException, httpx2.TimeoutException)
_TRANSPORT_ERRORS = (httpx.TransportError, httpx2.TransportError)


def build_client(api_key: str, timeout_seconds: float) -> genai.Client:
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=round(timeout_seconds * 1000),
            # Un solo intento: el tiempo límite es uno para toda la generación, y el
            # reintento lo decide el profesional (RNF-02).
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


class GeminiProvider:
    """Adaptador de la API de Gemini (`generateContent`, sin estado del lado del
    proveedor). Envía solo el prompt, nunca la solicitud (RNF-07)."""

    name = "gemini"

    def __init__(self, model: str, reasoning_level: str, client: genai.Client):
        if reasoning_level not in REASONING_LEVELS:
            raise ValueError(f"AI_REASONING_LEVEL inválido para gemini: {reasoning_level!r}")
        self.model = model
        self._client = client
        self._config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=RESPONSE_SCHEMA,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel(reasoning_level.upper())),
            # Sin registro de la solicitud en el proyecto, aunque esté activado (RNF-07).
            store=False,
        )

    async def generate(self, prompt: str, request: PlanProposalRequest) -> ProviderOutput:
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model, contents=prompt, config=self._config
            )
        except _TIMEOUT_ERRORS as exc:
            logger.warning("gemini timeout error=%s", type(exc).__name__)
            raise ProviderTimeoutError("Gemini no respondió a tiempo") from exc
        except errors.APIError as exc:
            logger.warning("gemini error status=%s message=%s", exc.code, exc.message)
            raise ProviderFailureError(f"Gemini respondió {exc.code}") from exc
        except _TRANSPORT_ERRORS as exc:
            logger.warning("gemini error=%s", type(exc).__name__)
            raise ProviderFailureError("No se pudo conectar con Gemini") from exc

        if not response.text:
            # Sin texto no hay nada que validar: bloqueo de seguridad o sin candidatos.
            logger.warning("gemini sin texto finish_reason=%s block_reason=%s", _finish_reason(response),
                           response.prompt_feedback and response.prompt_feedback.block_reason)
            raise ProviderFailureError("Gemini respondió sin texto")

        usage = response.usage_metadata
        return ProviderOutput(
            text=response.text,
            input_tokens=usage.prompt_token_count if usage else None,
            # Incluye los tokens de razonamiento, como OpenAI: se facturan como salida.
            output_tokens=_sum(usage.candidates_token_count, usage.thoughts_token_count) if usage else None,
        )


def _finish_reason(response: types.GenerateContentResponse):
    return response.candidates[0].finish_reason if response.candidates else None


def _sum(*counts: int | None) -> int | None:
    present = [count for count in counts if count is not None]
    return sum(present) if present else None
