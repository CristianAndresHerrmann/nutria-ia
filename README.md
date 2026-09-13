# nutria-ia

Servicio de inteligencia artificial de **NutrIA**, implementado en Python + FastAPI. Recibe del backend un contexto mínimo y anonimizado del paciente, construye la solicitud al proveedor externo de IA y normaliza la respuesta a un esquema estructurado. No accede a la base de datos operativa ni aplica el motor de reglas clínicas, que reside en `nutria-backend`.

En el Incremento 1 este servicio queda como esqueleto (endpoint de salud y documentación automática), sin integración con ningún proveedor externo de IA.

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
- `app/api/health.py` — endpoint de salud del servicio.
- `run.py` — punto de entrada para levantar el servidor con un solo comando.
- `requirements.txt` — dependencias del entorno virtual.
- `Dockerfile` — imagen de este servicio, usada por el `docker-compose.yml` de `nutria-backend`.

## Variables de entorno

Copiar `.env.example` a `.env` (no se versiona) antes de ejecutar:

```bash
cp .env.example .env
```

`AI_PROVIDER_API_KEY` y `AI_PROVIDER_BASE_URL` quedan vacías en este incremento, ya que todavía no hay integración con un proveedor externo.

## Cómo ejecutar

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
python run.py
```

El servicio queda disponible en `http://localhost:8000`:

- `GET /health` — verificación de disponibilidad.
- `GET /docs` — documentación Swagger generada automáticamente por FastAPI.

Para levantar el stack completo con Docker (frontend + backend + ia + postgres + proxy) con un solo comando, ver la sección "Cómo ejecutar todo el stack con Docker Compose" en el README de `nutria-backend`. En ese modo el servicio se accede como `http://ia.local.nutria.com` (virtual host servido por Traefik).

## Tecnologías previstas

- Python
- FastAPI
- Uvicorn

## Repositorios relacionados

- `nutria-backend` — API principal (Node.js + Express).
- `nutria-frontend` — interfaz web (React + Vite).
