import asyncio

import pytest

from app.config import Settings
from app.providers import build_provider
from app.providers.fake import FakeProvider
from app.schemas.plan_proposal import (
    PLAN_PROPOSAL_REQUEST_EXAMPLE,
    PlanProposal,
    PlanProposalRequest,
)

request = PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE)


def generate(provider):
    return asyncio.run(provider.generate("prompt", request))


def test_la_misma_solicitud_da_siempre_la_misma_respuesta():
    assert generate(FakeProvider()).text == generate(FakeProvider()).text


def test_la_respuesta_simulada_cumple_el_contrato():
    proposal = PlanProposal.model_validate_json(generate(FakeProvider()).text, strict=True)

    assert proposal.violations_against(request) == []


def test_escenario_desconocido_falla_al_crear_el_proveedor():
    with pytest.raises(ValueError):
        FakeProvider(scenario="otro")


def test_proveedor_desconocido_falla_al_armarlo():
    with pytest.raises(ValueError, match="AI_PROVIDER"):
        build_provider(Settings(ai_provider="otro", provider_timeout_seconds=1, fake_provider_scenario="ok"))


def settings(**overrides):
    values = {"ai_provider": "openai", "provider_timeout_seconds": 1, "fake_provider_scenario": "ok",
              "ai_model": "modelo-ficticio", "gemini_api_key": "clave-ficticia", "openai_api_key": "clave-ficticia"}
    return Settings(**(values | overrides))


@pytest.mark.parametrize("provider", ["gemini", "openai"])
def test_proveedor_real_se_arma_con_modelo_y_clave_sin_llamar_a_la_api(provider):
    built = build_provider(settings(ai_provider=provider))

    assert (built.name, built.model) == (provider, "modelo-ficticio")


@pytest.mark.parametrize(
    ("overrides", "variable"),
    [
        pytest.param({"ai_provider": "gemini", "ai_model": None}, "AI_MODEL", id="gemini-sin-modelo"),
        pytest.param({"ai_provider": "gemini", "gemini_api_key": None}, "GEMINI_API_KEY", id="gemini-sin-clave"),
        pytest.param({"ai_provider": "openai", "ai_model": None}, "AI_MODEL", id="openai-sin-modelo"),
        pytest.param({"ai_provider": "openai", "openai_api_key": None}, "OPENAI_API_KEY", id="openai-sin-clave"),
        pytest.param({"ai_provider": "gemini", "ai_reasoning_level": "max"}, "AI_REASONING_LEVEL",
                     id="gemini-razonamiento-invalido"),
        pytest.param({"ai_provider": "openai", "ai_reasoning_level": "bajo"}, "AI_REASONING_LEVEL",
                     id="openai-razonamiento-invalido"),
    ],
)
def test_proveedor_real_mal_configurado_falla_al_armarlo(overrides, variable):
    with pytest.raises(ValueError, match=variable):
        build_provider(settings(**overrides))


def test_las_claves_no_aparecen_en_la_representacion_de_la_configuracion():
    assert "clave-ficticia" not in repr(settings())
