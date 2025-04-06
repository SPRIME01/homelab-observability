#!/bin/bash
set -e

# Update paths in all scripts
for script in $(find . -name "*.sh"); do
    # Replace homelab-infra paths with homelab-observability
    sed -i 's|homelab-infra/monitoring|homelab-observability|g' "$script"
done

echo "All scripts updated with new paths"
