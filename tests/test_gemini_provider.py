import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import errors, types

from app.main import app
from app.prompts import render_plan_prompt
from app.providers import get_provider
from app.providers.fake import simulated_proposal
from app.providers.gemini import RESPONSE_SCHEMA, GeminiProvider
from app.schemas.plan_proposal import PLAN_PROPOSAL_REQUEST_EXAMPLE, PlanProposalRequest

client = TestClient(app)
request = PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE)
valid_text = json.dumps(simulated_proposal(request), ensure_ascii=False)


class FakeGeminiClient:
    """Superficie del cliente de google-genai que usa el adaptador. Registra cada
    llamada y devuelve una respuesta del SDK o levanta un error del SDK."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate_content))

    async def _generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def gemini_response(text, finish_reason="STOP"):
    parts = [{"text": text}] if text is not None else []
    return types.GenerateContentResponse.model_validate(
        {
            "candidates": [{"content": {"role": "model", "parts": parts}, "finish_reason": finish_reason}],
            "usage_metadata": {"prompt_token_count": 900, "candidates_token_count": 400, "thoughts_token_count": 120},
        }
    )


def provider(fake_client, reasoning_level="low"):
    return GeminiProvider(model="gemini-3.8-flash", reasoning_level=reasoning_level, client=fake_client)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def post_with(fake_client):
    app.dependency_overrides[get_provider] = lambda: provider(fake_client)
    return client.post("/plan-proposals", json=PLAN_PROPOSAL_REQUEST_EXAMPLE)


def test_respuesta_valida_devuelve_la_propuesta_con_los_datos_de_la_generacion():
    response = post_with(FakeGeminiClient(gemini_response(valid_text)))

    assert response.status_code == 200
    generation = response.json()["generation"]
    assert generation["provider"] == "gemini"
    assert generation["model"] == "gemini-3.8-flash"
    assert generation["raw_response"] == valid_text


def test_los_tokens_de_salida_incluyen_los_de_razonamiento():
    output = asyncio.run(provider(FakeGeminiClient(gemini_response(valid_text))).generate("prompt", request))

    assert output.input_tokens == 900
    assert output.output_tokens == 520
    assert output.reasoning_tokens == 120


def test_envia_solo_el_prompt_con_el_esquema_estricto_y_el_razonamiento_configurado():
    fake_client = FakeGeminiClient(gemini_response(valid_text))

    post_with(fake_client)

    (call,) = fake_client.calls
    assert set(call) == {"model", "contents", "config"}
    assert call["model"] == "gemini-3.8-flash"
    assert call["contents"] == render_plan_prompt(request)
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == RESPONSE_SCHEMA
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert config.store is False


def test_el_esquema_para_gemini_no_lleva_maxitems():
    # Con los maxItems anidados del contrato, la API responde 400.
    assert "maxItems" not in json.dumps(RESPONSE_SCHEMA)
    assert "minItems" in json.dumps(RESPONSE_SCHEMA)


def test_el_nivel_de_razonamiento_es_configurable():
    fake_client = FakeGeminiClient(gemini_response(valid_text))

    asyncio.run(provider(fake_client, reasoning_level="high").generate("prompt", request))

    assert fake_client.calls[0]["config"].thinking_config.thinking_level == types.ThinkingLevel.HIGH


def test_nivel_de_razonamiento_desconocido_falla_al_crear_el_proveedor():
    with pytest.raises(ValueError, match="AI_REASONING_LEVEL"):
        provider(FakeGeminiClient(), reasoning_level="xhigh")


def test_timeout_del_cliente_da_504():
    response = post_with(FakeGeminiClient(error=httpx.ReadTimeout("timeout")))

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "PROVIDER_TIMEOUT"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(errors.ServerError(503, {"error": {"code": 503, "message": "Sobrecargado"}}), id="error-5xx"),
        pytest.param(errors.ClientError(429, {"error": {"code": 429, "message": "Cuota agotada"}}), id="error-4xx"),
        pytest.param(httpx.ConnectError("sin conexión"), id="sin-conexion"),
    ],
)
def test_falla_del_proveedor_da_502_sin_respuesta_cruda(error):
    response = post_with(FakeGeminiClient(error=error))

    assert response.status_code == 502
    body = response.json()["error"]
    assert body["code"] == "PROVIDER_ERROR"
    assert body["details"]["generation"]["provider"] == "gemini"
    assert body["details"]["generation"]["raw_response"] is None


def test_respuesta_sin_texto_da_502_provider_error():
    response = post_with(FakeGeminiClient(gemini_response(None, finish_reason="SAFETY")))

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_ERROR"


def test_texto_fuera_del_contrato_da_invalid_provider_output_con_la_respuesta_cruda():
    truncated = valid_text[:200]

    response = post_with(FakeGeminiClient(gemini_response(truncated, finish_reason="MAX_TOKENS")))

    assert response.status_code == 502
    body = response.json()["error"]
    assert body["code"] == "INVALID_PROVIDER_OUTPUT"
    assert body["details"]["generation"]["raw_response"] == truncated
