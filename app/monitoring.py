"""
AirCast India — In-process metrics collector.
Tracks request counts, latency percentiles, prediction distribution,
error rates, and per-city stats for monitoring dashboards.
Author: Ansh Parashar
"""

import time
import threading
from collections import defaultdict, deque
from typing import Dict, Any


class MetricsCollector:
    """Thread-safe in-memory metrics store.

    In production this would flush to Prometheus / CloudWatch / Grafana.
    For this deployment simulation, all metrics are served via /metrics.
    """

    def __init__(self, latency_window: int = 1000):
        self._lock = threading.Lock()
        self._start_time = time.time()
        self.total_requests: int = 0
        self.total_errors: int = 0
        self._latencies: deque = deque(maxlen=latency_window)   # rolling window
        self._status_counts: Dict[int, int] = defaultdict(int)
        self._path_counts: Dict[str, int] = defaultdict(int)
        self._city_counts: Dict[str, int] = defaultdict(int)
        self._city_pm25_sum: Dict[str, float] = defaultdict(float)
        self._prediction_count: int = 0
        self._error_log: deque = deque(maxlen=100)              # last 100 errors

    def uptime(self) -> float:
        return time.time() - self._start_time

    def record_request(self, path: str, status_code: int, latency_ms: float):
        with self._lock:
            self.total_requests += 1
            self._latencies.append(latency_ms)
            self._status_counts[status_code] += 1
            self._path_counts[path] += 1
            if status_code >= 500:
                self.total_errors += 1

    def record_prediction(self, city: str, pm25: float, latency_ms: float):
        with self._lock:
            self._prediction_count += 1
            self._city_counts[city] += 1
            self._city_pm25_sum[city] += pm25

    def record_error(self, path: str, error: str):
        with self._lock:
            self.total_errors += 1
            self._error_log.append({
                "timestamp": time.time(),
                "path": path,
                "error": error,
            })

    def _percentile(self, p: float) -> float:
        if not self._latencies:
            return 0.0
        sorted_lat = sorted(self._latencies)
        idx = max(0, int(len(sorted_lat) * p / 100) - 1)
        return round(sorted_lat[idx], 2)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            city_stats = {}
            for city in self._city_counts:
                count = self._city_counts[city]
                city_stats[city] = {
                    "predictions": count,
                    "avg_pm25_forecast": round(self._city_pm25_sum[city] / count, 2) if count else 0,
                }
            return {
                "uptime_seconds": round(self.uptime(), 2),
                "total_requests": self.total_requests,
                "total_predictions": self._prediction_count,
                "total_errors": self.total_errors,
                "error_rate_pct": round(
                    100 * self.total_errors / max(self.total_requests, 1), 2
                ),
                "latency_ms": {
                    "p50": self._percentile(50),
                    "p90": self._percentile(90),
                    "p99": self._percentile(99),
                },
                "status_codes": dict(self._status_counts),
                "requests_by_path": dict(self._path_counts),
                "predictions_by_city": city_stats,
                "recent_errors": list(self._error_log)[-10:],
            }
