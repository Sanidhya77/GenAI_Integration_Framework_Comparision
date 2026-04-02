"""URL routing for Django API endpoints."""

from django.urls import path

from api.views import api_inference, api_inference_stream, api_pipeline, health

urlpatterns = [
    path("api/inference", api_inference, name="inference"),
    path("api/inference/stream", api_inference_stream, name="inference_stream"),
    path("api/pipeline", api_pipeline, name="pipeline"),
    path("health", health, name="health"),
]