"""OpenTelemetry instrumentation setup for FastAPI and LangGraph nodes."""

import logging
from contextlib import contextmanager
from typing import Generator

from fastapi import FastAPI

from backend.core.config import settings

logger = logging.getLogger(__name__)

_tracer = None


def setup_opentelemetry(app: FastAPI) -> None:
    """Initializes OpenTelemetry tracer and instruments the FastAPI application."""
    global _tracer
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource(attributes={SERVICE_NAME: "konformai-backend"})
        provider = TracerProvider(resource=resource)

        otlp_endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT.strip()
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info("OpenTelemetry exporting to OTLP endpoint: %s", otlp_endpoint)
            except Exception as e:
                logger.warning("Could not setup OTLP exporter (%s); using console exporter.", e)
                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        else:
            # Console or silent span exporter for local / demo use
            logger.info("OpenTelemetry configured with local console tracer provider.")

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("konformai.tracer")

        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OpenTelemetry instrumentation initialized.")

    except Exception as exc:
        logger.warning("OpenTelemetry initialization note (%s); tracing will run in lightweight mock mode.", exc)


@contextmanager
def trace_node_span(node_name: str, case_id: str) -> Generator[None, None, None]:
    """Context manager wrapping execution of a LangGraph agent node inside an OpenTelemetry span."""
    global _tracer
    if _tracer is not None:
        with _tracer.start_as_current_span(f"node.{node_name}") as span:
            span.set_attribute("case.id", case_id)
            span.set_attribute("node.name", node_name)
            yield
    else:
        yield
