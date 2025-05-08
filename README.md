# Homelab Observability

This repository contains the monitoring and observability stack for the homelab project. It was created as part of a migration from the original `homelab-infra` repository to better organize the codebase.

## Repository Structure

- **alerting/**: Alert manager configurations and notification templates
- **collectors/**: Monitoring data collectors and exporters
- **configs/**: Configuration files for observability components
- **dashboards/**: Grafana dashboards
- **grafana/**: Grafana configuration and provisioning
- **log-management/**: Log collection and processing configurations
- **opentelemetry/**: OpenTelemetry configurations and collectors
- **scripts/**: Utility scripts for deployment and maintenance

## Migration Status

The migration from `homelab-infra` has been completed. All monitoring components have been successfully moved and tested in their new locations.

## Integration with Other Repositories

This repository works in conjunction with:

- **homelab-infra**: Core infrastructure components
- **homelab-ai**: AI/ML components for the homelab
- **homelab-data**: Data processing and storage services

## Getting Started

1. Clone this repository
2. Set up dependencies as described in the docs folder
3. Run the deployment scripts to set up observability stack

## Deployment

To deploy the full observability stack:

```bash
./scripts/deploy-observability.sh
```

To deploy individual components:

```bash
./scripts/deploy-prometheus.sh
./scripts/deploy-grafana.sh
./scripts/deploy-loki.sh
```

## Environment Variables

Ensure the following environment variables are set before running `setup-influxdb.py`:

- `INFLUXDB_URL`: URL of the InfluxDB instance
- `INFLUXDB_TOKEN`: Admin token for InfluxDB
- `INFLUXDB_ORG`: Organization name in InfluxDB

## Testing

Automated tests are available in the `tests/` directory.

## Contributing

See CONTRIBUTING.md for details on how to contribute to this project.

## Future Improvements

For a comprehensive to-do list identifying all necessary tasks to ensure the project is robust, maintainable, well-documented, and functionally correct, please refer to the `docs/future-improvements.md` file.
