# nutria-ia

Servicio de inteligencia artificial de **NutrIA**, implementado en Python + FastAPI.
Recibe del backend un contexto mínimo y anonimizado, arma la solicitud al proveedor
externo de IA y devuelve una respuesta estructurada. No accede a la base de datos
operativa ni decide restricciones clínicas: el motor de reglas determinístico vive
en `nutria-backend`.

Qué expone el servicio y qué cambió en cada iteración no se documenta acá: el
contrato vigente se ve en la documentación automática de FastAPI (`/docs`).

## Estructura de carpetas raíz del proyecto

Este repositorio es uno de los tres repos que componen NutrIA (`nutria-frontend`, `nutria-backend`, `nutria-ia`) y debe clonarse como carpeta **hermana** de los otros dos, dentro de una misma carpeta raíz local:

```
NutrIA/
├── nutria-backend/
├── nutria-frontend/
└── nutria-ia/         (este repositorio)
```

Esta disposición es necesaria porque el `docker-compose.yml` de `nutria-backend` construye este servicio a partir de una ruta relativa (`../nutria-ia`).

## Estructura interna del repositorio

- `app/main.py` — instancia de la aplicación FastAPI y registro de routers.
- `app/api/` — un módulo por router.
- `app/schemas/` — contratos Pydantic de entrada y salida.
- `app/services/` — orquestación de cada generación (prompt, proveedor y validación de la respuesta).
- `app/providers/` — interfaz común de proveedor y sus implementaciones (hoy, el simulado).
- `app/prompts/templates/` — plantillas de prompt, un archivo por versión. Una versión publicada no se edita: un cambio de texto va en un archivo nuevo, y `tests/test_prompts.py` lo controla.
- `run.py` — punto de entrada para levantar el servidor con un solo comando.
- `requirements.txt` — dependencias del servicio.
- `requirements-dev.txt` — herramientas de desarrollo y CI (pytest, httpx, ruff, pip-audit). No entran en la imagen de runtime.
- `tests/` — tests de pytest.
- `contracts/openapi.json` — contrato OpenAPI versionado; pytest verifica que coincida con el generado por FastAPI.
- `scripts/export_openapi.py` — exporta ese contrato para actualizar las copias de IA y backend.
- `pyproject.toml` — configuración de pytest y ruff (las dependencias no van acá).
- `Dockerfile` — imagen de este servicio, en etapas: `runtime` (la última, la que usa el `docker-compose.yml` de `nutria-backend`) y `test`, que suma `requirements-dev.txt` y `tests/` para `npm run test:ia`.
- `.github/workflows/ci.yml` — integración continua (ver "Integración continua"); `cd-staging.yml` — despliegue a staging (ver "Despliegue en staging").

## Variables de entorno

Copiar `.env.example` a `.env` (no se versiona) antes de ejecutar:

```bash
cp .env.example .env
```

El servicio escucha en el puerto 8000, igual que el puerto interno configurado en
Docker y Traefik. `AI_PROVIDER_API_KEY` y `AI_PROVIDER_BASE_URL` están reservadas
para el proveedor externo de IA y no se versionan con valor.

| Variable | Default | Uso |
|---|---|---|
| `AI_PROVIDER` | `fake` | Proveedor que responde las generaciones. Hoy solo existe `fake`, el simulado. Un valor desconocido impide que el servicio arranque. |
| `AI_PROVIDER_TIMEOUT_SECONDS` | `25` | Tiempo máximo de espera al proveedor. Pasado ese tiempo, la generación responde `504 PROVIDER_TIMEOUT`. El tiempo máximo del backend para esta llamada tiene que ser mayor. |
| `FAKE_PROVIDER_SCENARIO` | `ok` | Solo con `AI_PROVIDER=fake`. `invalid_output`, `timeout` o `provider_error` hacen que cada generación termine en ese error controlado, para probar el manejo de errores del backend contra el stack real. |

Las tres tienen default, así que un `.env` anterior sigue funcionando sin cambios.

## Cómo ejecutar

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt -r requirements-dev.txt
python run.py
```

El servicio queda disponible en `http://localhost:8000`; `GET /health` sirve para
verificar que está arriba y `/docs` abre la documentación automática de FastAPI.

`python run.py` inicia Uvicorn sin recarga automática, tanto en local como en la
imagen de runtime usada en staging. Para desarrollar con recarga, ejecutar
explícitamente:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Para levantar el stack completo con Docker (frontend + backend + ia + postgres + proxy) con un solo comando, ver la sección "Cómo ejecutar todo el stack con Docker Compose" en el README de `nutria-backend`. En ese modo el servicio se accede como `http://ia.local.nutria.com` (virtual host servido por Traefik).

## Integración continua

`.github/workflows/ci.yml` corre en cada PR hacia `development`, `staging` o `master`, en cada
push a `development` y a mano desde la pestaña Actions (`workflow_dispatch`). El job
se llama `ci` y es el check obligatorio del ruleset de `development`, `staging` y `master`: un
PR no se puede mergear con ese check en rojo.

No usa secrets ni variables de GitHub: ningún test llama al proveedor externo de IA.
Un test que lo necesite usa un doble, nunca una API key.

Cada paso, y cómo reproducirlo en local desde la carpeta raíz `nutria/` (dentro del
contenedor de la etapa `test`; `C` abrevia `docker compose -f nutria-backend/docker-compose.yml`):

| Paso de la CI | En local |
|---|---|
| `pip install -r requirements.txt -r requirements-dev.txt` | Lo hace el build de la etapa `test` (`C build ia-test`). |
| `ruff check` | `C run --build --rm --no-deps ia-test ruff check` |
| `pytest` | `npm run test:ia` |
| `pip-audit -r requirements.txt` | `C run --build --rm --no-deps ia-test pip-audit -r requirements.txt` |
| `docker build` (sin push) y tamaño menor a 0,5 GB | `docker build -t nutria-ia:local nutria-ia` y `docker image inspect nutria-ia:local --format '{{.Size}}'` (bytes; el límite es 500 000 000). |

El límite de tamaño sostiene la decisión de usar ONNX Runtime en vez de PyTorch.

Cuando cambie intencionalmente el contrato, revisar la compatibilidad y ejecutar
`npm run contract:ia:update` desde la carpeta raíz `nutria/`: genera el OpenAPI
actual en este repo y en `nutria-backend`, dentro de Docker. Después ejecutar
`npm run test:ia` y `npm run test:backend` desde esa raíz. Las suites comprueban las
copias sin regenerarlas; cada CI funciona con su propio checkout. Los cambios del
contrato requieren actualizar ambos repos de forma coordinada antes de desplegar.

## Despliegue en staging

Un push a `staging` dispara `.github/workflows/cd-staging.yml`: corre el CI y, si
pasa, despliega el servicio `ia` en la VM de staging. En staging el servicio no tiene
ruta pública: el smoke test lo verifica a través del backend (`/health/ia`). Cómo
funciona, la configuración del Environment `staging` y la operación de la VM: README
de `nutria-backend`, sección "Staging".

## Stack

- Python
- FastAPI
- Uvicorn
- pytest y ruff (desarrollo y CI)

## Repositorios relacionados

- `nutria-backend` — API principal (Node.js + Express).
- `nutria-frontend` — interfaz web (React + Vite).
