from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
