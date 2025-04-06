#!/bin/bash
set -e

INFRA_REPO="/home/sprime01/homelab/homelab-infra"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Preparing to clean up monitoring components from infrastructure repository ===${NC}"
echo "This will remove monitoring components from: $INFRA_REPO"
echo -e "${YELLOW}Warning: Make sure all components have been successfully migrated before proceeding${NC}"
read -p "Are you sure you want to continue? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cleanup aborted${NC}"
    exit 1
fi

# Check if the infrastructure repo exists
if [ ! -d "$INFRA_REPO" ]; then
    echo -e "${RED}Error: Infrastructure repository not found at $INFRA_REPO${NC}"
    exit 1
fi

# Function to backup before deletion
backup_and_delete() {
    local path="$1"
    if [ -e "$path" ]; then
        echo "Backing up $path to ${path}.bak"
        cp -r "$path" "${path}.bak"
        echo "Removing $path"
        rm -rf "$path"
        return 0
    else
        echo "Path not found: $path, skipping..."
        return 1
    fi
}

# Back up and remove monitoring components
echo -e "\n${BLUE}=== Cleaning up Prometheus components ===${NC}"
backup_and_delete "$INFRA_REPO/monitoring/prometheus"

echo -e "\n${BLUE}=== Cleaning up Grafana components ===${NC}"
backup_and_delete "$INFRA_REPO/monitoring/grafana"

echo -e "\n${BLUE}=== Cleaning up Alertmanager components ===${NC}"
backup_and_delete "$INFRA_REPO/monitoring/alertmanager"

echo -e "\n${BLUE}=== Cleaning up Correlator components ===${NC}"
backup_and_delete "$INFRA_REPO/monitoring/correlator"

echo -e "\n${BLUE}=== Cleaning up Exporters components ===${NC}"
backup_and_delete "$INFRA_REPO/monitoring/exporters"

echo -e "\n${BLUE}=== Cleaning up Loki components ===${NC}"
backup_and_delete "$INFRA_REPO/monitoring/loki"

echo -e "\n${GREEN}Cleanup completed!${NC}"
echo -e "Backup files were created with .bak extension in case you need to restore anything"
echo -e "Consider updating the migration checklist to mark cleanup steps as completed"
