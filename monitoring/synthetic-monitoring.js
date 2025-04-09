'use strict';

const opentelemetry = require('@opentelemetry/api');
const { MeterProvider } = require('@opentelemetry/sdk-metrics');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc');
const axios = require('axios');

class SyntheticMonitor {
    constructor(serviceName = 'synthetic-monitor') {
        this.serviceName = serviceName;
        this.setupTelemetry();
    }

    setupTelemetry() {
        // Configure metrics
        const meterProvider = new MeterProvider();
        const metricExporter = new OTLPMetricExporter({
            url: 'http://otel-collector:4317'
        });

        meterProvider.addMetricReader(metricExporter);
        opentelemetry.metrics.setGlobalMeterProvider(meterProvider);

        const meter = opentelemetry.metrics.getMeter(this.serviceName);

        // Create metrics
        this.requestDuration = meter.createHistogram('synthetic_request_duration', {
            description: 'Duration of synthetic requests',
            unit: 'ms'
        });

        this.errorCounter = meter.createCounter('synthetic_request_errors', {
            description: 'Number of synthetic request errors'
        });
    }

    async checkApiEndpoint(url, method = 'GET', expectedStatus = 200) {
        const startTime = Date.now();
        try {
            const response = await axios({
                method,
                url,
                validateStatus: null
            });

            const duration = Date.now() - startTime;
            this.requestDuration.record(duration, {
                endpoint: url,
                method
            });

            if (response.status !== expectedStatus) {
                this.errorCounter.add(1, {
                    endpoint: url,
                    error: 'status_mismatch'
                });
                return false;
            }
            return true;
        } catch (error) {
            this.errorCounter.add(1, {
                endpoint: url,
                error: error.message
            });
            return false;
        }
    }

    async generateAiLoad(modelEndpoint, batchSize = 1) {
        // Create random input data
        const inputData = Array.from({ length: batchSize }, () =>
            Array.from({ length: 3 }, () =>
                Array.from({ length: 224 }, () =>
                    Array.from({ length: 224 }, () =>
                        Math.random() * 2 - 1
                    )
                )
            )
        );

        const startTime = Date.now();
        try {
            const response = await axios.post(modelEndpoint, {
                inputs: inputData
            });

            const duration = Date.now() - startTime;
            this.requestDuration.record(duration, {
                endpoint: modelEndpoint,
                type: 'inference'
            });

            if (response.status !== 200) {
                this.errorCounter.add(1, {
                    endpoint: modelEndpoint,
                    error: 'inference_failed'
                });
            }
        } catch (error) {
            this.errorCounter.add(1, {
                endpoint: modelEndpoint,
                error: error.message
            });
        }
    }

    async triggerHomeAutomation(hassUrl, token) {
        const headers = {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
        };

        const scenarios = [
            { service: 'light/turn_on', entity_id: 'light.living_room' },
            { service: 'switch/toggle', entity_id: 'switch.office_fan' },
            { service: 'scene/turn_on', entity_id: 'scene.evening_mode' }
        ];

        for (const scenario of scenarios) {
            const startTime = Date.now();
            try {
                const response = await axios.post(
                    `${hassUrl}/api/services/${scenario.service}`,
                    { entity_id: scenario.entity_id },
                    { headers }
                );

                const duration = Date.now() - startTime;
                this.requestDuration.record(duration, {
                    service: scenario.service,
                    entity: scenario.entity_id
                });

                if (response.status !== 200) {
                    this.errorCounter.add(1, {
                        service: scenario.service,
                        error: 'automation_failed'
                    });
                }
            } catch (error) {
                this.errorCounter.add(1, {
                    service: scenario.service,
                    error: error.message
                });
            }
        }
    }
}

async function main() {
    const monitor = new SyntheticMonitor();

    async function runMonitoring() {
        try {
            // Check API endpoints
            await monitor.checkApiEndpoint('http://api-gateway/health');
            await monitor.checkApiEndpoint('http://rabbitmq:15672/api/health');

            // Generate AI model load
            await monitor.generateAiLoad('http://triton:8000/v2/models/resnet50/infer');

            // Trigger home automation
            await monitor.triggerHomeAutomation(
                'http://homeassistant:8123',
                'YOUR_LONG_LIVED_ACCESS_TOKEN'
            );
        } catch (error) {
            console.error('Error in monitoring loop:', error);
        }
    }

    // Run monitoring every minute
    setInterval(runMonitoring, 60000);
    runMonitoring(); // Run immediately on start
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = SyntheticMonitor;
