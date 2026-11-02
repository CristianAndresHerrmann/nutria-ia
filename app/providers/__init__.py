from app.config import Settings, get_settings
from app.providers import gemini, openai
from app.providers.base import PlanProvider
from app.providers.fake import FakeProvider


def build_provider(settings: Settings) -> PlanProvider:
    if settings.ai_provider == "fake":
        return FakeProvider(scenario=settings.fake_provider_scenario)
    if settings.ai_provider == "gemini":
        return gemini.GeminiProvider(
            model=_required(settings.ai_model, "AI_MODEL", "gemini"),
            reasoning_level=settings.ai_reasoning_level,
            client=gemini.build_client(
                _required(settings.gemini_api_key, "GEMINI_API_KEY", "gemini"), settings.provider_timeout_seconds
            ),
        )
    if settings.ai_provider == "openai":
        return openai.OpenAIProvider(
            model=_required(settings.ai_model, "AI_MODEL", "openai"),
            reasoning_level=settings.ai_reasoning_level,
            client=openai.build_client(
                _required(settings.openai_api_key, "OPENAI_API_KEY", "openai"), settings.provider_timeout_seconds
            ),
        )
    raise ValueError(f"AI_PROVIDER desconocido: {settings.ai_provider!r}")


def _required(value: str | None, variable: str, provider: str) -> str:
    if not value:
        raise ValueError(f"{variable} es obligatoria con AI_PROVIDER={provider}")
    return value


# Se arma al importar: una configuración inválida impide que el servicio arranque,
# en vez de fallar en la primera generación.
_provider = build_provider(get_settings())


def get_provider() -> PlanProvider:
    return _provider
