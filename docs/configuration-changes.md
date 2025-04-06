# Configuration Changes After Migration

This document outlines the configuration changes made during the migration of monitoring and observability components from `homelab-infra` to `homelab-observability`.

## Directory Structure Changes

| Before (homelab-infra) | After (homelab-observability) |
|------------------------|-------------------------------|
| `/monitoring/prometheus/prometheus-config.yaml` | `/configs/prometheus/prometheus-config.yaml` |
| `/monitoring/prometheus/alert-rules.yaml` | `/alerting/prometheus-rules.yaml` |
| `/monitoring/grafana/dashboards/*.json` | `/dashboards/*.json` |
| `/monitoring/alertmanager/*` | `/alerting/alertmanager/*` |
| `/monitoring/correlator/deployment.yaml` | `/collectors/correlator/deployment.yaml` |
| `/monitoring/exporters/*` | `/collectors/exporters/*` |
| `/monitoring/loki/*` | `/logs/loki/*` |

## Script Changes

Scripts that referenced these paths have been updated:
- `deploy-dashboards.sh`
- `deploy-correlator.sh`

## Kubernetes Manifest Changes

If you're using Kubernetes manifests to deploy these components, update your ConfigMap and Volume references to point to the new locations.

### Example ConfigMap Change

```yaml
# Before
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    # Contents of homelab-infra/monitoring/prometheus/prometheus-config.yaml

# After
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    # Contents of homelab-observability/configs/prometheus/prometheus-config.yaml
```

## Testing Your Changes

After updating paths, you should:

1. Deploy the updated configurations
2. Verify that metrics are being collected correctly
3. Check that dashboards load properly in Grafana
4. Test that alerting rules are firing as expected
5. Verify log collection and querying is working

Use the `test-observability-stack.sh` script to help with verification.

## Running Molecule Tests

### Prerequisites
1. Install the required dependencies:
```bash
python3 -m pip install --user molecule molecule-docker ansible-lint yamllint
```

2. Ensure Docker is installed and your user has permissions:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Running Tests

1. Navigate to the role directory you want to test:
```bash
cd roles/[role-name]
```

2. Run the full test suite:
```bash
molecule test
```

3. For development, you can run individual steps:
```bash
molecule create     # Create test containers
molecule converge   # Run the playbook
molecule verify     # Run test cases
molecule destroy    # Clean up
```

### Troubleshooting

If you encounter issues:

1. Use `molecule --debug test` for verbose output
2. Check Docker permissions with `docker ps`
3. Verify test scenarios in `molecule/default/converge.yml`
4. Inspect test container: `molecule login`

## Rollback Plan

In case of issues, backup files are stored in the original locations with `.bak` extension. You can restore them if needed:

```bash
# Example rollback command
cp /home/sprime01/homelab/homelab-infra/monitoring/prometheus/prometheus-config.yaml.bak /home/sprime01/homelab/homelab-infra/monitoring/prometheus/prometheus-config.yaml
```
