"""Prometheus metrics middleware setup."""

from starlette_prometheus import (
    PrometheusMiddleware,
    metrics,
)


def setup_metrics(app):
    """Set up Prometheus metrics middleware and endpoints.

    Args:
        app: FastAPI application instance
    """
    # Add Prometheus middleware
    app.add_middleware(PrometheusMiddleware)

    # Add metrics endpoint
    app.add_route("/metrics", metrics)
