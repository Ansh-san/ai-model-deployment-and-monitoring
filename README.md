# AirCast India — Week 5: Deployment & Monitoring

**Author:** Ansh Parashar | **Week 5 Task**

---

## Overview

A production-ready FastAPI service that serves 24-hour PM2.5 and AQI forecasts for 8 Indian cities, containerised with Docker.

## Repository Structure

```
week5-deployment/
├── app/
│   ├── main.py          ← FastAPI application (endpoints, middleware, logging)
│   ├── model.py         ← Simulated pre-trained ensemble model (Ridge + LightGBM)
│   ├── monitoring.py    ← In-process metrics collector (requests, latency, errors)
│   └── requirements.txt
├── tests/
│   └── test_api.py      ← Pytest test suite (10 tests)
├── monitoring/
│   └── prometheus.yml   ← Prometheus scrape config
├── Dockerfile           ← Multi-stage build (builder + slim runtime)
├── docker-compose.yml
└── README.md
```

## Quick Start

### Option A — Docker Compose (recommended)
```bash
docker compose up --build
# API available at http://localhost:8000
# Swagger UI at  http://localhost:8000/docs
```

### Option B — Local (no Docker)
```bash
pip install -r app/requirements.txt
cd app && uvicorn main:app --reload --port 8000
```

### Option C — Run tests
```bash
pip install fastapi uvicorn pydantic numpy httpx pytest
pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness/readiness probe |
| GET | `/metrics` | In-process metrics snapshot |
| POST | `/predict` | 24-h PM2.5 + AQI forecast |
| GET | `/predict/demo` | Pre-filled demo prediction |
| GET | `/cities` | List supported cities |
| GET | `/docs` | Swagger UI |

## Example Prediction Request

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Delhi",
    "temperature_c": 14.0,
    "humidity_pct": 78.0,
    "wind_speed_ms": 1.2,
    "pressure_hpa": 1015.0,
    "pm25_lag_1h": 95.0,
    "pm25_lag_24h": 88.0,
    "hour": 8,
    "day_of_week": 1,
    "month": 12
  }'
```

Example response:
```json
{
  "request_id": "a3f8c1d2",
  "city": "Delhi",
  "pm25_forecast_24h": 112.4,
  "aqi_category": "Poor",
  "confidence_interval_low": 96.8,
  "confidence_interval_high": 128.0,
  "model_version": "aircast-v1.0.0",
  "latency_ms": 3.2
}
```

## Health Check

Docker and docker-compose both run the health check automatically every 30 s:
```
GET /health  →  {"status": "healthy", "uptime_seconds": ..., ...}
```

---
*Part of the AirCast India AI project — Week 5 Deployment & Monitoring.*
