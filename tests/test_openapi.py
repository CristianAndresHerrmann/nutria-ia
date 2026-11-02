import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_el_openapi_versionado_coincide_con_el_servicio():
    snapshot = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"
    assert client.get("/openapi.json").json() == json.loads(snapshot.read_text(encoding="utf-8")), (
        "Cambió el contrato de IA. Revisar compatibilidad y ejecutar "
        "npm run contract:ia:update desde nutria/; verificar también los tests del backend."
    )


def test_el_contrato_de_plan_proposals_figura_en_el_spec():
    spec = client.get("/openapi.json").json()

    operation = spec["paths"]["/plan-proposals"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PlanProposalRequest"
    )
    responses = operation["responses"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PlanProposalResponse")
    assert "422" in responses
    for status in ("502", "504"):
        assert responses[status]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/GenerationErrorResponse"
        )

    schemas = spec["components"]["schemas"]
    assert schemas["PlanProposalRequest"]["additionalProperties"] is False
    assert schemas["PlanProposalRequest"]["examples"]
