#!/bin/bash
set -e

echo "Updating Prometheus configuration references..."

# Check if running in the correct directory
if [[ ! -d "./configs/prometheus" ]]; then
  echo "Error: Must run from the homelab-observability root directory"
  exit 1
fi

# Update any Kubernetes manifests that reference Prometheus configs
find . -name "*.yaml" -o -name "*.yml" | xargs sed -i 's|homelab-observability/configs/prometheus|homelab-observability/configs/prometheus|g'

# Update configuration paths in any deployment scripts
find ./scripts -name "*.sh" | xargs sed -i 's|homelab-observability/configs/prometheus|homelab-observability/configs/prometheus|g'

echo "Prometheus configuration references updated"
