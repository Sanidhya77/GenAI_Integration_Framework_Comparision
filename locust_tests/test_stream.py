"""
Locust test for Endpoint 2: /api/inference/stream (SSE streaming).

Metrics collected:
  - TTFT (ms) — Metric #1 (custom instrumentation)
  - TPOT (ms/token) — Metric #2 (custom instrumentation)
  - Total Response Time (ms) — Metric #3 (custom Locust event)
  - Connection Success Rate (%) — Metric #4 (custom tracking)
  - Throughput (req/s) — Metric #5 (Locust native)
  - Tail Latency p95/p99 (ms) — Metric #6 (Locust native)
  - Error Rate (%) — Metric #7 (Locust native)

Usage:
  cd /home/sanidhya/experiment
  locust -f locust_tests/test_stream.py --headless \
    -u <CONCURRENCY> -r <CONCURRENCY> \
    -t 60s --host http://localhost:8000 \
    --csv data/<framework>/stream/run<N>

Custom metrics (TTFT, TPOT, CSR) are saved to a separate CSV file
alongside the Locust CSV output.
"""

import csv
import json
import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from locust import HttpUser, task, between, events

from common.config import USER_PROMPT


# Custom metrics storage

# Thread-safe list to collect per-request streaming metrics
_stream_metrics = []
_metrics_lock = threading.Lock()


class StreamingUser(HttpUser):
    """Simulates users sending streaming inference requests."""

    wait_time = between(0, 0)  # No wait to sustain maximum concurrency

    @task
    def stream_inference(self):
        """Send a streaming request, parse SSE events, measure TTFT and TPOT."""
        request_start = time.perf_counter()
        ttft = None
        token_times = []
        token_count = 0
        success = False
        exception = None

        try:
            # Use requests directly for streaming (Locust client doesn't handle SSE iteration well)
            response = requests.post(
                f"{self.host}/api/inference/stream",
                json={"prompt": USER_PROMPT},
                stream=True,
                timeout=120,
            )

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            buffer = ""
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    buffer += chunk

                    while "\n\n" in buffer:
                        event, buffer = buffer.split("\n\n", 1)
                        event = event.strip()

                        if event.startswith("data: "):
                            data_str = event[6:]
                            now = time.perf_counter()

                            try:
                                data = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            if data.get("done"):
                                success = True
                                continue

                            token_count += 1
                            token_times.append(now)

                            if ttft is None:
                                ttft = (now - request_start) * 1000  # ms

        except Exception as e:
            exception = e

        request_end = time.perf_counter()
        total_time = (request_end - request_start) * 1000  # ms

        # Compute TPOT
        tpot = None
        if len(token_times) >= 2:
            streaming_duration = (token_times[-1] - token_times[0]) * 1000  # ms
            tpot = streaming_duration / (len(token_times) - 1)

        # Fire Locust event for response time tracking
        self.environment.events.request.fire(
            request_type="SSE",
            name="/api/inference/stream",
            response_time=total_time,
            response_length=token_count,
            exception=exception,
            context={},
        )

        # Store custom metrics
        with _metrics_lock:
            _stream_metrics.append({
                "timestamp": time.time(),
                "ttft_ms": round(ttft, 3) if ttft is not None else None,
                "tpot_ms": round(tpot, 3) if tpot is not None else None,
                "total_time_ms": round(total_time, 3),
                "token_count": token_count,
                "success": success,
            })



# Save custom metrics on test stop

@events.quitting.add_listener
def save_custom_metrics(environment, **kwargs):
    """Save TTFT, TPOT, and CSR data to CSV when the test ends."""
    if not _stream_metrics:
        return

    # Determine output path from Locust CSV prefix
    csv_prefix = environment.parsed_options.csv_prefix if hasattr(environment, 'parsed_options') and environment.parsed_options else None

    if csv_prefix:
        output_path = f"{csv_prefix}_stream_metrics.csv"
    else:
        output_path = "stream_metrics.csv"

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp", "ttft_ms", "tpot_ms", "total_time_ms",
            "token_count", "success",
        ])
        writer.writeheader()
        writer.writerows(_stream_metrics)

    # Compute summary
    successful = [m for m in _stream_metrics if m["success"]]
    total = len(_stream_metrics)
    csr = (len(successful) / total * 100) if total > 0 else 0

    ttft_values = [m["ttft_ms"] for m in successful if m["ttft_ms"] is not None]
    tpot_values = [m["tpot_ms"] for m in successful if m["tpot_ms"] is not None]

    print(f"\n--- Streaming Custom Metrics ---")
    print(f"Total requests: {total}")
    print(f"Successful streams: {len(successful)}")
    print(f"Connection Success Rate: {csr:.1f}%")
    if ttft_values:
        ttft_values.sort()
        print(f"TTFT median: {ttft_values[len(ttft_values)//2]:.1f} ms")
        print(f"TTFT p95: {ttft_values[int(len(ttft_values)*0.95)]:.1f} ms")
    if tpot_values:
        tpot_values.sort()
        print(f"TPOT median: {tpot_values[len(tpot_values)//2]:.1f} ms")
        print(f"TPOT p95: {tpot_values[int(len(tpot_values)*0.95)]:.1f} ms")
    print(f"Saved to: {output_path}")

    # Clear for next run
    _stream_metrics.clear()