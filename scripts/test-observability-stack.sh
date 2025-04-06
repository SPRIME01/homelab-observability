#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Testing Observability Stack Components ===${NC}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found. Please install kubectl.${NC}"
    exit 1
fi

# Function to test component availability
test_component() {
    local component=$1
    local namespace=$2
    local type=$3
    local name=$4
    
    echo -ne "Testing $component... "
    if kubectl get $type $name -n $namespace &> /dev/null; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        return 1
    fi
}

# Test Prometheus
test_component "Prometheus" "monitoring" "deployment" "prometheus" || echo -e "${YELLOW}Prometheus deployment not found. Check configuration.${NC}"

# Test AlertManager
test_component "AlertManager" "monitoring" "deployment" "alertmanager" || echo -e "${YELLOW}AlertManager deployment not found. Check configuration.${NC}"

# Test Grafana
test_component "Grafana" "monitoring" "deployment" "grafana" || echo -e "${YELLOW}Grafana deployment not found. Check configuration.${NC}"

# Test Loki
test_component "Loki" "monitoring" "statefulset" "loki" || echo -e "${YELLOW}Loki StatefulSet not found. Check configuration.${NC}"

# Test Correlator
test_component "Correlator" "monitoring" "deployment" "log-metric-correlator" || echo -e "${YELLOW}Correlator deployment not found. Check configuration.${NC}"

echo -e "\n${BLUE}=== Testing Dashboard Access ===${NC}"
# Check Grafana port-forward capability
if kubectl port-forward -n monitoring svc/grafana 3000:3000 >/dev/null 2>&1 & 
then
    PID=$!
    sleep 3
    
    # Test dashboard access
    if curl -s http://localhost:3000/api/health | grep -q "ok"; then
        echo -e "${GREEN}Grafana is accessible${NC}"
        echo -e "Visit http://localhost:3000 to check imported dashboards"
        echo -e "Default login should be admin/admin"
    else
        echo -e "${RED}Failed to access Grafana${NC}"
    fi
    
    kill $PID 2>/dev/null
else
    echo -e "${RED}Failed to port-forward to Grafana service${NC}"
fi

echo -e "\n${BLUE}=== Testing Prometheus API ===${NC}"
# Test Prometheus API
if kubectl port-forward -n monitoring svc/prometheus 9090:9090 >/dev/null 2>&1 &
then
    PID=$!
    sleep 3
    
    if curl -s http://localhost:9090/api/v1/status/config | grep -q "yaml_config"; then
        echo -e "${GREEN}Prometheus API is accessible${NC}"
        echo -e "Visit http://localhost:9090 to check query UI"
    else
        echo -e "${RED}Failed to access Prometheus API${NC}"
    fi
    
    kill $PID 2>/dev/null
else
    echo -e "${RED}Failed to port-forward to Prometheus service${NC}"
fi

echo -e "\n${BLUE}=== Test Complete ===${NC}"
echo -e "For a comprehensive test, please check:"
echo -e "1. Dashboard imports work correctly"
echo -e "2. Alerts are firing as expected"
echo -e "3. Metrics are being collected properly"
echo -e "4. Logs are being stored and are queryable"
echo -e "5. All collectors are reporting metrics"

echo -e "\n${GREEN}If all components are working correctly, mark the corresponding items as complete in the checklist.${NC}"
