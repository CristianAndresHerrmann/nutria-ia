import hashlib

import pytest

from app.prompts import (
    PLAN_PROPOSAL_TEMPLATE_VERSION,
    TEMPLATES_DIR,
    load_template,
    render_plan_prompt,
    require_template,
)
from app.schemas.plan_proposal import PLAN_PROPOSAL_REQUEST_EXAMPLE, PlanProposalRequest

# Hash de cada versión publicada. Si este test falla porque cambió el texto de una
# plantilla, el cambio va en una versión nueva (un archivo nuevo) y se agrega acá; la
# versión anterior no se toca, para que cada generación registrada siga apuntando al
# texto que la produjo.
TEMPLATE_HASHES = {
    "plan_proposal_v1": "198b65d6e82951aa2c6e24c9d5de64023d20062ef1ddcff1ef93aac3fab0ed01",
    # Salida más corta, para medir el tiempo (T41). No es la vigente.
    "plan_proposal_v2": "86c86b16bcdb920257ac9815018979a7087374f9efa67cb2361bba0911c301d6",
    # La v1 con el objetivo del paciente. No es la vigente.
    "plan_proposal_v3": "c424d5bcb820c82b13195ae6b76a11f3cd414410aa7935e96c864b4fb05733d5",
    # La v3 con la variante para una intolerancia, la fruta de postre y sin repetir el texto de uso (DA-43). La vigente.
    "plan_proposal_v4": "f5d2f1e9f2e4360e3551ed4753b42cae3e066dc995e77ca0bbff877046c658f6",
}


def test_ninguna_plantilla_cambio_sin_cambiar_de_version():
    versions = sorted(path.stem for path in TEMPLATES_DIR.glob("*.txt"))

    assert versions == sorted(TEMPLATE_HASHES)
    for version in versions:
        digest = hashlib.sha256(load_template(version).encode("utf-8")).hexdigest()
        assert digest == TEMPLATE_HASHES[version], f"{version} cambió: crear una versión nueva"


def test_la_version_vigente_existe():
    assert PLAN_PROPOSAL_TEMPLATE_VERSION in TEMPLATE_HASHES


def test_una_plantilla_no_publicada_no_se_puede_elegir():
    assert require_template("plan_proposal_v2") == "plan_proposal_v2"
    with pytest.raises(ValueError, match="AI_PLAN_TEMPLATE"):
        require_template("plan_proposal_v9")


def test_el_prompt_usa_la_version_pedida():
    request = PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE)

    assert render_plan_prompt(request) != render_plan_prompt(request, "plan_proposal_v2")
    assert "2 o 3 opciones" in render_plan_prompt(request, "plan_proposal_v2")


def test_la_vigente_pide_orientar_la_propuesta_al_objetivo_y_lleva_el_objetivo_en_el_contexto():
    request = PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE)

    prompt = render_plan_prompt(request)

    assert PLAN_PROPOSAL_TEMPLATE_VERSION == "plan_proposal_v4"
    assert 'Si figura "goal"' in prompt
    assert '"goal": "Ordenar las comidas de la semana"' in prompt


def test_el_prompt_incluye_el_contexto_de_la_solicitud():
    request = PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE)

    prompt = render_plan_prompt(request)

    assert request.model_dump_json(indent=2) in prompt
    assert "$context" not in prompt


def test_la_vigente_pide_la_variante_para_una_intolerancia_y_la_fruta_de_postre_sin_repetir_el_texto_de_uso():
    request = PlanProposalRequest.model_validate(PLAN_PROPOSAL_REQUEST_EXAMPLE)

    prompt = render_plan_prompt(request)

    assert '"Leche deslactosada" frente a una intolerancia a "Leche"' in prompt
    assert "No lo hagas ante una alergia ni un rechazo." in prompt
    assert "fruta fresca de postre" in prompt
    assert "el plan ya incluye ese texto" in prompt
