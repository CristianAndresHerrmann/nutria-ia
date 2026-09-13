from fastapi import FastAPI

from app.api import health

app = FastAPI(
    title="nutria-ia",
    description="Servicio de generación asistida de NutrIA. Esqueleto sin integración "
    "con proveedor externo de IA (Incremento 1).",
    version="0.1.0",
)

app.include_router(health.router)
