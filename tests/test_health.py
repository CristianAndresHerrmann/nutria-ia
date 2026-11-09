from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers import get_provider
from app.providers.openai import OpenAIProvider

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


class RecordingClient:
    """Doble del cliente de openai: registra cualquier llamada para comprobar que el
    health no genera nada."""

    def __init__(self):
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)


def test_health_responde_ok_con_timestamp_utc():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "nutria-ia"
    assert datetime.fromisoformat(body["timestamp"]).utcoffset() is not None


def test_health_informa_el_simulado_cuando_es_el_proveedor_configurado():
    body = client.get("/health").json()

    assert (body["provider"], body["model"]) == ("fake", "fake-deterministic")


def test_health_informa_proveedor_y_modelo_reales_sin_llamar_al_proveedor():
    recording = RecordingClient()
    app.dependency_overrides[get_provider] = lambda: OpenAIProvider(
        model="gpt-6-luna", reasoning_level="low", client=recording
    )

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert (body["provider"], body["model"]) == ("openai", "gpt-6-luna")
    assert set(body) == {"status", "service", "provider", "model", "timestamp"}
    assert recording.calls == []
