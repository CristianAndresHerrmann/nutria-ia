"""Contrato de GET /health.

Informa el proveedor y el modelo configurados para que el smoke test del CD distinga
el simulado del real sin generar nada (T74). Se leen del proveedor ya construido al
arrancar: ni se lo llama ni se exponen claves.
"""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(examples=["ok"])
    service: str = Field(examples=["nutria-ia"])
    provider: str = Field(
        description="Proveedor configurado (`AI_PROVIDER`): `fake` es el simulado, sin llamadas externas.",
        examples=["openai"],
    )
    model: str = Field(description="Modelo configurado (`AI_MODEL`).", examples=["gpt-6-luna"])
    timestamp: str = Field(description="Fecha y hora en UTC, ISO 8601.")
