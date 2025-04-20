import os
import sys
import time
import logging
import requests
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Health check endpoints
HEALTH_CHECKS = {
    'api_gateway': 'http://api-gateway/health',
    'rabbitmq': 'http://rabbitmq:15672/api/health',
    'triton': 'http://triton:8000/v2/health/ready',
    'home_assistant': 'http://homeassistant:8123/api/states'
}

@app.route('/health', methods=['GET'])
def health_check():
    results = {}
    for service, url in HEALTH_CHECKS.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                results[service] = 'healthy'
            else:
                results[service] = f'unhealthy (status code: {response.status_code})'
        except requests.RequestException as e:
            results[service] = f'unhealthy (error: {str(e)})'
    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
