"""Plantillas de prompt versionadas.

Cada versión es un archivo en templates/ que no se edita una vez publicado: un
cambio de texto es una versión nueva. tests/test_prompts.py guarda el hash de cada
una y falla si el texto cambia sin cambiar la versión.
"""

from pathlib import Path
from string import Template

from app.schemas.plan_proposal import PlanProposalRequest

TEMPLATES_DIR = Path(__file__).parent / "templates"

PLAN_PROPOSAL_TEMPLATE_VERSION = "plan_proposal_v1"


def load_template(version: str) -> str:
    # Normaliza los fines de línea: el checkout en Windows puede convertirlos a CRLF.
    return (TEMPLATES_DIR / f"{version}.txt").read_text(encoding="utf-8").replace("\r\n", "\n")


def render_plan_prompt(request: PlanProposalRequest) -> str:
    template = Template(load_template(PLAN_PROPOSAL_TEMPLATE_VERSION))
    return template.substitute(context=request.model_dump_json(indent=2))
