"""
Django views — WSGI synchronous full-stack framework.

Endpoints:
  /api/inference        — Standard request-response (Endpoint 1)
  /api/inference/stream — SSE streaming token-by-token (Endpoint 2)
  /api/pipeline         — Four-stage compound AI pipeline (Endpoint 3)

Server: Gunicorn 25.3.0 with default sync worker class
Client: Anthropic() — synchronous
Streaming: StreamingHttpResponse with generator
"""

import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from common.config import USER_PROMPT
from common.anthropic_client import inference_sync, stream_sync
from common.pipeline_service import run_pipeline_sync

FRAMEWORK_NAME = "django"


# ---------------------------------------------------------------------------
# Endpoint 1: /api/inference — Standard request-response
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def api_inference(request):
    """Receive prompt, call Anthropic API, return complete JSON response."""
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    prompt = data.get("prompt", USER_PROMPT)

    result = inference_sync(prompt)

    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Endpoint 2: /api/inference/stream — SSE streaming
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def api_inference_stream(request):
    """Receive prompt, stream tokens via Server-Sent Events."""
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    prompt = data.get("prompt", USER_PROMPT)

    def generate():
        token_count = 0
        for chunk in stream_sync(prompt):
            token_count += 1
            event_data = json.dumps({"token": chunk, "index": token_count})
            yield f"data: {event_data}\n\n"

        # Signal stream completion
        yield f"data: {json.dumps({'done': True, 'total_tokens': token_count})}\n\n"

    response = StreamingHttpResponse(
        generate(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ---------------------------------------------------------------------------
# Endpoint 3: /api/pipeline — Four-stage compound AI pipeline
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def api_pipeline(request):
    """Execute the 4-stage RAG pipeline and return result with stage timings."""
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    prompt = data.get("prompt", USER_PROMPT)

    result = run_pipeline_sync(prompt, framework_name=FRAMEWORK_NAME)

    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@require_GET
def health(request):
    """Simple health check for verifying server is running."""
    return JsonResponse({"status": "ok", "framework": FRAMEWORK_NAME})