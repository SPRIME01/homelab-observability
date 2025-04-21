import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter
import logging
import datetime
import ipaddress

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Placeholder for known malicious IPs/subnets (replace with actual feed/list)
KNOWN_MALICIOUS_IPS = {"192.0.2.100", "203.0.113.5"}
# Ports typically used for specific services (example)
COMMON_SERVICE_PORTS = {
    80: "HTTP",
    443: "HTTPS",
    22: "SSH",
    53: "DNS",
    # Add more mappings relevant to your homelab
}
# Thresholds for anomaly detection (example)
ANOMALY_THRESHOLD_BYTES = 1 * 1024 * 1024 * 1024 # 1 GB
ANOMALY_THRESHOLD_CONNECTIONS = 1000

# --- Data Loading ---

def load_flow_data(filepath: str) -> pd.DataFrame:
    """
    Loads flow data from a source (e.g., CSV).
    Assumes CSV format with columns like:
    timestamp, src_ip, dst_ip, src_port, dst_port, protocol, bytes, packets

    NOTE: This is a placeholder. Real-world implementation depends heavily
          on the flow export format (NetFlow, sFlow, PCAP analysis results).
          Privacy: Ensure only necessary metadata is loaded, avoid payload.
    """
    try:
        # Example using pandas read_csv
        # Adjust parameters based on your actual data format
        df = pd.read_csv(
            filepath,
            parse_dates=['timestamp'],
            # dtype={'src_port': 'Int64', 'dst_port': 'Int64'} # Handle potential NaN ports
        )
        logging.info(f"Loaded {len(df)} flow records from {filepath}")
        # Data Cleaning/Preprocessing (Example)
        df.dropna(subset=['src_ip', 'dst_ip', 'bytes'], inplace=True)
        df['src_port'] = pd.to_numeric(df['src_port'], errors='coerce').fillna(0).astype(int)
        df['dst_port'] = pd.to_numeric(df['dst_port'], errors='coerce').fillna(0).astype(int)
        df['bytes'] = pd.to_numeric(df['bytes'], errors='coerce').fillna(0).astype(int)
        return df
    except FileNotFoundError:
        logging.error(f"Flow data file not found: {filepath}")
        return pd.DataFrame()
    except Exception as e:
        logging.error(f"Error loading flow data: {e}")
        return pd.DataFrame()

# --- Analysis ---

def identify_top_talkers(df: pd.DataFrame, top_n: int = 10):
    """Identifies top source and destination IPs by byte count."""
    if df.empty:
        return {}, {}
    top_src = df.groupby('src_ip')['bytes'].sum().nlargest(top_n).to_dict()
    top_dst = df.groupby('dst_ip')['bytes'].sum().nlargest(top_n).to_dict()
    logging.info(f"Identified top {top_n} talkers.")
    return top_src, top_dst

def identify_frequent_ports(df: pd.DataFrame, top_n: int = 10):
    """Identifies most frequently used destination ports."""
    if df.empty:
        return {}
    frequent_ports = df['dst_port'].value_counts().nlargest(top_n).to_dict()
    logging.info(f"Identified top {top_n} destination ports.")
    return frequent_ports

def detect_anomalies(df: pd.DataFrame):
    """Basic anomaly detection based on byte counts and connection frequency."""
    anomalies = []
    if df.empty:
        return anomalies

    # Anomaly 1: Excessive byte transfer per flow
    large_flows = df[df['bytes'] > ANOMALY_THRESHOLD_BYTES]
    if not large_flows.empty:
        logging.warning(f"Detected {len(large_flows)} flows exceeding byte threshold ({ANOMALY_THRESHOLD_BYTES} bytes).")
        anomalies.extend(large_flows.to_dict('records'))

    # Anomaly 2: Excessive connections from a single source
    connection_counts = df['src_ip'].value_counts()
    high_conn_sources = connection_counts[connection_counts > ANOMALY_THRESHOLD_CONNECTIONS]
    if not high_conn_sources.empty:
        logging.warning(f"Detected {len(high_conn_sources)} sources exceeding connection threshold ({ANOMALY_THRESHOLD_CONNECTIONS}).")
        # Could add more details to anomalies list if needed
        anomalies.append({"type": "high_connection_source", "sources": high_conn_sources.to_dict()})

    # Add more anomaly detection rules as needed (e.g., unusual port scanning, time-based anomalies)
    return anomalies

# --- Security Detection ---

def detect_security_issues(df: pd.DataFrame):
    """Detects potential security issues based on flow data."""
    issues = []
    if df.empty:
        return issues

    # Issue 1: Communication with known malicious IPs
    malicious_comm_src = df[df['src_ip'].isin(KNOWN_MALICIOUS_IPS)]
    malicious_comm_dst = df[df['dst_ip'].isin(KNOWN_MALICIOUS_IPS)]
    if not malicious_comm_src.empty or not malicious_comm_dst.empty:
        logging.warning(f"Detected communication involving known malicious IPs.")
        issues.extend(malicious_comm_src.to_dict('records'))
        issues.extend(malicious_comm_dst.to_dict('records'))

    # Issue 2: Unusual port usage (e.g., non-standard ports for common services - requires context)
    # Example: Look for traffic NOT using port 443 to common web IPs (requires external IP context)
    # This requires more sophisticated logic and context about your network.

    # Issue 3: Potential data exfiltration (large outbound transfers to external IPs)
    # Define internal subnets (adjust to your homelab)
    internal_subnets = [ipaddress.ip_network("192.168.1.0/24"), ipaddress.ip_network("10.0.0.0/8")]
    df['src_is_internal'] = df['src_ip'].apply(lambda ip: any(ipaddress.ip_address(ip) in net for net in internal_subnets))
    df['dst_is_internal'] = df['dst_ip'].apply(lambda ip: any(ipaddress.ip_address(ip) in net for net in internal_subnets))

    large_outbound = df[(df['src_is_internal']) & (~df['dst_is_internal']) & (df['bytes'] > ANOMALY_THRESHOLD_BYTES / 10)] # Lower threshold for outbound
    if not large_outbound.empty:
         logging.warning(f"Detected {len(large_outbound)} potentially large outbound data transfers.")
         issues.extend(large_outbound.to_dict('records'))


    return issues

# --- Visualization ---

def visualize_communication_graph(df: pd.DataFrame, output_filename="network_graph.png", top_n_edges=50):
    """Creates a graph visualizing network communication (top N edges by byte count)."""
    if df.empty:
        logging.warning("No data to visualize.")
        return

    # Aggregate data for graph edges (bytes per src-dst pair)
    # Resource Efficiency: Limit the number of edges shown
    graph_data = df.groupby(['src_ip', 'dst_ip'])['bytes'].sum().nlargest(top_n_edges).reset_index()

    if graph_data.empty:
        logging.warning("No aggregated graph data to visualize.")
        return

    G = nx.DiGraph()
    for _, row in graph_data.iterrows():
        # Add edge with weight (bytes)
        G.add_edge(row['src_ip'], row['dst_ip'], weight=row['bytes'])

    if not G.nodes:
        logging.warning("Graph has no nodes after processing.")
        return

    plt.figure(figsize=(15, 15))
    pos = nx.spring_layout(G, k=0.5) # Adjust layout algorithm and parameters as needed

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=700, node_color='skyblue', alpha=0.8)

    # Draw edges - adjust width based on weight (bytes)
    # Normalize weights for better visualization
    weights = [G[u][v]['weight'] for u, v in G.edges()]
    max_weight = max(weights) if weights else 1
    edge_widths = [(w / max_weight * 5) + 0.5 for w in weights] # Min width 0.5, max 5.5
    nx.draw_networkx_edges(G, pos, width=edge_widths, alpha=0.5, edge_color='gray', arrows=True)

    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=8)

    plt.title(f"Network Communication Graph (Top {top_n_edges} Connections by Bytes)")
    plt.axis('off')
    try:
        plt.savefig(output_filename)
        logging.info(f"Network graph saved to {output_filename}")
    except Exception as e:
        logging.error(f"Failed to save network graph: {e}")
    plt.close() # Close the plot to free memory

# --- Reporting ---

def generate_bandwidth_report(df: pd.DataFrame, output_filename="bandwidth_report.txt"):
    """Generates a report on bandwidth usage by service (approximated by dest port)."""
    if df.empty:
        logging.warning("No data for bandwidth report.")
        return

    # Aggregate bytes by destination port
    port_usage = df.groupby('dst_port')['bytes'].sum().sort_values(ascending=False)

    total_bytes = df['bytes'].sum()

    try:
        with open(output_filename, 'w') as f:
            f.write(f"Bandwidth Usage Report - {datetime.datetime.now()}\n")
            f.write("=" * 40 + "\n")
            f.write(f"Total Bytes Transferred: {total_bytes / (1024**3):.2f} GB\n")
            f.write("-" * 40 + "\n")
            f.write("Bandwidth Usage by Destination Port (Top 20):\n\n")
            f.write(f"{'Port':<10} {'Service':<15} {'Bytes':<15} {'Percentage':<10}\n")
            f.write("-" * 50 + "\n")

            for port, byte_count in port_usage.head(20).items():
                service_name = COMMON_SERVICE_PORTS.get(port, "Unknown")
                percentage = (byte_count / total_bytes * 100) if total_bytes > 0 else 0
                f.write(f"{port:<10} {service_name:<15} {byte_count:<15} {percentage:.2f}%\n")

            logging.info(f"Bandwidth report saved to {output_filename}")
    except Exception as e:
        logging.error(f"Failed to write bandwidth report: {e}")


# --- Main Execution Example ---

if __name__ == "__main__":
    logging.info("Starting network traffic analysis...")

    # Replace with the actual path to your flow data
    flow_data_file = "path/to/your/flow_data.csv"

    df_flows = load_flow_data(flow_data_file)

    if not df_flows.empty:
        # --- Perform Analysis ---
        top_sources, top_destinations = identify_top_talkers(df_flows)
        logging.info(f"Top Sources by Bytes: {top_sources}")
        logging.info(f"Top Destinations by Bytes: {top_destinations}")

        frequent_ports = identify_frequent_ports(df_flows)
        logging.info(f"Most Frequent Destination Ports: {frequent_ports}")

        # --- Detect Issues ---
        anomalies_detected = detect_anomalies(df_flows)
        if anomalies_detected:
             logging.warning(f"Anomalies Detected: {len(anomalies_detected)}")
             # Process/log anomalies further if needed

        security_issues_detected = detect_security_issues(df_flows)
        if security_issues_detected:
            logging.warning(f"Potential Security Issues Detected: {len(security_issues_detected)}")
            # Process/log issues further if needed

        # --- Visualize & Report ---
        visualize_communication_graph(df_flows, output_filename="homelab_network_graph.png")
        generate_bandwidth_report(df_flows, output_filename="homelab_bandwidth_report.txt")

        logging.info("Network traffic analysis finished.")
    else:
        logging.error("Analysis aborted due to data loading issues.")
