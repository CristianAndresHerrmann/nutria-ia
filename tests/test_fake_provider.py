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
