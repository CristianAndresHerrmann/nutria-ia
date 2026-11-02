import copy

import jsonschema
import pytest

from app.providers.fake import simulated_proposal
from app.providers.schema import RESPONSE_SCHEMA
from app.schemas.plan_proposal import PLAN_PROPOSAL_REQUEST_EXAMPLE, PlanProposalRequest

proposal = simulated_proposal(PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE))


def nodes(node):
    yield node
    for value in node.get("properties", {}).values():
        yield from nodes(value)
    if "items" in node:
        yield from nodes(node["items"])
    for option in node.get("anyOf", []):
        yield from nodes(option)


def test_no_usa_palabras_clave_fuera_del_modo_estricto_de_los_proveedores():
    unsupported = {"$ref", "$defs", "oneOf", "discriminator", "const", "default", "title", "description",
                   "minLength", "maxLength", "pattern"}

    for node in nodes(RESPONSE_SCHEMA):
        assert not unsupported & set(node), node


def test_cada_objeto_requiere_todas_sus_propiedades_y_no_admite_otras():
    objects = [node for node in nodes(RESPONSE_SCHEMA) if node.get("type") == "object"]

    assert objects
    for node in objects:
        assert node["required"] == list(node["properties"])
        assert node["additionalProperties"] is False


def test_una_propuesta_que_cumple_el_contrato_cumple_el_esquema():
    jsonschema.validate(proposal, RESPONSE_SCHEMA)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda p: p["meals"][0]["options"][0]["items"][0].update(grams=100), id="cantidad-en-gramos"),
        pytest.param(lambda p: p.update(clinical_recommendations="texto"), id="recomendaciones-clinicas"),
        pytest.param(lambda p: p["meals"][0]["options"][0]["items"].append({"type": "unknown", "code": "A1"}),
                     id="tipo-de-item-desconocido"),
        pytest.param(lambda p: p["meals"][0].update(meal_type="brunch"), id="tipo-de-comida-desconocido"),
    ],
)
def test_el_esquema_rechaza_lo_que_el_contrato_no_admite(mutate):
    invalid = copy.deepcopy(proposal)
    mutate(invalid)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, RESPONSE_SCHEMA)
