"""
AirCast India — FastAPI Service
Serves 24-hour PM2.5 forecasts for 8 Indian cities.
Author: Ansh Parashar
"""

import time
import uuid
import logging
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from model import PredictionInput, predict, CITY_BASELINES
from monitoring import MetricsCollector

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("aircast")

VALID_CITIES = set(CITY_BASELINES.keys())

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AirCast India",
    description="24-hour PM2.5 and AQI category forecast API for 8 Indian cities.",
    version="1.0.0",
    contact={"name": "Ansh Parashar"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

metrics = MetricsCollector()


# ── Request / Response schemas ────────────────────────────────────────────────
class ForecastRequest(BaseModel):
    city: str = Field(..., example="Delhi")
    temperature_c: float = Field(..., ge=-20, le=60, example=24.5)
    humidity_pct: float = Field(..., ge=0, le=100, example=65.0)
    wind_speed_ms: float = Field(..., ge=0, le=50, example=2.3)
    pressure_hpa: float = Field(..., ge=900, le=1100, example=1012.0)
    pm25_lag_1h: float = Field(..., ge=0, le=1000, example=78.4)
    pm25_lag_24h: float = Field(..., ge=0, le=1000, example=82.1)
    hour: int = Field(..., ge=0, le=23, example=14)
    day_of_week: int = Field(..., ge=0, le=6, example=2)
    month: int = Field(..., ge=1, le=12, example=11)

    @field_validator("city")
    @classmethod
    def city_must_be_valid(cls, v):
        if v not in VALID_CITIES:
            raise ValueError(f"city must be one of {sorted(VALID_CITIES)}")
        return v


class ForecastResponse(BaseModel):
    request_id: str
    timestamp_utc: str
    city: str
    pm25_forecast_24h: float
    aqi_category: str
    aqi_color: str
    confidence_interval_low: float
    confidence_interval_high: float
    model_version: str
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    total_requests: int
    total_errors: int
    model_version: str


# ── Middleware: request logging + latency ────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    start  = time.time()
    response = await call_next(request)
    latency = (time.time() - start) * 1000
    logger.info(
        json.dumps({
            "req_id": req_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round(latency, 2),
        })
    )
    metrics.record_request(
        path=request.url.path,
        status_code=response.status_code,
        latency_ms=latency,
    )
    return response


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "AirCast India API — visit /docs for Swagger UI"}


@app.get("/health", response_model=HealthResponse, tags=["Operations"])
async def health():
    """Liveness and readiness probe. Returns service health and uptime."""
    return HealthResponse(
        status="healthy",
        uptime_seconds=round(metrics.uptime(), 2),
        total_requests=metrics.total_requests,
        total_errors=metrics.total_errors,
        model_version="aircast-v1.0.0",
    )


@app.get("/metrics", tags=["Operations"])
async def get_metrics():
    """Prometheus-style metrics snapshot for monitoring dashboards."""
    return metrics.snapshot()


@app.post("/predict", response_model=ForecastResponse, tags=["Forecast"])
async def forecast(req: ForecastRequest):
    """
    Predict next-24-hour PM2.5 and AQI category for a given city and
    current meteorological conditions.
    """
    req_id = str(uuid.uuid4())[:8]
    start  = time.time()

    try:
        inp = PredictionInput(
            city=req.city,
            temperature_c=req.temperature_c,
            humidity_pct=req.humidity_pct,
            wind_speed_ms=req.wind_speed_ms,
            pressure_hpa=req.pressure_hpa,
            pm25_lag_1h=req.pm25_lag_1h,
            pm25_lag_24h=req.pm25_lag_24h,
            hour=req.hour,
            day_of_week=req.day_of_week,
            month=req.month,
        )
        result = predict(inp)
        latency = (time.time() - start) * 1000
        metrics.record_prediction(city=req.city, pm25=result.pm25_forecast_24h, latency_ms=latency)

        logger.info(json.dumps({
            "req_id": req_id,
            "event": "prediction",
            "city": req.city,
            "pm25_forecast": result.pm25_forecast_24h,
            "aqi": result.aqi_category,
            "latency_ms": round(latency, 2),
        }))

        return ForecastResponse(
            request_id=req_id,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            city=result.city,
            pm25_forecast_24h=result.pm25_forecast_24h,
            aqi_category=result.aqi_category,
            aqi_color=result.aqi_color,
            confidence_interval_low=result.confidence_interval_low,
            confidence_interval_high=result.confidence_interval_high,
            model_version=result.model_version,
            latency_ms=round(latency, 2),
        )

    except Exception as exc:
        metrics.record_error(path="/predict", error=str(exc))
        logger.error(json.dumps({"req_id": req_id, "event": "error", "detail": str(exc)}))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.get("/cities", tags=["Forecast"])
async def list_cities():
    """Return the list of supported cities."""
    return {"cities": sorted(VALID_CITIES)}


@app.get("/predict/demo", tags=["Forecast"])
async def demo_prediction():
    """
    Returns a pre-filled example prediction for Delhi in winter.
    Useful for smoke-testing the deployment without constructing a request body.
    """
    from fastapi.testclient import TestClient
    demo_payload = {
        "city": "Delhi", "temperature_c": 14.0, "humidity_pct": 78.0,
        "wind_speed_ms": 1.2, "pressure_hpa": 1015.0,
        "pm25_lag_1h": 95.0, "pm25_lag_24h": 88.0,
        "hour": 8, "day_of_week": 1, "month": 12,
    }
    inp = PredictionInput(**demo_payload)
    result = predict(inp)
    return {
        "demo": True,
        "input": demo_payload,
        "output": {
            "pm25_forecast_24h": result.pm25_forecast_24h,
            "aqi_category": result.aqi_category,
            "confidence_interval": [result.confidence_interval_low, result.confidence_interval_high],
            "model_version": result.model_version,
        },
    }
