#!/bin/bash

# Deploy the full observability stack

# Deploy Prometheus
./scripts/deploy-prometheus.sh

# Deploy Grafana
./scripts/deploy-grafana.sh

# Deploy Loki
./scripts/deploy-loki.sh

echo "Observability stack deployment complete."
