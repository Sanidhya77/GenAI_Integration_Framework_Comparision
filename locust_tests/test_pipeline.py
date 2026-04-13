"""
Locust test for Endpoint 3: /api/pipeline (four-stage compound AI pipeline).

Metrics collected:
  - E2E Pipeline Latency (ms) — Metric #11 (custom from response payload)
  - Stage-Level Timing (ms/stage) — Metric #12 (from server-side logs)
  - Pipeline Completion Rate (%) — Metric #13 (custom tracking)
  - Total Response Time (ms) — Metric #3 (Locust native)
  - Throughput (req/s) — Metric #5 (Locust native)
  - Tail Latency p95/p99 (ms) — Metric #6 (Locust native)
  - Error Rate (%) — Metric #7 (Locust native)

Run command:
  cd /home/sanidhya/experiment
  locust -f locust_tests/test_pipeline.py --headless \
    -u <CONCURRENCY> -r <CONCURRENCY> \
    -t 60s --host http://localhost:8000 \
    --csv data/<framework>/pipeline/run<N>

Pipeline stage timings (Metric #12) are logged server-side to logs/<framework>/.
E2E latency and completion rate are saved to a separate CSV.
"""

import csv
import json
import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from locust import HttpUser, task, between, events

from common.config import USER_PROMPT

# Custom metrics storage

_pipeline_metrics = []
_metrics_lock = threading.Lock()


class PipelineUser(HttpUser):
    """Simulates users sending pipeline requests."""

    wait_time = between(0, 0)  # No wait to sustain maximum concurrency

    @task
    def pipeline(self):
        """Send a pipeline request and extract stage timing data."""
        completed = False
        stage_timings = None
        e2e_latency = None

        with self.client.post(
            "/api/pipeline",
            json={"prompt": USER_PROMPT},
            timeout=120,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()

                    # Extract stage timings from response payload
                    stage_timings = data.get("stage_timings", {})
                    e2e_latency = stage_timings.get("total_pipeline_ms")

                    # Verify pipeline produced a result
                    pipeline_result = data.get("pipeline_result", {})
                    if pipeline_result.get("answer"):
                        completed = True
                        response.success()
                    else:
                        response.failure("Pipeline returned empty answer")

                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

        # Store custom metrics
        with _metrics_lock:
            _pipeline_metrics.append({
                "timestamp": time.time(),
                "completed": completed,
                "e2e_pipeline_ms": round(e2e_latency, 3) if e2e_latency else None,
                "stage1_ms": round(stage_timings.get("stage1_query_analysis_ms", 0), 3) if stage_timings else None,
                "stage2_ms": round(stage_timings.get("stage2_context_retrieval_ms", 0), 3) if stage_timings else None,
                "stage3_ms": round(stage_timings.get("stage3_augmented_inference_ms", 0), 3) if stage_timings else None,
                "stage4_ms": round(stage_timings.get("stage4_postprocessing_ms", 0), 3) if stage_timings else None,
            })



# Save custom metrics on test stop

@events.quitting.add_listener
def save_custom_metrics(environment, **kwargs):
    """Save pipeline metrics to CSV when the test ends."""
    if not _pipeline_metrics:
        return

    # Determine output path
    csv_prefix = environment.parsed_options.csv_prefix if hasattr(environment, 'parsed_options') and environment.parsed_options else None

    if csv_prefix:
        output_path = f"{csv_prefix}_pipeline_metrics.csv"
    else:
        output_path = "pipeline_metrics.csv"

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp", "completed", "e2e_pipeline_ms",
            "stage1_ms", "stage2_ms", "stage3_ms", "stage4_ms",
        ])
        writer.writeheader()
        writer.writerows(_pipeline_metrics)

    # Compute summary
    total = len(_pipeline_metrics)
    completed = [m for m in _pipeline_metrics if m["completed"]]
    pcr = (len(completed) / total * 100) if total > 0 else 0

    e2e_values = [m["e2e_pipeline_ms"] for m in completed if m["e2e_pipeline_ms"] is not None]

    print(f"\n--- Pipeline Custom Metrics ---")
    print(f"Total requests: {total}")
    print(f"Completed pipelines: {len(completed)}")
    print(f"Pipeline Completion Rate: {pcr:.1f}%")
    if e2e_values:
        e2e_values.sort()
        print(f"E2E Latency median: {e2e_values[len(e2e_values)//2]:.1f} ms")
        print(f"E2E Latency p95: {e2e_values[int(len(e2e_values)*0.95)]:.1f} ms")
    print(f"Saved to: {output_path}")

    # Clear for next run
    _pipeline_metrics.clear()