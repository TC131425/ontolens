# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS python-build
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=0 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --locked --no-dev --extra web --extra pdf --no-editable --python /usr/local/bin/python

FROM python:3.12-slim-bookworm AS runtime
RUN groupadd --gid 1000 ontolens && useradd --uid 1000 --gid 1000 --create-home ontolens \
    && mkdir /data && chown ontolens:ontolens /data
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ontolens-browsers
RUN --mount=type=bind,from=python-build,source=/app/.venv/lib/python3.12/site-packages/playwright/driver,target=/opt/playwright-driver \
    /opt/playwright-driver/node /opt/playwright-driver/package/cli.js install --with-deps --only-shell chromium \
    && chmod -R a+rX /opt/ontolens-browsers \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python-build /app/.venv /app/.venv
COPY --from=frontend /frontend/dist /app/frontend
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    ONTOLENS_DATA_ROOT=/data ONTOLENS_STATIC_DIR=/app/frontend
WORKDIR /data
USER ontolens
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["uvicorn", "ontolens.deployment:create_container_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
