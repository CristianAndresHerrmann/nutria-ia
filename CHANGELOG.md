# Changelog — nutria-ia

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y [Semantic Versioning](https://semver.org/lang/es/). Nunca se documentan credenciales (claves de API, tokens, secrets) aquí.

## Unreleased

### Added

- `POST /plan-proposals` (T33; DA-28): genera una propuesta de plan alimentario a partir del contexto anonimizado del paciente.
  - **Entrada:** contrato Pydantic estricto (`extra="forbid"`). Un campo no declarado, un tipo de comida desconocido o repetido, un código de catálogo repetido o un grupo inexistente dan `422` sin llamar al proveedor (RNF-07). El catálogo y las recetas candidatas viajan con códigos cortos, nunca con UUID.
  - **Salida:** seis textos (sin recomendaciones clínicas) y comidas → opciones → ítems. Cada ítem referencia un código de catálogo, un código de receta o es texto libre marcado, sin cantidades (RF-35). La respuesta informa la versión de la plantilla, el proveedor, el modelo, la duración y los tokens.
  - **Errores controlados**, con código estable y recuperables: `PROVIDER_TIMEOUT` (`504`), `PROVIDER_ERROR` e `INVALID_PROVIDER_OUTPUT` (`502`). Una salida que no respeta el esquema o usa un código que no se envió es `INVALID_PROVIDER_OUTPUT`.
  - **Plantillas de prompt versionadas** en archivos (`app/prompts/templates/plan_proposal_v1.txt`).
  - **Interfaz común de proveedor** y proveedor simulado determinístico (`AI_PROVIDER=fake`), con escenarios para provocar cada error (`FAKE_PROVIDER_SCENARIO`: `ok`, `timeout`, `provider_error`, `invalid_output`). El tiempo límite se configura con `AI_PROVIDER_TIMEOUT_SECONDS` (25 s por defecto).
  - Tests de contrato, de validación de entrada y salida, de errores y de versionado de prompts.
- CI (`.github/workflows/ci.yml`): lint con `ruff`, tests con `pytest`, auditoría de dependencias con `pip-audit`, build de la imagen y control de su tamaño (menos de 0,5 GB). Corre en PR hacia `development`, `staging` y `master`, en push a `development` y a mano.
- CD a staging (`.github/workflows/cd-staging.yml`): despliegue por SSH en la VM de OCI con cada push a `staging`. Reutiliza la CI: si falla, no se despliega.

### Changed

- `FoodCategoryType` suma `complementary` (T28; DA-32), igual que el enum de `schema.prisma` del backend. Sin este valor, un catálogo con un alimento complementario (azúcar, sal, condimentos, grasas sólidas, agua) daba `422` en cada generación. Las categorías de un alimento admiten hasta 7 valores.

## [0.0.1] - 2026-09-30

Incremento 1 (ver `docs/cierre-incremento-1.md` en el repo raíz).

### Added

- Estructura del servicio: FastAPI con Docker (`python:3.12-slim`).
- `GET /health`: devuelve `{ status, service, timestamp }`. Lo usa el backend para probar la comunicación con el servicio de IA (`GET /health/ia`, T7).
