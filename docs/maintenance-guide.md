# Observability Maintenance Guide

This document provides guidance for maintaining the observability stack over time.

## Regular Maintenance Tasks

### Weekly
- Check alert status and resolve any recurring alerts
- Verify all targets are being scraped in Prometheus
- Ensure log retention policies are working correctly

### Monthly
- Update dashboards with any new metrics or improvements
- Check resource usage of observability components
- Review alert thresholds and adjust as needed

### Quarterly
- Upgrade components to latest stable versions
- Review and optimize retention periods and storage
- Test disaster recovery procedures

## Configuration Management

### Prometheus
- Kubernetes CRDs are in `configs/prometheus/prometheus-config.yaml`
- Standard format for local testing is in `configs/prometheus/prometheus.yml`
- Use `fix-prometheus-config.sh` when moving between formats

### Grafana
- Dashboards are stored in `dashboards/` as JSON files
- When modifying dashboards, export them to maintain version control
- Update dashboard provisioning when adding new dashboards

### Alerting
- Rules are stored in `alerting/prometheus-rules.yaml` (Kubernetes format)
- Standard rules for validation are in `alerting/prometheus-rules-standard.yml`
- Test rules with `promtool check rules` before deploying

## Troubleshooting

### Common Issues
- If Prometheus is not finding targets, check the service discovery configuration
- For missing metrics, verify the exporter is running and scraped
- Dashboard variables may need updating when services change names or namespaces

### Diagnostic Commands
```bash
# Check Prometheus target status
kubectl exec -n monitoring deploy/prometheus-server -- wget -qO- http://localhost:9090/api/v1/targets | jq

# Verify Prometheus rules
kubectl exec -n monitoring deploy/prometheus-server -- wget -qO- http://localhost:9090/api/v1/rules | jq

# Check alert status
kubectl exec -n monitoring deploy/prometheus-server -- wget -qO- http://localhost:9090/api/v1/alerts | jq
```
