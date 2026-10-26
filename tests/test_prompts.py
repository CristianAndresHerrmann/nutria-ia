import hashlib

from app.prompts import (
    PLAN_PROPOSAL_TEMPLATE_VERSION,
    TEMPLATES_DIR,
    load_template,
    render_plan_prompt,
)
from app.schemas.plan_proposal import PLAN_PROPOSAL_REQUEST_EXAMPLE, PlanProposalRequest

# Hash de cada versión publicada. Si este test falla porque cambió el texto de una
# plantilla, el cambio va en una versión nueva (un archivo nuevo) y se agrega acá; la
# versión anterior no se toca, para que cada generación registrada siga apuntando al
# texto que la produjo.
TEMPLATE_HASHES = {
    "plan_proposal_v1": "198b65d6e82951aa2c6e24c9d5de64023d20062ef1ddcff1ef93aac3fab0ed01",
}


def test_ninguna_plantilla_cambio_sin_cambiar_de_version():
    versions = sorted(path.stem for path in TEMPLATES_DIR.glob("*.txt"))

    assert versions == sorted(TEMPLATE_HASHES)
    for version in versions:
        digest = hashlib.sha256(load_template(version).encode("utf-8")).hexdigest()
        assert digest == TEMPLATE_HASHES[version], f"{version} cambió: crear una versión nueva"


def test_la_version_vigente_existe():
    assert PLAN_PROPOSAL_TEMPLATE_VERSION in TEMPLATE_HASHES


def test_el_prompt_incluye_el_contexto_de_la_solicitud():
    request = PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE)

    prompt = render_plan_prompt(request)

    assert request.model_dump_json(indent=2) in prompt
    assert "$context" not in prompt
