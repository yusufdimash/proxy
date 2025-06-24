#!/usr/bin/env python3
"""
Rotating Proxy API Server

Provides three main endpoints:
1. /api/proxy/rotate - Always rotating proxy (changes every request)
2. /api/proxy/manual - Manual refresh proxy (only changes when refresh endpoint is hit)
3. /api/proxy/refresh - Trigger manual refresh for the manual endpoint

Additional endpoints:
- /api/health - Health check
- /api/stats - Proxy statistics
"""

import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
from datetime import datetime

# Add the parent directory to the path so we can import from other modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Api.proxy_manager import ProxyManager

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global proxy manager instance
proxy_manager = None

def initialize_proxy_manager():
    """Initialize the global proxy manager."""
    global proxy_manager
    if proxy_manager is None:
        print("🚀 Initializing Proxy Manager...")
        proxy_manager = ProxyManager()
        print("✅ Proxy Manager initialized successfully")

# Initialize proxy manager when module is loaded
initialize_proxy_manager()

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint to verify the API server is working.
    
    Returns:
        JSON: Health status and basic information
    """
    try:
        is_healthy = proxy_manager.health_check() if proxy_manager else False
        
        return jsonify({
            'status': 'healthy' if is_healthy else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'proxy_manager_initialized': proxy_manager is not None,
            'message': 'Rotating Proxy API Server is running'
        }), 200 if is_healthy else 503
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'message': 'Health check failed'
        }), 500

@app.route('/api/proxy/rotate', methods=['GET'])
def get_rotating_proxy():
    """
    Get a rotating proxy that always changes on each request.
    If the current proxy fails, it automatically switches to the next one.
    
    Returns:
        JSON: Proxy information including IP, port, type, and additional metadata
    """
    try:
        if not proxy_manager:
            return jsonify({
                'error': 'Proxy manager not initialized',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        proxy = proxy_manager.get_rotating_proxy()
        
        if not proxy:
            return jsonify({
                'error': 'No working proxies available',
                'message': 'Please check proxy database or run scraping job',
                'timestamp': datetime.now().isoformat()
            }), 503
        
        return jsonify({
            'status': 'success',
            'proxy': proxy,
            'endpoint_type': 'rotating',
            'timestamp': datetime.now().isoformat(),
            'message': 'Proxy rotates on every request'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'endpoint_type': 'rotating',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/proxy/manual', methods=['GET'])
def get_manual_refresh_proxy():
    """
    Get a proxy that only changes when the refresh endpoint is triggered.
    This proxy remains the same until /api/proxy/refresh is called.
    
    Returns:
        JSON: Proxy information that remains consistent until manual refresh
    """
    try:
        if not proxy_manager:
            return jsonify({
                'error': 'Proxy manager not initialized',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        proxy = proxy_manager.get_manual_refresh_proxy()
        
        if not proxy:
            return jsonify({
                'error': 'No working proxies available',
                'message': 'Please check proxy database or run scraping job',
                'timestamp': datetime.now().isoformat()
            }), 503
        
        return jsonify({
            'status': 'success',
            'proxy': proxy,
            'endpoint_type': 'manual_refresh',
            'timestamp': datetime.now().isoformat(),
            'message': 'Proxy changes only when refresh endpoint is hit'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'endpoint_type': 'manual_refresh',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/proxy/refresh', methods=['POST'])
def trigger_proxy_refresh():
    """
    Trigger a manual refresh of the proxy list.
    This will update the proxy returned by the /api/proxy/manual endpoint.
    
    Returns:
        JSON: Success status and refresh information
    """
    try:
        if not proxy_manager:
            return jsonify({
                'error': 'Proxy manager not initialized',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        success = proxy_manager.trigger_manual_refresh()
        
        if success:
            # Get the new proxy to return
            new_proxy = proxy_manager.get_manual_refresh_proxy()
            
            return jsonify({
                'status': 'success',
                'message': 'Proxy list refreshed successfully',
                'new_proxy': new_proxy,
                'timestamp': datetime.now().isoformat(),
                'action': 'manual_refresh_triggered'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to refresh proxy list',
                'timestamp': datetime.now().isoformat(),
                'action': 'manual_refresh_failed'
            }), 500
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Manual refresh failed',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_proxy_stats():
    """
    Get statistics about the current proxy pool and rotation status.
    
    Returns:
        JSON: Detailed statistics about proxies and server status
    """
    try:
        if not proxy_manager:
            return jsonify({
                'error': 'Proxy manager not initialized',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        stats = proxy_manager.get_proxy_stats()
        
        return jsonify({
            'status': 'success',
            'stats': stats,
            'timestamp': datetime.now().isoformat(),
            'message': 'Proxy statistics retrieved successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/proxy/report-failed', methods=['POST'])
def report_failed_proxy():
    """
    Report a proxy as failed. This will remove it from rotation and mark it in the database.
    
    Expected JSON payload:
    {
        "proxy_id": "uuid-of-failed-proxy"
    }
    
    Returns:
        JSON: Success status
    """
    try:
        if not proxy_manager:
            return jsonify({
                'error': 'Proxy manager not initialized',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        data = request.get_json()
        if not data or 'proxy_id' not in data:
            return jsonify({
                'error': 'Missing proxy_id in request body',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        proxy_id = data['proxy_id']
        proxy_manager.mark_proxy_failed(proxy_id)
        
        return jsonify({
            'status': 'success',
            'message': f'Proxy {proxy_id} marked as failed and removed from rotation',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/endpoints', methods=['GET'])
def list_endpoints():
    """
    List all available API endpoints with descriptions.
    
    Returns:
        JSON: List of all available endpoints and their descriptions
    """
    endpoints = {
        'endpoints': [
            {
                'path': '/api/health',
                'method': 'GET',
                'description': 'Health check endpoint'
            },
            {
                'path': '/api/proxy/rotate',
                'method': 'GET',
                'description': 'Get a rotating proxy (changes on every request)'
            },
            {
                'path': '/api/proxy/manual',
                'method': 'GET',
                'description': 'Get a manual refresh proxy (only changes when refresh is triggered)'
            },
            {
                'path': '/api/proxy/refresh',
                'method': 'POST',
                'description': 'Trigger manual refresh for the manual proxy endpoint'
            },
            {
                'path': '/api/stats',
                'method': 'GET',
                'description': 'Get proxy statistics and server status'
            },
            {
                'path': '/api/proxy/report-failed',
                'method': 'POST',
                'description': 'Report a proxy as failed (expects {"proxy_id": "uuid"})'
            },
            {
                'path': '/api/endpoints',
                'method': 'GET',
                'description': 'List all available endpoints (this endpoint)'
            }
        ],
        'timestamp': datetime.now().isoformat(),
        'message': 'Rotating Proxy API Server - Available Endpoints'
    }
    
    return jsonify(endpoints), 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with helpful information."""
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'Use /api/endpoints to see available endpoints',
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred',
        'timestamp': datetime.now().isoformat()
    }), 500

def run_server(host='0.0.0.0', port=5000, debug=False):
    """
    Run the Flask server.
    
    Args:
        host (str): Host to bind to
        port (int): Port to bind to
        debug (bool): Enable debug mode
    """
    print(f"""
🚀 Starting Rotating Proxy API Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📡 Server URL: http://{host}:{port}
🔧 Debug Mode: {'Enabled' if debug else 'Disabled'}

📋 Available Endpoints:
   • GET  /api/health           - Health check
   • GET  /api/proxy/rotate     - Always rotating proxy
   • GET  /api/proxy/manual     - Manual refresh proxy
   • POST /api/proxy/refresh    - Trigger manual refresh
   • GET  /api/stats           - Proxy statistics
   • POST /api/proxy/report-failed - Report failed proxy
   • GET  /api/endpoints       - List all endpoints

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    app.run(host=host, port=port, debug=debug, threaded=True)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Rotating Proxy API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port, debug=args.debug) 