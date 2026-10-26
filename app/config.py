import os
from dataclasses import dataclass
from functools import cache


@dataclass(frozen=True)
class Settings:
    ai_provider: str
    provider_timeout_seconds: float
    fake_provider_scenario: str


@cache
def get_settings() -> Settings:
    return Settings(
        ai_provider=os.environ.get("AI_PROVIDER", "fake"),
        provider_timeout_seconds=float(os.environ.get("AI_PROVIDER_TIMEOUT_SECONDS", "25")),
        fake_provider_scenario=os.environ.get("FAKE_PROVIDER_SCENARIO", "ok"),
    )
