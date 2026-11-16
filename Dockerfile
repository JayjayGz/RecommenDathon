FROM node:24-bookworm-slim AS node
FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
COPY backend/requirements-lambda.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/src/ /app/backend/src/
COPY plateforme/ /app/plateforme/
COPY scripts/start_local.mjs /app/scripts/start_local.mjs
COPY dataset/ /app/dataset/
COPY profiles.json /app/profiles.json

ENV ALPHAFORGE_MODE=local \
    WEB_HOST=0.0.0.0 \
    PORT=10000 \
    BACKEND_PORT=8000 \
    PYTHON_EXECUTABLE=python \
    PYTHONUNBUFFERED=1 \
    AUDIT_DIR=/tmp/alphaforge-audit

EXPOSE 10000
CMD ["node", "scripts/start_local.mjs"]
