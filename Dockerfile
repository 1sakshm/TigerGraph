FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRAPHSENTINEL_MODE=demo \
    GRAPHSENTINEL_DB=/data/cases.sqlite \
    PORT=8000

COPY pyproject.toml README.md ./
COPY graphsentinel ./graphsentinel
COPY frontend ./frontend
COPY data/demo.json ./data/demo.json
COPY cases ./cases
RUN pip install --no-cache-dir . && \
    groupadd --system app && useradd --system --gid app app && \
    mkdir -p /data && chown app:app /data

USER app
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn graphsentinel.server:create_from_env --factory --host 0.0.0.0 --port ${PORT:-8000}"]
