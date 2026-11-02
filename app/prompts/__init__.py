"""Plantillas de prompt versionadas.

Cada versión es un archivo en templates/ que no se edita una vez publicado: un
cambio de texto es una versión nueva. tests/test_prompts.py guarda el hash de cada
una y falla si el texto cambia sin cambiar la versión.
"""

from pathlib import Path
from string import Template

from app.schemas.plan_proposal import PlanProposalRequest

TEMPLATES_DIR = Path(__file__).parent / "templates"

# La versión por defecto. AI_PLAN_TEMPLATE elige otra publicada, para comparar
# plantillas sin desplegar código (T41); la traza registra la que se usó.
PLAN_PROPOSAL_TEMPLATE_VERSION = "plan_proposal_v1"


def load_template(version: str) -> str:
    # Normaliza los fines de línea: el checkout en Windows puede convertirlos a CRLF.
    return (TEMPLATES_DIR / f"{version}.txt").read_text(encoding="utf-8").replace("\r\n", "\n")


def require_template(version: str) -> str:
    if not (TEMPLATES_DIR / f"{version}.txt").is_file():
        raise ValueError(f"AI_PLAN_TEMPLATE no es una plantilla publicada: {version!r}")
    return version


def render_plan_prompt(request: PlanProposalRequest, version: str = PLAN_PROPOSAL_TEMPLATE_VERSION) -> str:
    template = Template(load_template(version))
    return template.substitute(context=request.model_dump_json(indent=2))
