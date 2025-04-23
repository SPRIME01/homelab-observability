#!/bin/bash

# Deploy Grafana

# Apply Grafana configuration
kubectl apply -f configs/grafana/provisioning/dashboards/default.yaml

# Apply Grafana dashboards
kubectl apply -f dashboards/application-performance-dashboard.json
kubectl apply -f dashboards/host-monitoring-dashboard.json
kubectl apply -f dashboards/kubernetes-cluster-dashboard.json

echo "Grafana deployment complete."
