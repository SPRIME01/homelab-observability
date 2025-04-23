#!/bin/bash

# Deploy Loki

# Apply Loki configuration
kubectl apply -f configs/loki/loki-config.yaml

# Apply Loki rules
kubectl apply -f alerting/loki-rules.yaml

echo "Loki deployment complete."
