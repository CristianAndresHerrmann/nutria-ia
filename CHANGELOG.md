# Changelog — nutria-ia

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y [Semantic Versioning](https://semver.org/lang/es/). Nunca se documentan credenciales (claves de API, tokens, secrets) aquí.

## Unreleased

## [0.0.3] - 2026-11-01

Incremento 3 (ver `docs/cierre-incremento-3.md` en el repo raíz).

### Added

- Tokens de razonamiento y plantilla seleccionable (T41, para atribuir y reducir el tiempo de la generación). Resultados en `docs/mediciones-de-generacion/` (repo raíz).
  - `generation.reasoning_tokens` en la respuesta y en los errores con traza: la parte de `output_tokens` que el modelo usó para razonar (OpenAI `output_tokens_details.reasoning_tokens`; Gemini `thoughts_token_count`). `null` si el proveedor no la informa. El contrato versionado (`contracts/openapi.json`) y su copia en el backend se actualizaron con `npm run contract:ia:update`.
  - `AI_PLAN_TEMPLATE` elige la plantilla entre las publicadas (`plan_proposal_v1` por defecto). Una que no existe impide arrancar. La traza registra la versión usada.
  - Plantilla `plan_proposal_v2`: la v1 con 2 o 3 opciones por comida y textos de hasta dos oraciones. Publicada para medir; la vigente sigue siendo la v1.

- Adaptadores de Gemini y OpenAI (T36; insumo de DA-12), detrás de la interfaz común de proveedor. Fundamento y política de datos de cada API en `docs/decisiones/adaptadores-de-proveedores-de-ia.md` (repo raíz).
  - **Configuración:** `AI_PROVIDER=gemini|openai`, con `AI_MODEL` y la clave del proveedor (`GEMINI_API_KEY`, `OPENAI_API_KEY`) solo en `.env` (RNF-06). Si falta el modelo o la clave, o el nivel de razonamiento no es válido, el servicio no arranca. Reemplazan a las reservadas `AI_PROVIDER_API_KEY` y `AI_PROVIDER_BASE_URL`.
  - **Salida estructurada** con un JSON Schema derivado del contrato (`PlanProposal`) y reducido al modo estricto de ambos proveedores. El de Gemini va sin `maxItems`, porque con los límites anidados del contrato la API responde `400`. La validación estricta del servicio no cambia.
  - **Razonamiento** configurable con `AI_REASONING_LEVEL`, `low` por defecto, por la meta de latencia.
  - Al proveedor solo viaja el prompt renderizado (RNF-07). Los dos se llaman con `store=false`: OpenAI no guarda la respuesta y Gemini no registra la solicitud en el proyecto. Ningún SDK reintenta: el tiempo límite cubre la generación completa (RNF-02).
  - Los errores del SDK se traducen a los errores controlados existentes: timeout → `PROVIDER_TIMEOUT`; error HTTP, de conexión, rechazo o respuesta sin texto → `PROVIDER_ERROR`; texto fuera de contrato (incluida una respuesta truncada) → `INVALID_PROVIDER_OUTPUT`. Los tokens de salida incluyen los de razonamiento en los dos.
  - Tests con el cliente de cada proveedor simulado y respuestas del SDK reales, sin red ni claves.
- AUD-004: contrato OpenAPI versionado y test que exige actualizarlo si cambia lo publicado por FastAPI. `scripts/export_openapi.py`, ejecutado por `npm run contract:ia:update` desde `nutria/`, actualiza las copias de IA y backend dentro de Docker; la exportación no entra en la imagen de runtime.

- `POST /plan-proposals` (T33; DA-28): genera una propuesta de plan alimentario a partir del contexto anonimizado del paciente.
  - **Entrada:** contrato Pydantic estricto (`extra="forbid"`). Un campo no declarado, un tipo de comida desconocido o repetido, un código de catálogo repetido o un grupo inexistente dan `422` sin llamar al proveedor (RNF-07). El catálogo y las recetas candidatas viajan con códigos cortos, nunca con UUID.
  - **Salida:** seis textos (sin recomendaciones clínicas) y comidas → opciones → ítems. Cada ítem referencia un código de catálogo, un código de receta o es texto libre marcado, sin cantidades (RF-35). La respuesta informa la versión de la plantilla, el proveedor, el modelo, la duración y los tokens.
  - **Errores controlados**, con código estable y recuperables: `PROVIDER_TIMEOUT` (`504`), `PROVIDER_ERROR` e `INVALID_PROVIDER_OUTPUT` (`502`). Una salida que no respeta el esquema o usa un código que no se envió es `INVALID_PROVIDER_OUTPUT`.
  - **Plantillas de prompt versionadas** en archivos (`app/prompts/templates/plan_proposal_v1.txt`).
  - **Interfaz común de proveedor** y proveedor simulado determinístico (`AI_PROVIDER=fake`), con escenarios para provocar cada error (`FAKE_PROVIDER_SCENARIO`: `ok`, `timeout`, `provider_error`, `invalid_output`). El tiempo límite se configura con `AI_PROVIDER_TIMEOUT_SECONDS` (25 s por defecto).
  - Tests de contrato, de validación de entrada y salida, de errores y de versionado de prompts.

### Changed

- `FoodCategoryType` suma `complementary` (T28; DA-32), igual que el enum de `schema.prisma` del backend. Sin este valor, un catálogo con un alimento complementario (azúcar, sal, condimentos, grasas sólidas, agua) daba `422` en cada generación. Las categorías de un alimento admiten hasta 7 valores.

### Fixed

- AUD-003: `python run.py` inicia Uvicorn sin recarga automática, incluida la imagen de runtime usada en staging. La recarga para desarrollo se activa con un comando explícito. Se elimina `PORT` de `.env.example` porque el servicio usa el puerto interno fijo 8000.

## [0.0.2] - 2026-10-25

Incremento 2 (ver `docs/cierre-incremento-2.md` en el repo raíz).

### Added

- CI (`.github/workflows/ci.yml`): lint con `ruff`, tests con `pytest`, auditoría de dependencias con `pip-audit`, build de la imagen y control de su tamaño (menos de 0,5 GB). Corre en PR hacia `development`, `staging` y `master`, en push a `development` y a mano.
- CD a staging (`.github/workflows/cd-staging.yml`): despliegue por SSH en la VM de OCI con cada push a `staging`. Reutiliza la CI: si falla, no se despliega.

## [0.0.1] - 2026-09-30

Incremento 1 (ver `docs/cierre-incremento-1.md` en el repo raíz).

### Added

- Estructura del servicio: FastAPI con Docker (`python:3.12-slim`).
- `GET /health`: devuelve `{ status, service, timestamp }`. Lo usa el backend para probar la comunicación con el servicio de IA (`GET /health/ia`, T7).
