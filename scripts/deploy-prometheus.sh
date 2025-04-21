#!/bin/bash

# Deploy Prometheus

# Apply Prometheus configuration
kubectl apply -f configs/prometheus/prometheus-config.yaml

# Apply Prometheus rules
kubectl apply -f alerting/prometheus-rules.yaml

echo "Prometheus deployment complete."
