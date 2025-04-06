#!/bin/bash
set -e

echo "Updating Grafana dashboard provisioning..."

# Check if running in the correct directory
if [[ ! -d "./dashboards" ]]; then
  echo "Error: Must run from the homelab-observability root directory"
  exit 1
fi

# Create dashboard provisioning configuration directory if it doesn't exist
mkdir -p ./configs/grafana/provisioning/dashboards

# Create dashboard provisioning configuration file
cat > ./configs/grafana/provisioning/dashboards/default.yaml << EOF
apiVersion: 1

providers:
  - name: 'Homelab Dashboards'
    orgId: 1
    folder: 'Homelab'
    folderUid: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
EOF

echo "Dashboard provisioning configuration created at ./configs/grafana/provisioning/dashboards/default.yaml"
echo "Don't forget to mount this configuration and dashboards in your Grafana deployment"
