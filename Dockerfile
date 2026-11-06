# ── Stage 1: build dependencies ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY app/requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --target=/build/deps -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="Ansh Parashar"
LABEL description="AirCast India — PM2.5 Forecast API"
LABEL version="1.0.0"

# Non-root user for security
RUN groupadd -r aircast && useradd -r -g aircast aircast

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /build/deps /usr/local/lib/python3.11/site-packages/

# Copy application source
COPY app/ /app/

# Ensure log directory exists and is writable
RUN mkdir -p /app/logs && chown -R aircast:aircast /app

USER aircast

# Expose FastAPI port
EXPOSE 8000

# Health check — Docker will mark the container unhealthy if this fails
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start Uvicorn with 2 workers, JSON access log
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
