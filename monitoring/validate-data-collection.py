#!/usr/bin/env python3
import os
import sys
import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any

import aiohttp
import requests
import influxdb_client
from prometheus_api_client import PrometheusConnect
from grafana_api.grafana_face import GrafanaFace

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ObservabilityValidator:
    def __init__(self):
        """Initialize the validator with service endpoints and credentials."""
        self.endpoints = {
            'prometheus': os.getenv('PROMETHEUS_URL', 'http://prometheus:9090'),
            'loki': os.getenv('LOKI_URL', 'http://loki:3100'),
            'tempo': os.getenv('TEMPO_URL', 'http://tempo:3200'),
            'influxdb': os.getenv('INFLUXDB_URL', 'http://homeassistant.local:8086'),
            'grafana': os.getenv('GRAFANA_URL', 'http://grafana:3000')
        }

        self.credentials = {
            'influxdb_token': os.getenv('INFLUXDB_TOKEN'),
            'grafana_token': os.getenv('GRAFANA_TOKEN')
        }

    async def check_prometheus_metrics(self) -> bool:
        """Validate Prometheus metrics collection."""
        try:
            prom = PrometheusConnect(url=self.endpoints['prometheus'])

            # Check basic metrics existence
            metrics_to_check = [
                'up',
                'node_memory_MemTotal_bytes',
                'container_cpu_usage_seconds_total'
            ]

            for metric in metrics_to_check:
                result = prom.get_current_metric_value(metric)
                if not result:
                    logger.error(f"Metric {metric} not found in Prometheus")
                    return False
                logger.info(f"Found metric {metric} with {len(result)} data points")

            # Check metric freshness
            latest_timestamp = prom.get_current_metric_value('up')[0]['value'][0]
            if time.time() - latest_timestamp > 300:  # 5 minutes
                logger.error("Prometheus metrics are stale")
                return False

            return True
        except Exception as e:
            logger.error(f"Prometheus validation failed: {e}")
            return False

    async def check_loki_logs(self) -> bool:
        """Validate Loki log collection."""
        try:
            async with aiohttp.ClientSession() as session:
                # Query last 5 minutes of logs
                query = '{app="observability"}'
                params = {
                    'query': query,
                    'start': str(int(time.time() - 300) * 1e9),
                    'end': str(int(time.time()) * 1e9),
                    'limit': 10
                }

                async with session.get(
                    f"{self.endpoints['loki']}/loki/api/v1/query_range",
                    params=params
                ) as response:
                    if response.status != 200:
                        logger.error(f"Loki query failed: {await response.text()}")
                        return False

                    data = await response.json()
                    if not data.get('data', {}).get('result'):
                        logger.error("No logs found in Loki")
                        return False

                    logger.info(f"Found {len(data['data']['result'])} log streams")
                    return True
        except Exception as e:
            logger.error(f"Loki validation failed: {e}")
            return False

    async def check_tempo_traces(self) -> bool:
        """Validate Tempo trace collection."""
        try:
            async with aiohttp.ClientSession() as session:
                # Check if Tempo is receiving traces
                async with session.get(
                    f"{self.endpoints['tempo']}/api/traces"
                ) as response:
                    if response.status != 200:
                        logger.error(f"Tempo API check failed: {await response.text()}")
                        return False

                    # Query for recent traces
                    query = {
                        'start': int(time.time() - 300) * 1000,
                        'end': int(time.time()) * 1000,
                        'limit': 10
                    }

                    async with session.get(
                        f"{self.endpoints['tempo']}/api/search",
                        params=query
                    ) as search_response:
                        data = await search_response.json()
                        if not data.get('traces'):
                            logger.error("No traces found in Tempo")
                            return False

                        logger.info(f"Found {len(data['traces'])} traces")
                        return True
        except Exception as e:
            logger.error(f"Tempo validation failed: {e}")
            return False

    async def check_influxdb_data(self) -> bool:
        """Validate InfluxDB data integrity."""
        try:
            client = influxdb_client.InfluxDBClient(
                url=self.endpoints['influxdb'],
                token=self.credentials['influxdb_token'],
                org='homeassistant'
            )

            # Check each bucket
            buckets_to_check = [
                'system_metrics',
                'home_assistant',
                'ai_inference'
            ]

            for bucket in buckets_to_check:
                query = f'''
                from(bucket: "{bucket}")
                    |> range(start: -5m)
                    |> count()
                '''

                result = client.query_api().query(query)
                if not result:
                    logger.error(f"No data found in bucket {bucket}")
                    return False

                logger.info(f"Found data in bucket {bucket}")

            return True
        except Exception as e:
            logger.error(f"InfluxDB validation failed: {e}")
            return False

    async def check_grafana_dashboards(self) -> bool:
        """Validate Grafana dashboard rendering."""
        try:
            grafana = GrafanaFace(
                auth=self.credentials['grafana_token'],
                host=self.endpoints['grafana']
            )

            # Check dashboard health
            dashboards_to_check = [
                'homelab-overview',
                'home-automation',
                'ai-performance'
            ]

            for uid in dashboards_to_check:
                try:
                    dashboard = grafana.dashboard.get_dashboard(uid)

                    # Verify dashboard renders
                    render_url = f"{self.endpoints['grafana']}/render/d/{uid}"
                    response = requests.get(
                        render_url,
                        headers={'Authorization': f"Bearer {self.credentials['grafana_token']}"},
                        params={'width': 1000, 'height': 500}
                    )

                    if response.status_code != 200:
                        logger.error(f"Dashboard {uid} failed to render")
                        return False

                    logger.info(f"Dashboard {uid} rendered successfully")
                except Exception as e:
                    logger.error(f"Error checking dashboard {uid}: {e}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Grafana validation failed: {e}")
            return False

    async def validate_all(self) -> Dict[str, bool]:
        """Run all validation checks."""
        results = {}

        checks = [
            ('prometheus', self.check_prometheus_metrics()),
            ('loki', self.check_loki_logs()),
            ('tempo', self.check_tempo_traces()),
            ('influxdb', self.check_influxdb_data()),
            ('grafana', self.check_grafana_dashboards())
        ]

        for name, check in checks:
            try:
                results[name] = await check
            except Exception as e:
                logger.error(f"Check {name} failed with error: {e}")
                results[name] = False

        return results

async def main():
    validator = ObservabilityValidator()
    results = await validator.validate_all()

    # Log results
    logger.info("Validation Results:")
    for component, status in results.items():
        logger.info(f"{component}: {'✓' if status else '✗'}")

    # Exit with status code
    if all(results.values()):
        logger.info("All validations passed!")
        sys.exit(0)
    else:
        logger.error("Some validations failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())


# ## example usage
# The script can be used in a Kubernetes Job like this:
#
# apiVersion: batch/v1
# kind: Job
# metadata:
#   name: observability-validation
# spec:
#   template:
#     spec:
#       containers:
#       - name: validator
#         image: python:3.9
#         command: ["python", "/app/validate-data-collection.py"]
#         env:
#         - name: PROMETHEUS_URL
#           value: "http://prometheus:9090"
#         - name: LOKI_URL
#           value: "http://loki:3100"
#         - name: TEMPO_URL
#           value: "http://tempo:3200"
#         - name: INFLUXDB_URL
#           value: "http://homeassistant.local:8086"
#         - name: GRAFANA_URL
#           value: "http://grafana:3000"
#         - name: INFLUXDB_TOKEN
#           valueFrom:
#             secretKeyRef:
#               name: influxdb-credentials
#               key: token
#         - name: GRAFANA_TOKEN
#           valueFrom:
#             secretKeyRef:
#               name: grafana-credentials
#               key: token
#         volumeMounts:
#         - name: validator-code
#           mountPath: /app
#       volumes:
#       - name: validator-code
#         configMap:
#           name: observability-validator
#       restartPolicy: OnFailure
