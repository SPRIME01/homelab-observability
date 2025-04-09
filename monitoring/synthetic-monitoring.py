import asyncio
import json
import logging
import random
import time
from typing import Dict, List
from datetime import datetime

import aiohttp
import numpy as np
from opentelemetry import trace, metrics
from opentelemetry.trace import Status, StatusCode
from opentelemetry.metrics import Histogram, Counter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SyntheticMonitor:
    def __init__(self, service_name: str = "synthetic-monitor"):
        self.service_name = service_name
        self._setup_telemetry()
        self.session = None

    def _setup_telemetry(self):
        """Set up OpenTelemetry instrumentation."""
        # Configure metrics
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint="http://otel-collector:4317")
        )
        provider = MeterProvider(metric_readers=[reader])
        metrics.set_meter_provider(provider)
        self.meter = metrics.get_meter(self.service_name)

        # Create metrics
        self.request_duration = self.meter.create_histogram(
            name="synthetic_request_duration",
            description="Duration of synthetic requests",
            unit="ms"
        )
        self.error_counter = self.meter.create_counter(
            name="synthetic_request_errors",
            description="Number of synthetic request errors"
        )

    async def setup(self):
        """Set up HTTP session."""
        self.session = aiohttp.ClientSession()

    async def cleanup(self):
        """Clean up resources."""
        if self.session:
            await self.session.close()

    async def check_api_endpoint(self, url: str, method: str = "GET", expected_status: int = 200) -> bool:
        """Check an API endpoint."""
        start_time = time.time()
        try:
            async with self.session.request(method, url) as response:
                duration = (time.time() - start_time) * 1000
                self.request_duration.record(
                    duration,
                    {"endpoint": url, "method": method}
                )

                if response.status != expected_status:
                    self.error_counter.add(1, {"endpoint": url, "error": "status_mismatch"})
                    return False
                return True
        except Exception as e:
            self.error_counter.add(1, {"endpoint": url, "error": str(e)})
            return False

    async def generate_ai_load(self, model_endpoint: str, batch_size: int = 1):
        """Generate synthetic load for AI models."""
        # Create random input data
        input_data = np.random.randn(batch_size, 3, 224, 224).tolist()

        start_time = time.time()
        try:
            async with self.session.post(
                model_endpoint,
                json={"inputs": input_data}
            ) as response:
                duration = (time.time() - start_time) * 1000
                self.request_duration.record(
                    duration,
                    {"endpoint": model_endpoint, "type": "inference"}
                )

                if response.status != 200:
                    self.error_counter.add(
                        1,
                        {"endpoint": model_endpoint, "error": "inference_failed"}
                    )
        except Exception as e:
            self.error_counter.add(
                1,
                {"endpoint": model_endpoint, "error": str(e)}
            )

    async def trigger_home_automation(self, hass_url: str, token: str):
        """Trigger Home Assistant automations."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # List of test scenarios
        scenarios = [
            {"service": "light/turn_on", "entity_id": "light.living_room"},
            {"service": "switch/toggle", "entity_id": "switch.office_fan"},
            {"service": "scene/turn_on", "entity_id": "scene.evening_mode"}
        ]

        for scenario in scenarios:
            start_time = time.time()
            try:
                async with self.session.post(
                    f"{hass_url}/api/services/{scenario['service']}",
                    headers=headers,
                    json={"entity_id": scenario["entity_id"]}
                ) as response:
                    duration = (time.time() - start_time) * 1000
                    self.request_duration.record(
                        duration,
                        {
                            "service": scenario["service"],
                            "entity": scenario["entity_id"]
                        }
                    )

                    if response.status != 200:
                        self.error_counter.add(
                            1,
                            {
                                "service": scenario["service"],
                                "error": "automation_failed"
                            }
                        )
            except Exception as e:
                self.error_counter.add(
                    1,
                    {
                        "service": scenario["service"],
                        "error": str(e)
                    }
                )

async def main():
    # Initialize monitor
    monitor = SyntheticMonitor()
    await monitor.setup()

    try:
        while True:
            # Check API endpoints
            await monitor.check_api_endpoint("http://api-gateway/health")
            await monitor.check_api_endpoint("http://rabbitmq:15672/api/health")

            # Generate AI model load
            await monitor.generate_ai_load("http://triton:8000/v2/models/resnet50/infer")

            # Trigger home automation
            await monitor.trigger_home_automation(
                "http://homeassistant:8123",
                "YOUR_LONG_LIVED_ACCESS_TOKEN"
            )

            # Wait before next iteration
            await asyncio.sleep(60)  # Run every minute

    except KeyboardInterrupt:
        logger.info("Shutting down synthetic monitoring")
    finally:
        await monitor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
