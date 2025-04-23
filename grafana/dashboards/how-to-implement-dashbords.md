# Implementing Grafana Dashboards

This directory contains JSON definitions for various Grafana dashboards designed to monitor key services within the homelab environment.

## Dashboards Included

*   **`rabbitmq-overview.json`**: Monitors RabbitMQ message queues, rates, connections, etc.
*   **`ai-services-overview.json`**: Monitors AI inference services (like Triton/Ray), focusing on GPU utilization, inference latency, and throughput.
*   **`n8n-workflow-overview.json`**: Monitors n8n workflow automation, tracking execution success/failure rates and durations.
*   **`home-assistant-overview.json`**: Monitors Home Assistant, visualizing sensor data, automation triggers, and system status.

## How to Use

1.  **Import into Grafana:**
    *   Navigate to your Grafana instance.
    *   Go to `Dashboards` -> `Browse`.
    *   Click the `Import` button.
    *   Either upload the `.json` file directly or paste the JSON content into the text area.
    *   Select the appropriate Prometheus data source when prompted.
    *   Click `Import`.

2.  **Customize Prometheus Queries:**
    *   **Crucial Step:** These dashboards are templates. The Prometheus Query Language (PromQL) expressions (`expr` fields within the JSON panel definitions) are placeholders or examples based on common metric names (e.g., from standard exporters like the Home Assistant integration, DCGM, Triton metrics).
    *   You **must** edit the imported dashboards in Grafana.
    *   For each panel, review the `expr` in the query editor.
    *   Replace the placeholder queries with the actual PromQL queries that match the metrics and labels exposed by *your specific* Prometheus exporters (e.g., your RabbitMQ exporter, n8n exporter, GPU exporter, Home Assistant configuration). Pay close attention to metric names and labels like `job`, `instance`, `entity_id`, `model`, `queue`, etc.

3.  **Adjust Template Variables:**
    *   Some dashboards use template variables (e.g., `$model`, `$gpu`, `$workflow`, `$sensor_entity`, `$area`) to allow dynamic filtering.
    *   Edit the dashboard settings (`Dashboard settings` -> `Variables`).
    *   Verify that the `Query Options` for each variable correctly fetch the desired label values from *your* metrics. Adjust the `label_values(metric_name, label_name)` queries as needed.

4.  **Configure Alerting Rules:**
    *   Example alerting rules are included in some panels (e.g., RabbitMQ queue depth, AI latency, n8n failure rate, HA temperature).
    *   Edit the panel and go to the `Alert` tab.
    *   Adjust the threshold values (`Conditions`) to levels appropriate for your environment.
    *   Configure notification channels in Grafana (`Alerting` -> `Notification channels`) and link them to the desired alerts.

5.  **Save Changes:**
    *   Once customized, save the dashboards in Grafana to preserve your changes.

By following these steps, you can adapt these template dashboards to effectively monitor your specific homelab services.
