FROM node:22-slim AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        poppler-utils \
        tesseract-ocr \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid 10001 --create-home --home-dir /home/appuser --shell /usr/sbin/nologin appuser

COPY --chown=appuser:appuser backend ./backend
COPY --from=frontend-builder --chown=appuser:appuser /build/frontend/dist ./frontend/dist

RUN mkdir -p /data/uploads /data/backups \
    && chown -R appuser:appuser /app /data

USER appuser:appuser

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
