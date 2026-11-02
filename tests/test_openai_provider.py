import asyncio
import json
from types import SimpleNamespace

import httpx2
import openai
import pytest
from fastapi.testclient import TestClient
from openai.types.responses import Response

from app.main import app
from app.prompts import render_plan_prompt
from app.providers import get_provider
from app.providers.fake import simulated_proposal
from app.providers.openai import OpenAIProvider
from app.providers.schema import RESPONSE_SCHEMA
from app.schemas.plan_proposal import PLAN_PROPOSAL_REQUEST_EXAMPLE, PlanProposalRequest

client = TestClient(app)
request = PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE)
valid_text = json.dumps(simulated_proposal(request), ensure_ascii=False)
api_request = httpx2.Request("POST", "https://api.openai.com/v1/responses")


class FakeOpenAIClient:
    """Superficie del cliente de openai que usa el adaptador. Registra cada llamada y
    devuelve una respuesta del SDK o levanta un error del SDK."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def openai_response(text=None, refusal=None, status="completed"):
    content = []
    if text is not None:
        content.append({"type": "output_text", "text": text, "annotations": []})
    if refusal is not None:
        content.append({"type": "refusal", "refusal": refusal})
    return Response.model_validate(
        {
            "id": "resp_ficticia",
            "object": "response",
            "created_at": 0,
            "model": "gpt-6-luna",
            "status": status,
            "output": [
                {"type": "message", "id": "msg_ficticio", "role": "assistant", "status": "completed",
                 "content": content}
            ],
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "usage": {
                "input_tokens": 900,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": 520,
                "output_tokens_details": {"reasoning_tokens": 120},
                "total_tokens": 1420,
            },
        }
    )


def provider(fake_client, reasoning_level="low"):
    return OpenAIProvider(model="gpt-6-luna", reasoning_level=reasoning_level, client=fake_client)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def post_with(fake_client):
    app.dependency_overrides[get_provider] = lambda: provider(fake_client)
    return client.post("/plan-proposals", json=PLAN_PROPOSAL_REQUEST_EXAMPLE)


def test_respuesta_valida_devuelve_la_propuesta_con_los_datos_de_la_generacion():
    response = post_with(FakeOpenAIClient(openai_response(valid_text)))

    assert response.status_code == 200
    generation = response.json()["generation"]
    assert generation["provider"] == "openai"
    assert generation["model"] == "gpt-6-luna"
    assert generation["raw_response"] == valid_text
    assert (generation["input_tokens"], generation["output_tokens"]) == (900, 520)
    # output_tokens ya incluye los de razonamiento; se informan además aparte.
    assert generation["reasoning_tokens"] == 120


def test_envia_solo_el_prompt_con_el_esquema_estricto_el_razonamiento_y_sin_guardar():
    fake_client = FakeOpenAIClient(openai_response(valid_text))

    post_with(fake_client)

    (call,) = fake_client.calls
    assert set(call) == {"model", "input", "reasoning", "text", "store"}
    assert call["model"] == "gpt-6-luna"
    assert call["input"] == render_plan_prompt(request)
    assert call["reasoning"] == {"effort": "low"}
    assert call["text"] == {
        "format": {"type": "json_schema", "name": "plan_proposal", "schema": RESPONSE_SCHEMA, "strict": True}
    }
    assert call["store"] is False


def test_el_nivel_de_razonamiento_es_configurable():
    fake_client = FakeOpenAIClient(openai_response(valid_text))

    asyncio.run(provider(fake_client, reasoning_level="medium").generate("prompt", request))

    assert fake_client.calls[0]["reasoning"] == {"effort": "medium"}


def test_nivel_de_razonamiento_desconocido_falla_al_crear_el_proveedor():
    with pytest.raises(ValueError, match="AI_REASONING_LEVEL"):
        provider(FakeOpenAIClient(), reasoning_level="bajo")


def test_timeout_del_cliente_da_504():
    response = post_with(FakeOpenAIClient(error=openai.APITimeoutError(request=api_request)))

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "PROVIDER_TIMEOUT"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(openai.InternalServerError("Falla", response=httpx2.Response(500, request=api_request),
                                                body=None), id="error-5xx"),
        pytest.param(openai.RateLimitError("Cuota agotada", response=httpx2.Response(429, request=api_request),
                                           body=None), id="error-4xx"),
        pytest.param(openai.APIConnectionError(request=api_request), id="sin-conexion"),
    ],
)
def test_falla_del_proveedor_da_502_sin_respuesta_cruda(error):
    response = post_with(FakeOpenAIClient(error=error))

    assert response.status_code == 502
    body = response.json()["error"]
    assert body["code"] == "PROVIDER_ERROR"
    assert body["details"]["generation"]["provider"] == "openai"
    assert body["details"]["generation"]["raw_response"] is None


@pytest.mark.parametrize(
    "sdk_response",
    [
        pytest.param(openai_response(refusal="No puedo ayudar con eso"), id="rechazo"),
        pytest.param(openai_response(status="failed"), id="respuesta-fallida"),
    ],
)
def test_respuesta_sin_texto_da_502_provider_error(sdk_response):
    response = post_with(FakeOpenAIClient(sdk_response))

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_ERROR"


def test_texto_fuera_del_contrato_da_invalid_provider_output_con_la_respuesta_cruda():
    truncated = valid_text[:200]

    response = post_with(FakeOpenAIClient(openai_response(truncated, status="incomplete")))

    assert response.status_code == 502
    body = response.json()["error"]
    assert body["code"] == "INVALID_PROVIDER_OUTPUT"
    assert body["details"]["generation"]["raw_response"] == truncated
