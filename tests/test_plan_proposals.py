import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.providers import get_provider
from app.providers.base import ProviderOutput
from app.providers.fake import FakeProvider, simulated_proposal
from app.schemas.plan_proposal import PLAN_PROPOSAL_REQUEST_EXAMPLE, PlanProposalRequest

client = TestClient(app)


class StubProvider:
    """Devuelve un texto fijo, para simular respuestas mal formadas del proveedor."""

    name = "stub"
    model = "stub-model"

    def __init__(self, text: str, delay_seconds: float = 0):
        self.text = text
        self.delay_seconds = delay_seconds
        self.calls = 0

    async def generate(self, prompt, request):
        self.calls += 1
        await asyncio.sleep(self.delay_seconds)
        return ProviderOutput(text=self.text, input_tokens=10, output_tokens=20)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def use_provider(provider):
    app.dependency_overrides[get_provider] = lambda: provider
    return provider


def payload():
    return copy.deepcopy(PLAN_PROPOSAL_REQUEST_EXAMPLE)


def valid_proposal():
    return simulated_proposal(PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE))


def post(body):
    return client.post("/plan-proposals", json=body)


# --- Solicitud válida -----------------------------------------------------------


def test_solicitud_valida_devuelve_propuesta_que_cumple_el_contrato():
    use_provider(FakeProvider())

    response = post(payload())

    assert response.status_code == 200
    body = response.json()
    proposal = body["proposal"]
    assert [meal["meal_type"] for meal in proposal["meals"]] == PLAN_PROPOSAL_REQUEST_EXAMPLE["meal_types"]
    assert "clinical_recommendations" not in proposal
    for field in ("situational_diagnosis", "introduction", "objectives", "general_recommendations",
                  "contextual_recommendations", "thematic_recommendations"):
        assert proposal[field]

    catalog = PLAN_PROPOSAL_REQUEST_EXAMPLE["catalog"]
    known = {
        "food": {food["code"] for food in catalog["foods"]},
        "food_group": {group["code"] for group in catalog["food_groups"]},
        "recipe": {recipe["code"] for recipe in PLAN_PROPOSAL_REQUEST_EXAMPLE["candidate_recipes"]},
    }
    items = [item for meal in proposal["meals"] for option in meal["options"] for item in option["items"]]
    assert {item["type"] for item in items} == {"food", "food_group", "recipe", "free_text"}
    for item in items:
        if item["type"] != "free_text":
            assert item["code"] in known[item["type"]]


def test_la_respuesta_informa_la_version_de_plantilla_y_los_datos_de_la_generacion():
    use_provider(FakeProvider())

    generation = post(payload()).json()["generation"]

    assert generation["template_version"] == "plan_proposal_v1"
    assert generation["provider"] == "fake"
    assert generation["model"] == "fake-deterministic"
    assert generation["duration_ms"] >= 0
    assert json.loads(generation["raw_response"])["meals"]


def test_la_traza_registra_la_plantilla_elegida_por_configuracion():
    use_provider(FakeProvider())
    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="fake", provider_timeout_seconds=5, fake_provider_scenario="ok", plan_template="plan_proposal_v2"
    )

    generation = post(payload()).json()["generation"]

    assert generation["template_version"] == "plan_proposal_v2"


def test_solicitud_minima_tambien_genera_propuesta_valida():
    use_provider(FakeProvider())
    body = {
        "meal_types": ["dinner"],
        "catalog": {"food_groups": [{"code": "G1", "name": "Frutas"}],
                    "foods": [{"code": "A1", "name": "Manzana", "group_code": "G1"}]},
    }

    response = post(body)

    assert response.status_code == 200
    assert [meal["meal_type"] for meal in response.json()["proposal"]["meals"]] == ["dinner"]


def test_catalogo_con_alimento_complementario_es_valido():
    use_provider(FakeProvider())
    body = {
        "meal_types": ["dinner"],
        "catalog": {"food_groups": [{"code": "G1", "name": "Sal, especias y hierbas"}],
                    "foods": [{"code": "A1", "name": "Sal fina", "group_code": "G1",
                               "categories": ["complementary"]}]},
    }

    assert post(body).status_code == 200


# --- Entrada fuera del contrato: 422 sin llamar al proveedor (RNF-07) ------------


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda body: body.update(patient_name="Paciente Ficticio"), id="campo-extra-en-la-raiz"),
        pytest.param(lambda body: body["conditions"][0].update(observations="Ver con Dra. X"), id="observaciones"),
        pytest.param(lambda body: body["habits"].update(email="ficticio@example.com"), id="campo-extra-anidado"),
        pytest.param(lambda body: body["catalog"]["foods"][0].update(id="uuid"), id="campo-extra-en-catalogo"),
        pytest.param(lambda body: body.update(meal_types=["brunch"]), id="tipo-de-comida-desconocido"),
        pytest.param(lambda body: body.update(meal_types=["lunch", "lunch"]), id="tipo-de-comida-repetido"),
        pytest.param(lambda body: body["catalog"]["foods"][1].update(code="A1"), id="codigo-repetido"),
        pytest.param(lambda body: body["catalog"]["foods"][0].update(group_code="G99"), id="grupo-inexistente"),
        pytest.param(lambda body: body["catalog"].update(foods=[]), id="catalogo-vacio"),
        pytest.param(lambda body: body["catalog"]["foods"][0].update(code="A 1"), id="codigo-con-espacio"),
    ],
)
def test_solicitud_fuera_del_contrato_da_422_y_no_llega_al_proveedor(mutate):
    provider = use_provider(StubProvider(json.dumps(valid_proposal())))
    body = payload()
    mutate(body)

    response = post(body)

    assert response.status_code == 422
    assert provider.calls == 0


# --- Salida inválida del proveedor: error controlado -----------------------------


def mutated_proposal(mutate):
    proposal = valid_proposal()
    mutate(proposal)
    return json.dumps(proposal)


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param('{"situational_diagnosis": "texto", ', id="json-roto"),
        pytest.param("Acá tenés tu plan: ...", id="texto-libre"),
        pytest.param(mutated_proposal(lambda p: p["meals"][0]["options"][0]["items"][0].update(grams=100)),
                     id="cantidad-en-gramos"),
        pytest.param(mutated_proposal(lambda p: p.update(clinical_recommendations="texto")),
                     id="recomendaciones-clinicas"),
        pytest.param(mutated_proposal(lambda p: p.pop("introduction")), id="campo-faltante"),
        pytest.param(mutated_proposal(lambda p: p["meals"][0].update(options="una opción")), id="tipo-incorrecto"),
        pytest.param(mutated_proposal(lambda p: p["meals"][0]["options"][0].update(items=[])), id="opcion-vacia"),
        pytest.param(mutated_proposal(lambda p: p["meals"][0]["options"][0]["items"].append({"type": "unknown"})),
                     id="tipo-de-item-desconocido"),
        pytest.param(mutated_proposal(lambda p: p["meals"][0]["options"][0]["items"].append(
            {"type": "free_text", "text": ""})), id="texto-libre-vacio"),
    ],
)
def test_salida_que_no_respeta_el_esquema_da_error_controlado(raw):
    use_provider(StubProvider(raw))

    response = post(payload())

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "INVALID_PROVIDER_OUTPUT"
    assert error["details"]["errors"]
    assert error["details"]["generation"]["raw_response"] == raw
    assert error["details"]["generation"]["template_version"] == "plan_proposal_v1"


def set_item(proposal, item):
    proposal["meals"][0]["options"][0]["items"][0] = item


@pytest.mark.parametrize(
    ("mutate", "loc"),
    [
        pytest.param(lambda p: set_item(p, {"type": "food", "code": "A99"}),
                     ["meals", 0, "options", 0, "items", 0, "code"], id="alimento-inventado"),
        pytest.param(lambda p: set_item(p, {"type": "food", "code": "G1"}),
                     ["meals", 0, "options", 0, "items", 0, "code"], id="codigo-de-otro-tipo"),
        pytest.param(lambda p: set_item(p, {"type": "recipe", "code": "R9"}),
                     ["meals", 0, "options", 0, "items", 0, "code"], id="receta-no-candidata"),
        pytest.param(lambda p: p["meals"].pop(), ["meals"], id="falta-un-tipo-de-comida"),
        pytest.param(lambda p: p["meals"][1].update(meal_type="breakfast"), ["meals", 1, "meal_type"],
                     id="tipo-de-comida-repetido"),
    ],
)
def test_salida_que_no_corresponde_a_la_solicitud_da_error_controlado(mutate, loc):
    use_provider(StubProvider(mutated_proposal(mutate)))

    response = post(payload())

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "INVALID_PROVIDER_OUTPUT"
    assert loc in [violation["loc"] for violation in error["details"]["errors"]]


def test_tipo_de_comida_no_solicitado_da_error_controlado():
    use_provider(StubProvider(json.dumps(valid_proposal())))
    body = payload()
    body["meal_types"] = ["breakfast", "lunch", "afternoon_snack"]

    response = post(body)

    assert response.status_code == 502
    assert ["meals", 3, "meal_type"] in [v["loc"] for v in response.json()["error"]["details"]["errors"]]


# --- Falla y timeout del proveedor -----------------------------------------------


def test_falla_del_proveedor_da_error_controlado_sin_respuesta_cruda():
    use_provider(FakeProvider(scenario="provider_error"))

    response = post(payload())

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "PROVIDER_ERROR"
    assert error["details"]["generation"]["raw_response"] is None
    assert error["details"]["errors"] is None


def test_timeout_informado_por_el_proveedor_da_504():
    use_provider(FakeProvider(scenario="timeout"))

    response = post(payload())

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "PROVIDER_TIMEOUT"


def test_proveedor_que_no_responde_dentro_del_limite_da_504():
    use_provider(StubProvider(json.dumps(valid_proposal()), delay_seconds=1))
    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="fake", provider_timeout_seconds=0.05, fake_provider_scenario="ok"
    )

    response = post(payload())

    assert response.status_code == 504
    error = response.json()["error"]
    assert error["code"] == "PROVIDER_TIMEOUT"
    assert error["details"]["generation"]["raw_response"] is None


def test_escenario_de_salida_invalida_del_proveedor_simulado_da_error_controlado():
    use_provider(FakeProvider(scenario="invalid_output"))

    response = post(payload())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_PROVIDER_OUTPUT"
