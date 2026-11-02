import logging

from fastapi import FastAPI

from app.api import health, plan_proposals
from app.config import get_settings
from app.errors import GenerationError, generation_error_handler
from app.prompts import require_template

# Sin esto, los logs de la aplicación (trazabilidad de cada generación) no salen:
# uvicorn solo configura sus propios loggers.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")

# Como el proveedor: una plantilla que no existe impide arrancar, en vez de
# fallar en la primera generación.
require_template(get_settings().plan_template)

app = FastAPI(
    title="nutria-ia",
    description="Servicio de generación asistida de NutrIA. Recibe un contexto anonimizado y devuelve "
    "una propuesta estructurada. No accede a la base ni aplica reglas clínicas.",
    version="0.1.0",
)

app.add_exception_handler(GenerationError, generation_error_handler)

app.include_router(health.router)
app.include_router(plan_proposals.router)
