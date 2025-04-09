import functools
import json
import logging
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass

import pika
from opentelemetry import trace, metrics, context
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.propagate import inject, extract
from opentelemetry.metrics import Counter, Histogram, Meter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

@dataclass
class QueueMetrics:
    """Holder for queue-specific metrics."""
    published_counter: Counter
    consumed_counter: Counter
    processing_time: Histogram
    queue_time: Histogram
    message_size: Histogram
    retry_counter: Counter

class RabbitMQInstrumentation:
    def __init__(self, service_name: str):
        """Initialize RabbitMQ instrumentation.

        Args:
            service_name: Name of the service for tracking
        """
        self.service_name = service_name
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)
        self.propagator = TraceContextTextMapPropagator()
        self._setup_metrics()

    def _setup_metrics(self):
        """Set up metrics collectors."""
        self.metrics_by_queue: Dict[str, QueueMetrics] = {}

    def _get_queue_metrics(self, queue_name: str) -> QueueMetrics:
        """Get or create metrics collectors for a queue."""
        if queue_name not in self.metrics_by_queue:
            self.metrics_by_queue[queue_name] = QueueMetrics(
                published_counter=self.meter.create_counter(
                    name=f"rabbitmq.{queue_name}.published",
                    description=f"Number of messages published to {queue_name}"
                ),
                consumed_counter=self.meter.create_counter(
                    name=f"rabbitmq.{queue_name}.consumed",
                    description=f"Number of messages consumed from {queue_name}"
                ),
                processing_time=self.meter.create_histogram(
                    name=f"rabbitmq.{queue_name}.processing_time",
                    description=f"Time taken to process messages from {queue_name}",
                    unit="ms"
                ),
                queue_time=self.meter.create_histogram(
                    name=f"rabbitmq.{queue_name}.queue_time",
                    description=f"Time messages spend in {queue_name}",
                    unit="ms"
                ),
                message_size=self.meter.create_histogram(
                    name=f"rabbitmq.{queue_name}.message_size",
                    description=f"Size of messages in {queue_name}",
                    unit="bytes"
                ),
                retry_counter=self.meter.create_counter(
                    name=f"rabbitmq.{queue_name}.retries",
                    description=f"Number of message retries in {queue_name}"
                )
            )
        return self.metrics_by_queue[queue_name]

    def instrument_publisher(self, channel: pika.channel.Channel):
        """Wrap a channel to instrument publishing.

        Args:
            channel: RabbitMQ channel to instrument
        """
        original_basic_publish = channel.basic_publish

        @functools.wraps(original_basic_publish)
        def instrumented_publish(
            exchange: str,
            routing_key: str,
            body: bytes,
            properties: pika.BasicProperties = None,
            mandatory: bool = False
        ):
            if properties is None:
                properties = pika.BasicProperties()
            if properties.headers is None:
                properties.headers = {}

            # Start publish span
            with self.tracer.start_as_current_span(
                name=f"publish {routing_key}",
                kind=SpanKind.PRODUCER,
                attributes={
                    "messaging.system": "rabbitmq",
                    "messaging.destination": routing_key,
                    "messaging.destination_kind": "queue",
                    "messaging.protocol": "AMQP",
                    "messaging.message_id": properties.message_id,
                }
            ) as span:
                # Inject context into message headers
                inject(properties.headers)

                # Add correlation ID if not present
                if not properties.correlation_id:
                    properties.correlation_id = format(span.get_span_context().span_id, "016x")

                try:
                    # Publish message
                    result = original_basic_publish(
                        exchange=exchange,
                        routing_key=routing_key,
                        body=body,
                        properties=properties,
                        mandatory=mandatory
                    )

                    # Record metrics
                    metrics = self._get_queue_metrics(routing_key)
                    metrics.published_counter.add(1)
                    metrics.message_size.record(len(body))

                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR))
                    span.record_exception(e)
                    raise

        channel.basic_publish = instrumented_publish
        return channel

    def instrument_consumer(
        self,
        channel: pika.channel.Channel,
        queue: str,
        callback: Callable
    ):
        """Wrap a consumer callback with instrumentation.

        Args:
            channel: RabbitMQ channel
            queue: Queue name
            callback: Original callback function
        """
        @functools.wraps(callback)
        def instrumented_callback(
            ch: pika.channel.Channel,
            method: pika.spec.Basic.Deliver,
            properties: pika.BasicProperties,
            body: bytes
        ):
            headers = properties.headers or {}

            # Extract context from headers
            ctx = extract(headers)

            # Start consumer span
            with self.tracer.start_span(
                name=f"consume {queue}",
                context=ctx,
                kind=SpanKind.CONSUMER,
                attributes={
                    "messaging.system": "rabbitmq",
                    "messaging.destination": queue,
                    "messaging.destination_kind": "queue",
                    "messaging.protocol": "AMQP",
                    "messaging.message_id": properties.message_id,
                    "messaging.correlation_id": properties.correlation_id,
                }
            ) as span:
                try:
                    # Record metrics before processing
                    metrics = self._get_queue_metrics(queue)
                    metrics.consumed_counter.add(1)
                    metrics.message_size.record(len(body))

                    if "x-first-death-exchange" in headers:
                        metrics.retry_counter.add(1)

                    # Process message with original callback
                    with self.tracer.start_span(
                        name=f"process {queue}",
                        attributes={
                            "messaging.operation": "process",
                        }
                    ):
                        result = callback(ch, method, properties, body)

                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR))
                    span.record_exception(e)
                    raise

        return instrumented_callback

    def create_dlq_policy(
        self,
        channel: pika.channel.Channel,
        queue: str,
        max_retries: int = 3
    ):
        """Create a dead letter queue policy for retries.

        Args:
            channel: RabbitMQ channel
            queue: Queue name
            max_retries: Maximum number of retries
        """
        # Create DLX exchange and queue
        dlx_exchange = f"{queue}.dlx"
        dlq = f"{queue}.dlq"

        channel.exchange_declare(dlx_exchange, "direct")
        channel.queue_declare(
            dlq,
            arguments={
                "x-message-ttl": 30000,  # 30 seconds delay before retry
                "x-dead-letter-exchange": "",  # Default exchange
                "x-dead-letter-routing-key": queue  # Route back to original queue
            }
        )
        channel.queue_bind(dlq, dlx_exchange, queue)

        # Set up main queue with DLX
        channel.queue_declare(
            queue,
            arguments={
                "x-dead-letter-exchange": dlx_exchange,
                "x-dead-letter-routing-key": queue
            }
        )

    def visualize_flow(self, channel: pika.channel.Channel):
        """Generate visualization data for message flows."""
        # This would collect flow data for visualization
        # Implementation would depend on your visualization needs
        pass

# Example usage
if __name__ == "__main__":
    # Initialize instrumentation
    instrumentation = RabbitMQInstrumentation("example-service")

    # Set up connection
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    # Instrument publisher
    channel = instrumentation.instrument_publisher(channel)

    # Define and instrument consumer
    def message_callback(ch, method, properties, body):
        print(f"Received: {body}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    instrumented_callback = instrumentation.instrument_consumer(
        channel, "example_queue", message_callback
    )

    # Set up queue with DLQ
    instrumentation.create_dlq_policy(channel, "example_queue")

    # Start consuming
    channel.basic_consume(
        queue="example_queue",
        on_message_callback=instrumented_callback
    )

    # Publish a message
    channel.basic_publish(
        exchange="",
        routing_key="example_queue",
        body="Hello World!"
    )

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()

    connection.close()
