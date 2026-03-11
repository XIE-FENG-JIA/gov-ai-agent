# === Stage 1: Builder ===
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
COPY pyproject.toml requirements-lock.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements-lock.txt

# === Stage 2: Runtime ===
FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ ./src/
COPY api_server.py config.yaml ./
COPY templates/ ./templates/

# Create non-root user
RUN useradd --create-home appuser && \
    mkdir -p /app/kb_data /app/output && \
    chown -R appuser:appuser /app
USER appuser

# Environment defaults
ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    API_WORKERS=1 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import requests; r=requests.get('http://localhost:8000/api/v1/health'); exit(0 if r.status_code==200 else 1)"

CMD ["python", "-m", "uvicorn", "api_server:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
