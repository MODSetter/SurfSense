"""OpenTelemetry Resource identity and instrumentation scope."""

from __future__ import annotations

import contextlib
import os
import socket
from importlib import metadata

# One neutral scope for every SurfSense-emitted span and metric.
INSTRUMENTATION_NAME = "surfsense"


def package_version() -> str:
    # Telemetry tag only: a malformed/editable install can raise beyond
    # PackageNotFoundError, so suppress broadly and fall back.
    with contextlib.suppress(Exception):
        return metadata.version("surf-new-backend")
    return "unknown"


def deployment_environment() -> str:
    return os.environ.get("SURFSENSE_ENV", "dev")


def build_resource():
    """Build the Resource shared by the tracer, meter, and logger providers."""
    from opentelemetry.sdk.resources import Resource

    environment = deployment_environment()
    return Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "surfsense-backend"),
            "service.version": package_version(),
            "service.instance.id": socket.gethostname(),
            "deployment.environment.name": environment,
            # Older key some Grafana onboarding checks still read.
            "deployment.environment": environment,
        }
    )
