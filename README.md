# Comparative Analysis of Python-Based Web Frameworks for Efficient Integration of Generative AI Services

**Bachelor Thesis — Riga Technical University (RTU)**  
Institute of Applied Computer Systems (IACS)  
Type 1: Research of Current Solutions (A-S-SV Model)

---

## Overview

This repository contains the experiment prototype for comparing four Python web frameworks under Generative AI integration workloads. The experiment measures how each framework handles real-time LLM inference requests, token-by-token streaming, and multi-stage compound AI pipelines.

## Frameworks Under Test

| Framework | Type | Execution Model | Server | Interface |
|-----------|------|-----------------|--------|-----------|
| Flask 3.1.3 | Micro-framework | Synchronous | Gunicorn 25.3.0 | WSGI |
| Django 6.0.3 | Full-stack | Synchronous | Gunicorn 25.3.0 | WSGI |
| FastAPI 0.135.3 | API-oriented | Asynchronous | Uvicorn 0.42.0 | ASGI |
| Tornado 6.5.5 | Event-driven | Non-blocking | Built-in server | Event Loop |

## Experiment Design

Each framework implements three identical API endpoints:

1. **`/api/inference`** — Standard request-response: receives a prompt, calls the Anthropic API, returns a complete JSON response.
2. **`/api/inference/stream`** — Streaming via SSE: forwards tokens from the Anthropic API to the client as they are generated.
3. **`/api/pipeline`** — Four-stage compound AI pipeline (RAG pattern):
   - Stage 1: Query analysis (local computation)
   - Stage 2: Context retrieval from document store + 50ms simulated vector DB latency
   - Stage 3: Augmented inference via Anthropic API
   - Stage 4: Post-processing and response formatting

All business logic is shared through a `common/` module to ensure the only variable is the framework architecture.

## Evaluation Metrics (13 Metrics, 4 Dimensions)

**Dimension 1 — Latency and Connection Stability:**
TTFT, TPOT, Total Response Time, Connection Success Rate

**Dimension 2 — Concurrency Scalability:**
Throughput, Tail Latency (p95/p99), Error Rate

**Dimension 3 — Resource Utilisation:**
Peak Memory RSS, Memory Growth Rate, CPU Utilisation

**Dimension 4 — Pipeline Coordination:**
E2E Pipeline Latency, Stage-Level Timing, Pipeline Completion Rate

## Hybrid Testing Approach

- **Real API** (concurrency 1, 5, 10): All endpoints use the live Anthropic API with `claude-haiku-4-5`.
- **Simulated endpoint** (concurrency 25, 50, 100): A local mock server calibrated to real API response characteristics replaces the Anthropic API to test pure framework concurrency behaviour.

## Test Matrix

- 4 frameworks × 3 endpoints × 6 concurrency levels × 5 runs = **360 total test executions**

## Project Structure

```
experiment/
├── common/                     # Shared logic (identical across all frameworks)
│   ├── config.py               #   Shared constants and configuration
│   ├── retrieval.py            #   Document store search (sync + async)
│   ├── anthropic_client.py     #   Anthropic API wrappers (sync + async)
│   └── pipeline_service.py     #   4-stage pipeline with stage timing
│
├── flask_app/                  # Flask implementation (WSGI, synchronous)
│   ├── app.py                  #   All 3 endpoints
│   └── gunicorn_config.py      #   Gunicorn server configuration
│
├── django_app/                 # Django implementation (WSGI, synchronous)
│   ├── manage.py
│   ├── gunicorn_config.py      #   Gunicorn server configuration
│   ├── config/                 #   Django project settings
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── api/                    #   All 3 endpoints
│       ├── views.py
│       └── urls.py
│
├── fastapi_app/                # FastAPI implementation (ASGI, asynchronous)
│   └── main.py                 #   All 3 endpoints
│
├── tornado_app/                # Tornado implementation (event loop, async)
│   └── main.py                 #   All 3 endpoints
│
├── simulated_endpoint/         # Mock API server for high-concurrency tests
│   └── simulator.py
│
├── locust_tests/               # Load testing scripts
│   ├── test_inference.py       #   Standard inference load test
│   ├── test_stream.py          #   Streaming with TTFT/TPOT measurement
│   └── test_pipeline.py        #   Pipeline with stage timing extraction
│
├── monitoring/                 # Resource monitoring
│   └── resource_monitor.py     #   psutil-based CPU and memory sampling
│
├── scripts/                    # Utility scripts
│   └── calibrate_simulator.py  #   Generate calibration.json from real API
│
├── document_store/             # Knowledge base for pipeline endpoint
│   └── genai_concepts.txt
│
├── data/                       # Raw test data output (per framework)
│   ├── flask/
│   ├── django/
│   ├── fastapi/
│   └── tornado/
│
├── logs/                       # Pipeline stage timing logs
├── results/                    # Processed data for Chapter 4
└── .env                        # API key (not committed)
```

## Environment

| Component | Version |
|-----------|---------|
| WSL2 Ubuntu | 24.04 LTS |
| Python | 3.12.3 |
| Anthropic SDK | 0.88.0 |
| Locust | 2.43.4 |
| psutil | 7.2.2 |

## How to Run

### Setup
```bash
cd /home/sanidhya/experiment
source venv/bin/activate
export $(cat .env | xargs)
```

### Start a Framework Server
```bash
# Flask
gunicorn -c flask_app/gunicorn_config.py flask_app.app:app

# Django
cd django_app && gunicorn -c gunicorn_config.py config.wsgi:application

# FastAPI
uvicorn fastapi_app.main:app --host 0.0.0.0 --port 8000 --workers 1

# Tornado
python tornado_app/main.py
```

### Health Check
```bash
curl http://localhost:8000/health
```

### Run a Load Test
```bash
locust -f locust_tests/test_inference.py --headless \
  -u 1 -r 1 -t 60s \
  --host http://localhost:8000 \
  --csv data/flask/inference/run1
```

### Resource Monitoring
```bash
python monitoring/resource_monitor.py --pid <SERVER_PID> --output data/flask/inference/run1_resources.csv
```

## GenAI API Configuration

- **Model:** claude-haiku-4-5-20251001
- **Max tokens:** 256
- **Temperature:** 0.0 (deterministic)
- **System prompt:** "You are a technical assistant specialising in web development."

## Thesis Chapter Mapping

| Chapter | Content | Status |
|---------|---------|--------|
| Chapter 1 | Theoretical Background | ✅ Complete |
| Chapter 2 | Literature Review and Framework Analysis | ✅ Complete |
| Chapter 3 | Methodology and Experimental Design | ✅ Complete |
| Chapter 4 | Results and Discussion | ⏳ Pending experiment |
| Chapter 5 | Scenarios and Validated Recommendations | ⏳ Pending results |