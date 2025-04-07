# Integration Guide

This document describes how the observability components integrate with other repositories in the homelab project.

## Repository Integration Points

### homelab-infra

- **Kubernetes Resources**: The homelab-observability stack is deployed on the Kubernetes cluster managed by homelab-infra
- **Service Discovery**: Prometheus discovers and scrapes metrics from services deployed via homelab-infra
- **Access Control**: Authentication and authorization are managed by services in homelab-infra

### homelab-ai

- **Model Monitoring**: Observability for AI models deployed by homelab-ai
- **Resource Usage**: Track GPU, memory, and CPU utilization for AI workloads
- **Alert Integration**: Send alerts about model performance to appropriate channels

### homelab-data

- **Message Queue Monitoring**: Track metrics from RabbitMQ and other messaging services
- **Data Pipeline Observability**: Monitor data processing workflows
- **Schema Evolution Tracking**: Track changes to data schemas over time

## Integration Testing

When making changes to observability components, ensure that:

1. All metrics continue to be collected from other systems
2. Dashboards properly display data from all integrated systems
3. Alert rules correctly trigger based on conditions in other systems
4. Log collection includes logs from all relevant services

## Cross-Repository Dependencies

- **Prometheus Service Discovery**: Relies on Kubernetes service annotations in homelab-infra
- **Dashboard Variables**: Many Grafana dashboards use variables based on services in other repositories
- **Alert Notification Channels**: Alerts may be routed to systems defined in other repositories
