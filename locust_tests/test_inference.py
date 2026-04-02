"""
Locust test for Endpoint 1: /api/inference (standard request-response).

Metrics collected:
  - Total Response Time (ms) — Metric #3 (Locust native)
  - Throughput (req/s) — Metric #5 (Locust native)
  - Tail Latency p95/p99 (ms) — Metric #6 (Locust native)
  - Error Rate (%) — Metric #7 (Locust native)

Usage:
  cd /home/sanidhya/experiment
  locust -f locust_tests/test_inference.py --headless \
    -u <CONCURRENCY> -r <CONCURRENCY> \
    -t 60s --host http://localhost:8000 \
    --csv data/<framework>/inference/run<N>

All metrics for this endpoint are collected natively by Locust.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from locust import HttpUser, task, between

from common.config import USER_PROMPT


class InferenceUser(HttpUser):
    """Simulates users sending standard inference requests."""

    wait_time = between(0, 0)  # No wait — sustain maximum concurrency

    @task
    def inference(self):
        """Send a standard inference request and let Locust measure it."""
        self.client.post(
            "/api/inference",
            json={"prompt": USER_PROMPT},
            timeout=120,
        )