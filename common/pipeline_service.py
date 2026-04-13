"""
Four-stage compound AI pipeline for Endpoint 3 (/api/pipeline).

The RAG-pattern pipeline defined in Chapter 3:
  Stage 1 — Query Analysis (LOCAL): Parse prompt, construct retrieval query
  Stage 2 — Context Retrieval (I/O-BOUND): Search document store + 50ms delay
  Stage 3 — Augmented Inference (API CALL): Send augmented prompt to Anthropic
  Stage 4 — Post-processing (LOCAL): Parse and format the response


Stage-level timing (Metric #12) is recorded for every pipeline execution
and included in the response payload.
"""

import json
import logging
import os
import time

from common.config import LOG_DIR, SYSTEM_PROMPT, USER_PROMPT
from common.retrieval import retrieve_context_async, retrieve_context_sync
from common.anthropic_client import inference_sync, inference_async

logger = logging.getLogger(__name__)


def _build_augmented_prompt(user_query, retrieved_context):
    """Construct the augmented prompt combining user query with retrieved context.

    This is the same prompt template for all four frameworks.
    """
    return (
        f"Context from knowledge base:\n"
        f"---\n"
        f"{retrieved_context}\n"
        f"---\n\n"
        f"Based on the above context, answer the following question:\n"
        f"{user_query}"
    )


def _log_stage_timing(framework_name, stage_timings):
    """Write stage timing data to the framework's log directory.

    Creates a JSON-lines log file for later analysis (Metric #12).
    """
    framework_log_dir = os.path.join(LOG_DIR, framework_name)
    os.makedirs(framework_log_dir, exist_ok=True)

    log_file = os.path.join(framework_log_dir, "pipeline_timing.jsonl")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(stage_timings) + "\n")



# Stage implementations for Synchronous


def _stage1_query_analysis_sync(user_query):
    """Stage 1 (LOCAL): Parse the user query and construct a retrieval query.

    In this experiment, the retrieval query is derived directly from the
    user prompt. This stage exists to represent the local computation
    component of a real compound AI pipeline.
    """
    # Extract key terms for retrieval
    retrieval_query = user_query
    return retrieval_query


def _stage4_postprocess_sync(api_response):
    """Stage 4 (LOCAL): Parse and format the inference response.

    Extracts the response text and structures the final output.
    In a production system, this might include response validation,
    filtering, or reformatting.
    """
    return {
        "answer": api_response["response"],
        "model": api_response["model"],
        "usage": api_response["usage"],
    }


# Synchronous pipeline for Flask and Django


def run_pipeline_sync(user_query, framework_name="unknown"):
    """Execute the full 4-stage pipeline synchronously.

    Returns a dict containing the processed response and stage-level
    timing data for Metric #12.
    """
    stage_timings = {"framework": framework_name, "timestamp": time.time()}

    # Stage 1 — Query Analysis (LOCAL)
    t0 = time.perf_counter()
    retrieval_query = _stage1_query_analysis_sync(user_query)
    t1 = time.perf_counter()
    stage_timings["stage1_query_analysis_ms"] = round((t1 - t0) * 1000, 3)

    # Stage 2 — Context Retrieval (I/O-BOUND with 50ms delay)
    t2 = time.perf_counter()
    retrieved_context = retrieve_context_sync(retrieval_query)
    t3 = time.perf_counter()
    stage_timings["stage2_context_retrieval_ms"] = round((t3 - t2) * 1000, 3)

    # Stage 3 — Augmented Inference (API CALL)
    augmented_prompt = _build_augmented_prompt(user_query, retrieved_context)
    t4 = time.perf_counter()
    api_response = inference_sync(augmented_prompt)
    t5 = time.perf_counter()
    stage_timings["stage3_augmented_inference_ms"] = round((t5 - t4) * 1000, 3)

    # Stage 4 — Post-processing (LOCAL)
    t6 = time.perf_counter()
    result = _stage4_postprocess_sync(api_response)
    t7 = time.perf_counter()
    stage_timings["stage4_postprocessing_ms"] = round((t7 - t6) * 1000, 3)

    # Total pipeline time
    stage_timings["total_pipeline_ms"] = round((t7 - t0) * 1000, 3)

    # Log timing data
    _log_stage_timing(framework_name, stage_timings)

    return {
        "pipeline_result": result,
        "stage_timings": stage_timings,
    }



# Asynchronous pipeline for FastAPI and Tornado


async def run_pipeline_async(user_query, framework_name="unknown"):
    """Execute the full 4-stage pipeline asynchronously.

    Returns a dict containing the processed response and stage-level
    timing data for Metric #12.
    """
    stage_timings = {"framework": framework_name, "timestamp": time.time()}

    # Stage 1 — Query Analysis (LOCAL)
    t0 = time.perf_counter()
    retrieval_query = _stage1_query_analysis_sync(user_query)  # Local — no async needed
    t1 = time.perf_counter()
    stage_timings["stage1_query_analysis_ms"] = round((t1 - t0) * 1000, 3)

    # Stage 2 — Context Retrieval (I/O-BOUND with 50ms delay)
    t2 = time.perf_counter()
    retrieved_context = await retrieve_context_async(retrieval_query)
    t3 = time.perf_counter()
    stage_timings["stage2_context_retrieval_ms"] = round((t3 - t2) * 1000, 3)

    # Stage 3 — Augmented Inference (API CALL)
    augmented_prompt = _build_augmented_prompt(user_query, retrieved_context)
    t4 = time.perf_counter()
    api_response = await inference_async(augmented_prompt)
    t5 = time.perf_counter()
    stage_timings["stage3_augmented_inference_ms"] = round((t5 - t4) * 1000, 3)

    # Stage 4 — Post-processing (LOCAL)
    t6 = time.perf_counter()
    result = _stage4_postprocess_sync(api_response)  # Local — no async needed
    t7 = time.perf_counter()
    stage_timings["stage4_postprocessing_ms"] = round((t7 - t6) * 1000, 3)

    # Total pipeline time
    stage_timings["total_pipeline_ms"] = round((t7 - t0) * 1000, 3)

    # Log timing data
    _log_stage_timing(framework_name, stage_timings)

    return {
        "pipeline_result": result,
        "stage_timings": stage_timings,
    }