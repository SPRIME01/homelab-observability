# 🏠 Homelab Observability Stack

> 📊 Comprehensive monitoring and observability configuration for my homelab infrastructure

## 🎯 Overview

This repository contains the complete observability stack configuration for my homelab, providing end-to-end monitoring, logging, and alerting capabilities.

## 🧰 Components

- 📡 **OpenTelemetry Collector** - Data collection and processing
- 📈 **Grafana** - Visualization and dashboarding
- 🚨 **Alerting** - Prometheus alerting rules and notifications
- 📝 **Logging** - Loki-based log aggregation
- ⏱️ **Tempo** - Distributed tracing

## 🏗️ Directory Structure

```bash
.
├── collectors/         # OpenTelemetry collector configurations
├── dashboards/        # Grafana dashboard definitions
├── alerting/          # Alert rules and notification policies
├── logging/           # Logging configurations
└── configs/           # General component configurations
```

## 🚀 Getting Started

1. Configure the OpenTelemetry Collector
    ```bash
    cd collectors
    kubectl apply -f otel-collector.yaml
    ```

2. Deploy Grafana dashboards
    ```bash
    cd dashboards
    kubectl apply -f .
    ```

## 📊 Monitoring Stack

- **Metrics**: Prometheus-based metrics collection
- **Logs**: Loki for log aggregation
- **Traces**: Tempo for distributed tracing
- **Dashboards**: Pre-configured Grafana dashboards

## ⚙️ Configuration

Refer to individual component directories for detailed configuration options:

- `collectors/README.md` - OpenTelemetry setup
- `dashboards/README.md` - Dashboard management
- `alerting/README.md` - Alert configuration
- `logging/README.md` - Log aggregation setup

## 🔐 Security

Sensitive information is managed through Kubernetes secrets. See `.gitignore` for excluded patterns.

## 📝 License

MIT License

## 🤝 Contributing

Contributions welcome! Please read the contributing guidelines first.
