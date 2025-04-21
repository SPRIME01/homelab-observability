#!/usr/bin/env python3
"""
Script to configure secure access to the existing InfluxDB instance on Home Assistant Yellow.
This script sets up:
 1. A dedicated user with appropriate permissions for the observability stack
 2. Retention policies for different data types
 3. Continuous queries for downsampling data
 4. Buckets for different data domains
"""

import os
import sys
import argparse
import logging
from datetime import timedelta
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.authorization import Authorization
from influxdb_client.domain.permission import Permission, PermissionResource

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_INFLUXDB_URL = "http://homeassistant.local:8086"
DEFAULT_ADMIN_TOKEN = os.getenv('INFLUXDB_ADMIN_TOKEN', '')  # This should be provided as an argument or environment variable
DEFAULT_ORG = "homeassistant"

# Retention configurations in hours
RETENTION_CONFIGS = {
    "metrics": {
        "raw": 24 * 7,             # 7 days for raw metrics
        "downsampled_1h": 24 * 30,  # 30 days for hourly averages
        "downsampled_1d": 24 * 365  # 365 days for daily averages
    },
    "logs": {
        "raw": 24 * 14,            # 14 days for raw logs
        "summarized": 24 * 90      # 90 days for summarized logs
    },
    "events": {
        "raw": 24 * 30             # 30 days for events
    }
}

# Data domain buckets
DATA_DOMAINS = [
    "system_metrics",
    "application_metrics",
    "kubernetes_metrics",
    "rabbitmq_metrics",
    "home_assistant",
    "ai_inference",
    "system_logs",
    "application_logs",
    "security_events"
]

class InfluxDBConfigurator:
    def __init__(self, url, token, org):
        """Initialize the InfluxDB configurator.

        Args:
            url: The URL of the InfluxDB server
            token: The admin token for authentication
            org: The organization name
        """
        self.url = url
        self.token = token
        self.org = org

        # Create the InfluxDB client
        self.client = influxdb_client.InfluxDBClient(
            url=self.url,
            token=self.token,
            org=self.org
        )

        # API instances
        self.users_api = self.client.users_api()
        self.buckets_api = self.client.buckets_api()
        self.authorizations_api = self.client.authorizations_api()
        self.query_api = self.client.query_api()
        self.org_id = self._get_org_id()

        logger.info(f"Connected to InfluxDB at {url} with organization {org}")

    def _get_org_id(self):
        """Get the organization ID from the name."""
        orgs = self.client.organizations_api().find_organizations(org=self.org)
        if not orgs or len(orgs) == 0:
            raise ValueError(f"Organization '{self.org}' not found.")
        return orgs[0].id

    def create_dedicated_user(self, username, password=None):
        """Create a dedicated user for the observability stack.

        Args:
            username: The username for the new user
            password: Optional password (if None, a token-based auth will be used)

        Returns:
            The user token for API access
        """
        logger.info(f"Creating dedicated user: {username}")

        # Define permissions for the observability user
        permissions = []

        # For each bucket we'll create, add read/write permissions
        for domain in DATA_DOMAINS:
            resource = PermissionResource(type="buckets", org_id=self.org_id)
            permissions.append(Permission(action="read", resource=resource))
            permissions.append(Permission(action="write", resource=resource))

        # Create the authorization (token)
        auth_desc = f"Token for {username} - Observability Stack"
        auth = Authorization(org_id=self.org_id, permissions=permissions, description=auth_desc)

        result = self.authorizations_api.create_authorization(auth)
        logger.info(f"Created authorization for {username} with ID: {result.id}")

        return result.token

    def create_buckets(self):
        """Create buckets for different data domains."""
        for domain in DATA_DOMAINS:
            logger.info(f"Creating bucket: {domain}")

            # Determine retention policy based on the data type
            if "metrics" in domain:
                retention = RETENTION_CONFIGS["metrics"]["raw"]
            elif "logs" in domain:
                retention = RETENTION_CONFIGS["logs"]["raw"]
            elif "events" in domain:
                retention = RETENTION_CONFIGS["events"]["raw"]
            else:
                retention = RETENTION_CONFIGS["metrics"]["raw"]  # Default

            # Convert hours to seconds for the API
            retention_seconds = int(retention * 3600)

            # Create the bucket
            try:
                self.buckets_api.create_bucket(
                    bucket_name=domain,
                    org_id=self.org_id,
                    retention_rules=[{
                        "type": "expire",
                        "everySeconds": retention_seconds,
                        "shardGroupDurationSeconds": 86400  # 1 day shard duration
                    }]
                )
                logger.info(f"Created bucket '{domain}' with retention: {retention} hours")
            except Exception as e:
                if "bucket already exists" in str(e).lower():
                    logger.warning(f"Bucket '{domain}' already exists. Updating...")
                    bucket = self.buckets_api.find_bucket_by_name(domain)
                    self.buckets_api.update_bucket_retention_rules(
                        bucket_id=bucket.id,
                        retention_rules=[{
                            "type": "expire",
                            "everySeconds": retention_seconds,
                            "shardGroupDurationSeconds": 86400
                        }]
                    )
                else:
                    logger.error(f"Error creating bucket '{domain}': {e}")

    def setup_continuous_queries(self):
        """Set up continuous queries for downsampling data."""
        # We'll specifically target metric buckets for downsampling
        metric_domains = [domain for domain in DATA_DOMAINS if "metrics" in domain]

        for domain in metric_domains:
            logger.info(f"Setting up downsampling for: {domain}")

            # Create 1-hour downsampled bucket
            downsampled_1h = f"{domain}_1h"
            self._create_downsampled_bucket(downsampled_1h, RETENTION_CONFIGS["metrics"]["downsampled_1h"])

            # Create 1-day downsampled bucket
            downsampled_1d = f"{domain}_1d"
            self._create_downsampled_bucket(downsampled_1d, RETENTION_CONFIGS["metrics"]["downsampled_1d"])

            # Create downsampling tasks with Flux
            self._create_downsampling_task(
                name=f"downsample_{domain}_to_1h",
                source_bucket=domain,
                target_bucket=downsampled_1h,
                window="1h",
                offset="auto",
                aggregate_fn="mean"
            )

            self._create_downsampling_task(
                name=f"downsample_{domain}_to_1d",
                source_bucket=domain,
                target_bucket=downsampled_1d,
                window="1d",
                offset="auto",
                aggregate_fn="mean"
            )

    def _create_downsampled_bucket(self, bucket_name, retention_hours):
        """Create a bucket for downsampled data.

        Args:
            bucket_name: Name of the bucket
            retention_hours: Retention period in hours
        """
        retention_seconds = int(retention_hours * 3600)

        try:
            self.buckets_api.create_bucket(
                bucket_name=bucket_name,
                org_id=self.org_id,
                retention_rules=[{
                    "type": "expire",
                    "everySeconds": retention_seconds
                }]
            )
            logger.info(f"Created downsampling bucket '{bucket_name}' with retention: {retention_hours} hours")
        except Exception as e:
            if "bucket already exists" in str(e).lower():
                logger.warning(f"Bucket '{bucket_name}' already exists.")
            else:
                logger.error(f"Error creating bucket '{bucket_name}': {e}")

    def _create_downsampling_task(self, name, source_bucket, target_bucket, window, offset, aggregate_fn="mean"):
        """Create a task for downsampling data.

        Args:
            name: Name of the task
            source_bucket: Source bucket name
            target_bucket: Target bucket name
            window: Window for aggregation (e.g., "1h", "1d")
            offset: Offset for the task
            aggregate_fn: Aggregate function to use
        """
        # Create a Flux query for downsampling
        flux_query = f'''
        option task = {{name: "{name}", every: {window}}}

        from(bucket: "{source_bucket}")
          |> range(start: -{window})
          |> filter(fn: (r) => r._measurement != "")
          |> aggregateWindow(every: {window}, fn: {aggregate_fn}, createEmpty: false)
          |> to(bucket: "{target_bucket}")
        '''

        # Create the task
        try:
            self.client.tasks_api().create_task_every(
                name=name,
                flux=flux_query,
                every=window,
                org_id=self.org_id,
                description=f"Downsample data from {source_bucket} to {target_bucket} every {window}"
            )
            logger.info(f"Created task '{name}' for downsampling to {window}")
        except Exception as e:
            logger.error(f"Error creating task '{name}': {e}")

def main():
    parser = argparse.ArgumentParser(description='Configure InfluxDB for the observability stack.')
    parser.add_argument('--url', default=os.environ.get('INFLUXDB_URL', DEFAULT_INFLUXDB_URL),
                        help='InfluxDB URL')
    parser.add_argument('--token', default=os.environ.get('INFLUXDB_TOKEN', DEFAULT_ADMIN_TOKEN),
                        help='InfluxDB admin token')
    parser.add_argument('--org', default=os.environ.get('INFLUXDB_ORG', DEFAULT_ORG),
                        help='InfluxDB organization')
    parser.add_argument('--username', default='observability',
                        help='Username for the dedicated observability user')
    args = parser.parse_args()

    # Check for required environment variables
    required_env_vars = ['INFLUXDB_URL', 'INFLUXDB_TOKEN', 'INFLUXDB_ORG']
    missing_env_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_env_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_env_vars)}")
        sys.exit(1)

    if not args.token:
        logger.error("No admin token provided. Set it with --token or INFLUXDB_TOKEN environment variable.")
        sys.exit(1)

    try:
        # Initialize the configurator
        configurator = InfluxDBConfigurator(args.url, args.token, args.org)

        # Create dedicated user and get token
        user_token = configurator.create_dedicated_user(args.username)
        logger.info(f"Created user token: {user_token}")
        logger.info("Store this token securely for the observability stack to use.")

        # Create buckets
        configurator.create_buckets()

        # Setup continuous queries for downsampling
        configurator.setup_continuous_queries()

        logger.info("InfluxDB configuration complete!")

        # Output the token to a file for retrieval in automation
        token_file = "influxdb_observability_token.txt"
        with open(token_file, "w") as f:
            f.write(user_token)
        logger.info(f"Token saved to {token_file}")

    except Exception as e:
        logger.error(f"Configuration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
