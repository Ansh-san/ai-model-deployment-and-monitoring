"""
AirCast India — Pre-trained PM2.5 Forecast Model (static/simulated)
Simulates a trained Ridge + LightGBM ensemble for serving via FastAPI.
Author: Ansh Parashar
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, Any

# ── AQI breakpoints (CPCB) ────────────────────────────────────────────────────
AQI_CATEGORIES = [
    (30,  "Good",         "#4CAF50"),
    (60,  "Satisfactory", "#8BC34A"),
    (90,  "Moderate",     "#FFC107"),
    (120, "Poor",         "#FF5722"),
    (250, "Very Poor",    "#9C27B0"),
    (float("inf"), "Severe", "#B71C1C"),
]

CITY_BASELINES: Dict[str, float] = {
    "Delhi": 85.0, "Mumbai": 45.0, "Kolkata": 70.0, "Chennai": 35.0,
    "Hyderabad": 50.0, "Bengaluru": 40.0, "Ahmedabad": 65.0, "Pune": 48.0,
}


@dataclass
class PredictionInput:
    city: str
    temperature_c: float
    humidity_pct: float
    wind_speed_ms: float
    pressure_hpa: float
    pm25_lag_1h: float
    pm25_lag_24h: float
    hour: int
    day_of_week: int   # 0=Mon … 6=Sun
    month: int


@dataclass
class PredictionOutput:
    city: str
    pm25_forecast_24h: float
    aqi_category: str
    aqi_color: str
    confidence_interval_low: float
    confidence_interval_high: float
    model_version: str


def _aqi_category(pm25: float) -> tuple[str, str]:
    for threshold, label, color in AQI_CATEGORIES:
        if pm25 <= threshold:
            return label, color
    return "Severe", "#B71C1C"


def predict(inp: PredictionInput) -> PredictionOutput:
    """
    Simulated ensemble model (Ridge + LightGBM blend).
    In production this would load serialised model weights from disk/S3.
    The formula reproduces the key relationships identified during feature
    engineering: strong autoregressive signal, wind dispersal, humidity trap.
    """
    base = CITY_BASELINES.get(inp.city, 60.0)

    # Autoregressive component (dominant signal)
    ar_component = 0.65 * inp.pm25_lag_1h + 0.20 * inp.pm25_lag_24h

    # Meteorological correction
    wind_effect  = -3.5 * max(inp.wind_speed_ms, 0.1)
    humid_effect =  0.15 * max(inp.humidity_pct - 60, 0)
    temp_effect  = -0.8 * (inp.temperature_c - 20)

    # Diurnal pattern (morning peak ~8–10 h, evening peak ~20–22 h)
    diurnal = 8 * np.sin(2 * np.pi * (inp.hour / 24 - 0.25))

    # Season correction (winter months → higher PM2.5)
    seasonal = 10 if inp.month in [11, 12, 1, 2] else (-5 if inp.month in [6, 7, 8] else 0)

    raw_pred = (0.35 * base + ar_component + wind_effect
                + humid_effect + temp_effect + diurnal + seasonal)
    pm25_pred = float(np.clip(raw_pred, 1.0, 500.0))

    # Uncertainty (wider CI for extreme values)
    sigma = 8.0 + 0.05 * pm25_pred
    ci_low  = float(max(1.0, pm25_pred - 1.96 * sigma))
    ci_high = float(pm25_pred + 1.96 * sigma)

    category, color = _aqi_category(pm25_pred)
    return PredictionOutput(
        city=inp.city,
        pm25_forecast_24h=round(pm25_pred, 2),
        aqi_category=category,
        aqi_color=color,
        confidence_interval_low=round(ci_low, 2),
        confidence_interval_high=round(ci_high, 2),
        model_version="aircast-v1.0.0",
    )
