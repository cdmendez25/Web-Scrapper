# syntax=docker/dockerfile:1

# Un solo Dockerfile con dos objetivos (api y scraper) para no repetir la
# instalacion de dependencias: ambos comparten las etapas "deps" y "runtime".
# Se construye con --target api o --target scraper (ver docker-compose.yml).
#
# El contexto de build es la raiz del repo porque requirements.txt vive ahi.

# ---------------------------------------------------------------------------
# Etapa 1: dependencias. Se instalan en un venv aislado que luego se copia,
# asi la imagen final no arrastra la cache de pip ni herramientas de build.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS deps

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Se copia solo requirements.txt para que esta capa se reutilice mientras
# no cambien las dependencias, sin importar los cambios en el codigo.
COPY requirements.txt /tmp/requirements.txt

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Etapa 2: base comun de ejecucion (venv + usuario sin privilegios).
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=deps /opt/venv /opt/venv

# Usuario no-root; el HOME es necesario para Chrome en la imagen del scraper.
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

WORKDIR /app

# ---------------------------------------------------------------------------
# Objetivo: api (FastAPI + uvicorn). Se ejecuta desde /app, igual que en
# local se ejecuta desde backend/, para que "api.main:app" resuelva.
# ---------------------------------------------------------------------------
FROM runtime AS api

COPY --chown=appuser:appuser backend/api ./api

USER appuser
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Objetivo: scraper (job de un solo uso). Necesita Chromium y su driver
# dentro de la imagen; Selenium Manager detecta el chromedriver del PATH y
# no descarga nada porque la version coincide con la de Chromium.
# ---------------------------------------------------------------------------
FROM runtime AS scraper

# Los paquetes de sistema van antes del codigo para que la capa quede en cache.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Ruta del navegador para que Selenium no tenga que adivinarla.
ENV CHROME_BIN=/usr/bin/chromium

COPY --chown=appuser:appuser backend/scripts ./scripts

USER appuser

# El termino de busqueda se pasa como argumento:
#   docker compose run --rm scraper cafe
# Sin argumento queda el default del propio script ("arroz").
ENTRYPOINT ["python", "scripts/scraper.py"]
CMD ["arroz"]
