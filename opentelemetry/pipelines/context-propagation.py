import json
import logging
from typing import Any, Dict, Optional, Union, Callable

import pika
import requests
from opentelemetry import context, trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.pika import PikaInstrumentor

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TracingHelper:
    def __init__(self, service_name: str, otlp_endpoint: str = "http://localhost:4317"):
        """Initialize the tracing helper with service information.

        Args:
            service_name: The name of the service using this helper
            otlp_endpoint: The OTLP endpoint for sending traces
        """
        self.service_name = service_name

        # Set up tracer provider
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        # Configure exporter
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        span_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(span_processor)

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Get a tracer
        self.tracer = trace.get_tracer(service_name)

        # Instrument libraries
        LoggingInstrumentor().instrument(set_logging_format=True)
        RequestsInstrumentor().instrument()
        PikaInstrumentor().instrument()

        logger.info(f"Initialized tracing for service: {service_name}")

    def extract_context_from_request(self, headers: Dict[str, str]) -> context.Context:
        """Extract trace context from HTTP headers.

        Args:
            headers: Dictionary containing HTTP headers

        Returns:
            Context object containing the extracted context
        """
        ctx = extract(headers)
        logger.debug(f"Extracted context from headers: {headers}")
        return ctx

    def create_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL,
                   attributes: Optional[Dict[str, Any]] = None,
                   parent_context: Optional[context.Context] = None) -> trace.Span:
        """Create a new span for a processing step.

        Args:
            name: Name of the span
            kind: Kind of span (SERVER, CLIENT, PRODUCER, CONSUMER, INTERNAL)
            attributes: Span attributes to add
            parent_context: Optional parent context

        Returns:
            The created span
        """
        ctx = parent_context or context.get_current()
        attributes = attributes or {}
        attributes["service.name"] = self.service_name

        span = self.tracer.start_span(
            name=name,
            kind=kind,
            attributes=attributes,
            context=ctx
        )

        logger.debug(f"Created span: {name}, kind: {kind}")
        return span

    def inject_context_to_headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Inject current context into HTTP headers.

        Args:
            headers: Optional existing headers to inject into

        Returns:
            Headers dict with injected trace context
        """
        headers = headers or {}
        inject(headers)
        logger.debug(f"Injected context to headers: {headers}")
        return headers

    def propagate_context_to_rabbitmq(self, properties: pika.BasicProperties) -> pika.BasicProperties:
        """Inject current context into RabbitMQ message properties.

        Args:
            properties: RabbitMQ BasicProperties object

        Returns:
            Updated properties with context headers
        """
        # If headers don't exist, create them
        if properties.headers is None:
            properties.headers = {}

        inject(properties.headers)
        logger.debug(f"Injected context to RabbitMQ headers: {properties.headers}")
        return properties

    def extract_context_from_rabbitmq(self, properties: pika.BasicProperties) -> context.Context:
        """Extract trace context from RabbitMQ message properties.

        Args:
            properties: RabbitMQ BasicProperties object

        Returns:
            Context object containing the extracted context
        """
        headers = properties.headers or {}
        ctx = extract(headers)
        logger.debug(f"Extracted context from RabbitMQ headers: {headers}")
        return ctx

    def instrument_function(self, span_name: str, kind: SpanKind = SpanKind.INTERNAL,
                           attributes: Optional[Dict[str, Any]] = None) -> Callable:
        """Decorator to instrument a function with tracing.

        Args:
            span_name: Name of the span
            kind: Kind of span
            attributes: Optional attributes for the span

        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    name=span_name,
                    kind=kind,
                    attributes=attributes
                ) as span:
                    try:
                        result = func(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR))
                        span.record_exception(e)
                        raise
            return wrapper
        return decorator

    def correlate_with_logs(self, log_message: str, additional_attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Correlate trace context with logs.

        Args:
            log_message: The log message
            additional_attributes: Additional attributes to include

        Returns:
            Dictionary with log context including trace information
        """
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()

        log_context = additional_attributes or {}
        log_context.update({
            "message": log_message,
            "trace_id": format(span_context.trace_id, "032x"),
            "span_id": format(span_context.span_id, "016x"),
            "trace_flags": span_context.trace_flags,
            "service.name": self.service_name
        })

        logger.info(json.dumps(log_context))
        return log_context

    def correlate_with_metrics(self, metric_name: str, attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Correlate trace context with metrics.

        Args:
            metric_name: The name of the metric
            attributes: Additional attributes to include with the metric

        Returns:
            Dictionary with metric context including trace information
        """
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()

        metric_attributes = attributes or {}
        metric_attributes.update({
            "trace_id": format(span_context.trace_id, "032x"),
            "span_id": format(span_context.span_id, "016x"),
            "service.name": self.service_name
        })

        logger.debug(f"Added trace context to metric: {metric_name}")
        return metric_attributes


# Example of using the helper in a service
def example_usage():
    # Initialize the helper
    tracing_helper = TracingHelper("example-service", "http://otel-collector:4317")

    # Example: Creating a span for processing
    with tracing_helper.create_span("process-data", kind=SpanKind.INTERNAL,
                                  attributes={"data.size": 100}) as span:
        # Do some processing
        span.add_event("Processing started")
        # ... processing logic ...
        span.add_event("Processing completed")

    # Example: Making an HTTP request with context propagation
    headers = tracing_helper.inject_context_to_headers()
    response = requests.get("http://other-service/api/data", headers=headers)

    # Example: Sending a message to RabbitMQ with context
    connection = pika.BlockingConnection(pika.ConnectionParameters("rabbitmq"))
    channel = connection.channel()

    properties = pika.BasicProperties()
    properties = tracing_helper.propagate_context_to_rabbitmq(properties)

    channel.basic_publish(
        exchange="",
        routing_key="example_queue",
        body="Hello World!",
        properties=properties
    )

    # Example: Correlating with logs
    tracing_helper.correlate_with_logs("Operation completed successfully", {"operation": "data-sync"})

    # Example: Decorating a function with tracing
    @tracing_helper.instrument_function("process-item", attributes={"item.type": "sensor"})
    def process_item(item_id):
        # ... processing logic ...
        return f"Processed {item_id}"

    result = process_item("sensor-123")
