import os
from dataclasses import dataclass, field
from functools import cache


@dataclass(frozen=True)
class Settings:
    ai_provider: str
    provider_timeout_seconds: float
    fake_provider_scenario: str
    ai_model: str | None = None
    ai_reasoning_level: str = "low"
    # Fuera del repr: un log de la configuración nunca imprime una clave (RNF-06).
    gemini_api_key: str | None = field(default=None, repr=False)
    openai_api_key: str | None = field(default=None, repr=False)


@cache
def get_settings() -> Settings:
    return Settings(
        ai_provider=os.environ.get("AI_PROVIDER", "fake"),
        provider_timeout_seconds=float(os.environ.get("AI_PROVIDER_TIMEOUT_SECONDS", "25")),
        fake_provider_scenario=os.environ.get("FAKE_PROVIDER_SCENARIO", "ok"),
        # `or None`: en el .env una variable sin valor llega como cadena vacía.
        ai_model=os.environ.get("AI_MODEL") or None,
        ai_reasoning_level=os.environ.get("AI_REASONING_LEVEL") or "low",
        gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
    )
