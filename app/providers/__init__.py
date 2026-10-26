from app.config import Settings, get_settings
from app.providers.base import PlanProvider
from app.providers.fake import FakeProvider


def build_provider(settings: Settings) -> PlanProvider:
    if settings.ai_provider == "fake":
        return FakeProvider(scenario=settings.fake_provider_scenario)
    raise ValueError(f"AI_PROVIDER desconocido: {settings.ai_provider!r}")


# Se arma al importar: una configuración inválida impide que el servicio arranque,
# en vez de fallar en la primera generación.
_provider = build_provider(get_settings())


def get_provider() -> PlanProvider:
    return _provider
