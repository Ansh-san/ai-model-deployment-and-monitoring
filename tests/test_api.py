"""
AirCast India — API test suite.
Run: pytest tests/ -v
Author: Ansh Parashar
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

DEMO_PAYLOAD = {
    "city": "Delhi",
    "temperature_c": 18.0,
    "humidity_pct": 70.0,
    "wind_speed_ms": 2.5,
    "pressure_hpa": 1013.0,
    "pm25_lag_1h": 90.0,
    "pm25_lag_24h": 85.0,
    "hour": 9,
    "day_of_week": 2,
    "month": 12,
}


def test_health_returns_200():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_predict_delhi():
    r = client.post("/predict", json=DEMO_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == "Delhi"
    assert body["pm25_forecast_24h"] > 0
    assert body["aqi_category"] in [
        "Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"
    ]
    assert body["confidence_interval_low"] < body["pm25_forecast_24h"]
    assert body["confidence_interval_high"] > body["pm25_forecast_24h"]


def test_predict_all_cities():
    cities = ["Delhi","Mumbai","Kolkata","Chennai","Hyderabad","Bengaluru","Ahmedabad","Pune"]
    for city in cities:
        payload = {**DEMO_PAYLOAD, "city": city}
        r = client.post("/predict", json=payload)
        assert r.status_code == 200, f"Failed for {city}"


def test_invalid_city_returns_422():
    payload = {**DEMO_PAYLOAD, "city": "London"}
    r = client.post("/predict", json=payload)
    assert r.status_code == 422


def test_missing_field_returns_422():
    payload = {k: v for k, v in DEMO_PAYLOAD.items() if k != "wind_speed_ms"}
    r = client.post("/predict", json=payload)
    assert r.status_code == 422


def test_out_of_range_humidity_returns_422():
    payload = {**DEMO_PAYLOAD, "humidity_pct": 150}
    r = client.post("/predict", json=payload)
    assert r.status_code == 422


def test_metrics_endpoint():
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "total_requests" in body
    assert "latency_ms" in body


def test_demo_endpoint():
    r = client.get("/predict/demo")
    assert r.status_code == 200
    assert r.json()["demo"] is True


def test_cities_endpoint():
    r = client.get("/cities")
    assert r.status_code == 200
    assert "Delhi" in r.json()["cities"]
