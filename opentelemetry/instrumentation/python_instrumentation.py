import os
import functools
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from contextlib import contextmanager

from opentelemetry import trace, baggage, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator

# Auto-instrumentation imports
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.instrumentation.pika import PikaInstrumentor

logger = logging.getLogger(__name__)

class HomelabTelemetry:
    def __init__(
        self,
        service_name: str,
        collector_endpoint: str = "http://otel-collector:4317",
        environment: str = "homelab",
        version: str = "1.0.0",
        auto_instrument: bool = True,
        sample_rate: float = 1.0
    ):
        """Initialize the homelab telemetry system.

        Args:
            service_name: Name of the service being instrumented
            collector_endpoint: OpenTelemetry collector endpoint
            environment: Environment name (e.g., homelab, staging, prod)
            version: Service version
            auto_instrument: Whether to automatically instrument common libraries
            sample_rate: Sampling rate (0.0 to 1.0)
        """
        self.service_name = service_name
        self.collector_endpoint = collector_endpoint

        # Create resource with service information
        self.resource = Resource.create({
            "service.name": service_name,
            "service.version": version,
            "deployment.environment": environment
        })

        # Initialize tracing
        self._setup_tracing(sample_rate)

        # Initialize metrics
        self._setup_metrics()

        # Initialize propagators
        self.propagator = TraceContextTextMapPropagator()
        self.baggage_propagator = W3CBaggagePropagator()

        if auto_instrument:
            self._setup_auto_instrumentation()

    def _setup_tracing(self, sample_rate: float):
        """Set up the tracing system."""
        trace_provider = TracerProvider(
            resource=self.resource,
            sampler=trace.sampling.TraceIdRatioBased(sample_rate)
        )

        otlp_exporter = OTLPSpanExporter(endpoint=self.collector_endpoint)
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace_provider.add_span_processor(span_processor)

        trace.set_tracer_provider(trace_provider)
        self.tracer = trace.get_tracer(self.service_name)

    def _setup_metrics(self):
        """Set up the metrics system."""
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=self.collector_endpoint)
        )

        metric_provider = MeterProvider(
            resource=self.resource,
            metric_readers=[metric_reader]
        )

        metrics.set_meter_provider(metric_provider)
        self.meter = metrics.get_meter(self.service_name)

    def _setup_auto_instrumentation(self):
        """Set up automatic instrumentation for common libraries."""
        instrumentors = [
            RequestsInstrumentor(),
            FlaskInstrumentor(),
            FastAPIInstrumentor(),
            DjangoInstrumentor(),
            SQLAlchemyInstrumentor(),
            RedisInstrumentor(),
            Psycopg2Instrumentor(),
            PymongoInstrumentor(),
            PikaInstrumentor()
        ]

        for instrumentor in instrumentors:
            try:
                instrumentor.instrument()
            except Exception as e:
                logger.debug(f"Failed to initialize {instrumentor.__class__.__name__}: {e}")

    def create_span(
        self,
        name: str,
        context: Optional[trace.SpanContext] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None
    ) -> trace.Span:
        """Create a new span."""
        return self.tracer.start_span(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes
        )

    @contextmanager
    def span_in_context(
        self,
        name: str,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Create and activate a span as a context manager."""
        span = self.create_span(name, kind=kind, attributes=attributes)
        with trace.use_span(span) as active_span:
            yield active_span

    def instrument(
        self,
        name: Optional[str] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Callable:
        """Decorator to instrument a function."""
        def decorator(func: Callable) -> Callable:
            span_name = name or func.__name__

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.span_in_context(span_name, kind=kind, attributes=attributes) as span:
                    try:
                        result = func(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(trace.Status(trace.StatusCode.ERROR))
                        raise
            return wrapper
        return decorator

    def inject_context(self, carrier: Dict[str, str]):
        """Inject context into carrier for distributed tracing."""
        self.propagator.inject(carrier)
        self.baggage_propagator.inject(carrier)

    def extract_context(self, carrier: Dict[str, str]) -> trace.SpanContext:
        """Extract context from carrier for distributed tracing."""
        context = self.propagator.extract(carrier)
        baggage.set_baggage(self.baggage_propagator.extract(carrier))
        return context

    def create_counter(self, name: str, description: str, unit: str = "1") -> metrics.Counter:
        """Create a counter metric."""
        return self.meter.create_counter(name, description=description, unit=unit)

    def create_histogram(self, name: str, description: str, unit: str = "ms") -> metrics.Histogram:
        """Create a histogram metric."""
        return self.meter.create_histogram(name, description=description, unit=unit)

# Testing utilities
class TelemetryTestMixin:
    """Mixin class for testing instrumented code."""

    def setup_telemetry(self):
        """Set up test telemetry."""
        self.telemetry = HomelabTelemetry(
            service_name="test-service",
            collector_endpoint="http://localhost:4317",
            environment="test",
            sample_rate=1.0
        )
        self.spans = []

        def span_processor(span):
            self.spans.append(span)

        # Add test span processor
        trace.get_tracer_provider().add_span_processor(span_processor)

    def get_spans(self, name: Optional[str] = None) -> List[trace.Span]:
        """Get recorded spans, optionally filtered by name."""
        if name:
            return [span for span in self.spans if span.name == name]
        return self.spans

    def clear_spans(self):
        """Clear recorded spans."""
        self.spans.clear()

# Example usage
if __name__ == "__main__":
    # Initialize telemetry
    telemetry = HomelabTelemetry(
        service_name="example-service",
        environment="homelab"
    )

    # Example of manual instrumentation
    @telemetry.instrument(name="process_data", attributes={"data_type": "example"})
    def process_data(data):
        # Process data here
        return data

    # Example of context propagation
    headers = {}
    telemetry.inject_context(headers)

    # Example of metrics
    request_counter = telemetry.create_counter(
        name="request_counter",
        description="Count of requests"
    )
    request_counter.add(1)
