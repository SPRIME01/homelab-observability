'use strict';

const opentelemetry = require('@opentelemetry/api');
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { Resource } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');
const { BatchSpanProcessor } = require('@opentelemetry/sdk-trace-base');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-grpc');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc');
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
const { HttpInstrumentation } = require('@opentelemetry/instrumentation-http');
const { ExpressInstrumentation } = require('@opentelemetry/instrumentation-express');
const { MongoDBInstrumentation } = require('@opentelemetry/instrumentation-mongodb');
const { PgInstrumentation } = require('@opentelemetry/instrumentation-pg');
const { RedisInstrumentation } = require('@opentelemetry/instrumentation-redis');
const { AmqplibInstrumentation } = require('@opentelemetry/instrumentation-amqplib');

class HomelabTelemetry {
    constructor(config = {}) {
        this.config = {
            serviceName: config.serviceName || process.env.SERVICE_NAME || 'unnamed-service',
            environment: config.environment || process.env.NODE_ENV || 'homelab',
            version: config.version || process.env.SERVICE_VERSION || '1.0.0',
            collectorEndpoint: config.collectorEndpoint || process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://otel-collector:4317',
            autoInstrument: config.autoInstrument !== false,
            sampleRate: config.sampleRate || 1.0,
            metricInterval: config.metricInterval || 15000,
        };

        this.tracer = null;
        this.meter = null;
        this.sdk = null;
        this.init();
    }

    init() {
        const resource = new Resource({
            [SemanticResourceAttributes.SERVICE_NAME]: this.config.serviceName,
            [SemanticResourceAttributes.SERVICE_VERSION]: this.config.version,
            [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: this.config.environment,
        });

        const traceExporter = new OTLPTraceExporter({
            url: this.config.collectorEndpoint,
        });

        const metricExporter = new OTLPMetricExporter({
            url: this.config.collectorEndpoint,
        });

        const metricReader = new PeriodicExportingMetricReader({
            exporter: metricExporter,
            exportIntervalMillis: this.config.metricInterval,
        });

        const instrumentations = this.config.autoInstrument ? [
            new HttpInstrumentation(),
            new ExpressInstrumentation(),
            new MongoDBInstrumentation(),
            new PgInstrumentation(),
            new RedisInstrumentation(),
            new AmqplibInstrumentation(),
        ] : [];

        this.sdk = new NodeSDK({
            resource,
            traceExporter,
            metricReader,
            instrumentations,
            spanProcessor: new BatchSpanProcessor(traceExporter),
        });

        this.sdk.start();
        this.tracer = opentelemetry.trace.getTracer(this.config.serviceName);
        this.meter = opentelemetry.metrics.getMeter(this.config.serviceName);

        // Handle graceful shutdown
        process.on('SIGTERM', () => this.shutdown());
        process.on('SIGINT', () => this.shutdown());
    }

    // Manual instrumentation helpers
    createSpan(name, options = {}) {
        return this.tracer.startSpan(name, options);
    }

    wrapAsync(name, fn) {
        return async (...args) => {
            const span = this.createSpan(name);
            try {
                const result = await fn(...args);
                span.end();
                return result;
            } catch (error) {
                span.recordException(error);
                span.setStatus({ code: opentelemetry.SpanStatusCode.ERROR });
                span.end();
                throw error;
            }
        };
    }

    // Context propagation utilities
    injectContext(headers = {}) {
        const context = opentelemetry.trace.getActiveSpan()?.context();
        if (context) {
            opentelemetry.propagation.inject(context, headers);
        }
        return headers;
    }

    extractContext(headers = {}) {
        return opentelemetry.propagation.extract(headers);
    }

    // Metrics helpers
    createCounter(name, options = {}) {
        return this.meter.createCounter(name, options);
    }

    createHistogram(name, options = {}) {
        return this.meter.createHistogram(name, options);
    }

    // n8n workflow integration
    instrumentN8nNode(nodeType, executeFunction) {
        return async function (...args) {
            const telemetry = HomelabTelemetry.getInstance();
            const span = telemetry.createSpan(`n8n.node.${nodeType}`, {
                attributes: {
                    'n8n.node.type': nodeType,
                    'n8n.workflow.id': this.workflow?.id,
                },
            });

            try {
                const result = await executeFunction.apply(this, args);
                span.end();
                return result;
            } catch (error) {
                span.recordException(error);
                span.setStatus({ code: opentelemetry.SpanStatusCode.ERROR });
                span.end();
                throw error;
            }
        };
    }

    // Express middleware for request tracing
    expressMiddleware() {
        return (req, res, next) => {
            const span = this.createSpan(`${req.method} ${req.path}`, {
                kind: opentelemetry.SpanKind.SERVER,
                attributes: {
                    'http.method': req.method,
                    'http.url': req.url,
                    'http.route': req.route?.path,
                },
            });

            // Add trace context to response headers
            this.injectContext(res.locals.traceHeaders = {});

            // End span on response finish
            res.on('finish', () => {
                span.setAttributes({
                    'http.status_code': res.statusCode,
                });
                span.end();
            });

            next();
        };
    }

    shutdown() {
        this.sdk.shutdown()
            .then(() => console.log('Telemetry SDK shut down successfully'))
            .catch((error) => console.error('Error shutting down Telemetry SDK', error))
            .finally(() => process.exit(0));
    }

    // Singleton instance
    static instance = null;
    static getInstance(config) {
        if (!HomelabTelemetry.instance) {
            HomelabTelemetry.instance = new HomelabTelemetry(config);
        }
        return HomelabTelemetry.instance;
    }
}

module.exports = HomelabTelemetry;

// Example usage:
/*
const HomelabTelemetry = require('./nodejs_instrumentation');

// Initialize telemetry
const telemetry = HomelabTelemetry.getInstance({
    serviceName: 'my-service',
    environment: 'homelab',
});

// Express app instrumentation
const app = express();
app.use(telemetry.expressMiddleware());

// Manual span creation
app.get('/api/data', async (req, res) => {
    const span = telemetry.createSpan('fetch-data');
    try {
        const data = await fetchData();
        span.end();
        res.json(data);
    } catch (error) {
        span.recordException(error);
        span.end();
        res.status(500).json({ error: error.message });
    }
});

// n8n node instrumentation
class MyCustomNode {
    execute = telemetry.instrumentN8nNode('MyCustomNode', async function(items) {
        // Node execution logic
        return items;
    });
}
*/
