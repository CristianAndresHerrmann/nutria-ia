FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

# Solo para `npm run test:ia` (servicio ia-test del compose): suma las
# herramientas de desarrollo y los tests sobre la misma base que el runtime.
FROM base AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY pyproject.toml .
COPY tests ./tests

CMD ["pytest"]

# Última etapa = target por defecto: la que construyen el compose y la CI, sin
# dependencias de desarrollo.
FROM base AS runtime

EXPOSE 8000

CMD ["python", "run.py"]
