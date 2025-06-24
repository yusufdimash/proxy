#!/usr/bin/env python3
"""
Rotating HTTP Proxy Server

This server acts as an HTTP proxy that routes traffic through proxies from the database.
Configure your browser/application to use this server as a proxy.

Three modes:
1. Always rotating - changes proxy for each request
2. Manual refresh - uses same proxy until refresh is triggered  
3. Refresh endpoint - triggers manual refresh via HTTP request
"""

import socket
import threading
import time
import sys
import os
from urllib.parse import urlparse
import json
from datetime import datetime
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Api.proxy_manager import ProxyManager


class ProxyRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler that forwards requests through database proxies."""
    
    def __init__(self, request, client_address, server):
        self.proxy_manager = server.proxy_manager
        self.proxy_mode = server.proxy_mode
        super().__init__(request, client_address, server)
    
    def log_message(self, format, *args):
        """Override to customize logging."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {self.address_string()} - {format % args}")
    
    def do_GET(self):
        """Handle GET requests."""
        # Check for refresh endpoint (allow GET for convenience)
        if self.path == '/refresh' and self.proxy_mode == 'manual':
            self.handle_refresh_request()
            return
        self.handle_request()
    
    def do_POST(self):
        """Handle POST requests."""
        # Check for refresh endpoint
        if self.path == '/refresh' and self.proxy_mode == 'manual':
            self.handle_refresh_request()
            return
        self.handle_request()
    
    def do_PUT(self):
        """Handle PUT requests."""
        self.handle_request()
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        self.handle_request()
    
    def do_HEAD(self):
        """Handle HEAD requests."""
        self.handle_request()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests."""
        self.handle_request()
    
    def do_CONNECT(self):
        """Handle CONNECT requests for HTTPS tunneling."""
        self.handle_connect_request()
    
    def handle_refresh_request(self):
        """Handle refresh endpoint for manual mode."""
        try:
            success = self.proxy_manager.trigger_manual_refresh()
            
            response = {
                'status': 'success' if success else 'error',
                'message': 'Proxy refreshed successfully' if success else 'Failed to refresh proxy',
                'timestamp': datetime.now().isoformat(),
                'mode': self.proxy_mode
            }
            
            self.send_response(200 if success else 500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_error(500, f"Refresh failed: {str(e)}")
    
    def handle_request(self):
        """Handle regular HTTP requests by forwarding through a proxy."""
        try:
            # Get proxy based on mode
            if self.proxy_mode == 'rotating':
                proxy_info = self.proxy_manager.get_rotating_proxy()
            else:  # manual mode
                proxy_info = self.proxy_manager.get_manual_refresh_proxy()
            
            if not proxy_info:
                self.send_error(503, "No working proxies available")
                return
            
            # Forward the request through the selected proxy
            self.forward_request(proxy_info)
            
        except Exception as e:
            print(f"❌ Error handling request: {str(e)}")
            self.send_error(500, f"Proxy error: {str(e)}")
    
    def handle_connect_request(self):
        """Handle HTTPS CONNECT requests for tunneling."""
        try:
            # Get proxy based on mode
            if self.proxy_mode == 'rotating':
                proxy_info = self.proxy_manager.get_rotating_proxy()
            else:  # manual mode
                proxy_info = self.proxy_manager.get_manual_refresh_proxy()
            
            if not proxy_info:
                self.send_error(503, "No working proxies available")
                return
            
            # Parse the target host and port
            host_port = self.path.split(':')
            if len(host_port) != 2:
                self.send_error(400, "Invalid CONNECT request")
                return
            
            target_host = host_port[0]
            target_port = int(host_port[1])
            
            # Connect through the proxy
            self.tunnel_through_proxy(proxy_info, target_host, target_port)
            
        except Exception as e:
            print(f"❌ Error handling CONNECT: {str(e)}")
            self.send_error(500, f"CONNECT error: {str(e)}")
    
    def forward_request(self, proxy_info):
        """Forward HTTP request through the selected proxy."""
        try:
            proxy_url = proxy_info['proxy_url']
            
            # Build the full URL
            if self.path.startswith('http'):
                url = self.path
            else:
                # Relative URL, need to construct full URL
                host = self.headers.get('Host', 'localhost')
                scheme = 'https' if self.command == 'CONNECT' else 'http'
                url = f"{scheme}://{host}{self.path}"
            
            # Read request body if present
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # Setup proxy
            proxy_handler = urllib.request.ProxyHandler({
                'http': proxy_url,
                'https': proxy_url
            })
            opener = urllib.request.build_opener(proxy_handler)
            
            # Create request
            req = urllib.request.Request(url, data=body, method=self.command)
            
            # Copy headers (excluding some that urllib2 handles)
            skip_headers = ['host', 'content-length', 'connection', 'proxy-connection']
            for header, value in self.headers.items():
                if header.lower() not in skip_headers:
                    req.add_header(header, value)
            
            # Make the request
            response = opener.open(req, timeout=30)
            
            # Send response back to client
            self.send_response(response.getcode())
            
            # Copy response headers
            for header, value in response.headers.items():
                if header.lower() not in ['connection', 'transfer-encoding']:
                    self.send_header(header, value)
            self.end_headers()
            
            # Copy response body
            while True:
                data = response.read(8192)
                if not data:
                    break
                self.wfile.write(data)
            
            print(f"✅ Forwarded {self.command} {url} via {proxy_info['ip']}:{proxy_info['port']}")
            
        except Exception as e:
            print(f"❌ Failed to forward request via {proxy_info['ip']}:{proxy_info['port']}: {str(e)}")
            # Mark proxy as failed and try to send error response
            self.proxy_manager.mark_proxy_failed(proxy_info['id'])
            
            # Try to send error response (only if no response has been started)
            try:
                self.send_error(502, f"Proxy forwarding failed: {str(e)}")
            except Exception as send_error_exception:
                print(f"⚠️ Could not send error response: {send_error_exception}")
    
    def tunnel_through_proxy(self, proxy_info, target_host, target_port):
        """Create HTTPS tunnel through the selected proxy."""
        try:
            # Connect to the proxy
            proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_socket.settimeout(30)
            proxy_socket.connect((proxy_info['ip'], proxy_info['port']))
            
            # Send CONNECT request to proxy
            connect_request = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
            connect_request += f"Host: {target_host}:{target_port}\r\n"
            connect_request += "Proxy-Connection: keep-alive\r\n\r\n"
            
            proxy_socket.send(connect_request.encode())
            
            # Read proxy response
            response = proxy_socket.recv(4096).decode()
            if "200" not in response.split('\n')[0]:
                raise Exception(f"Proxy CONNECT failed: {response.split(chr(10))[0]}")
            
            # Send 200 Connection Established to client
            self.send_response(200, "Connection Established")
            self.end_headers()
            
            # Start tunneling data between client and proxy
            client_socket = self.request
            
            def forward_data(source, destination, direction):
                try:
                    while True:
                        data = source.recv(4096)
                        if not data:
                            break
                        destination.send(data)
                except:
                    pass
                finally:
                    try:
                        source.close()
                        destination.close()
                    except:
                        pass
            
            # Start forwarding in both directions
            client_to_proxy = threading.Thread(
                target=forward_data, 
                args=(client_socket, proxy_socket, "client->proxy")
            )
            proxy_to_client = threading.Thread(
                target=forward_data, 
                args=(proxy_socket, client_socket, "proxy->client")
            )
            
            client_to_proxy.daemon = True
            proxy_to_client.daemon = True
            
            client_to_proxy.start()
            proxy_to_client.start()
            
            # Wait for either thread to finish
            client_to_proxy.join()
            proxy_to_client.join()
            
            print(f"✅ HTTPS tunnel established through {proxy_info['ip']}:{proxy_info['port']}")
            
        except Exception as e:
            print(f"❌ Failed to tunnel through {proxy_info['ip']}:{proxy_info['port']}: {str(e)}")
            # Mark proxy as failed
            self.proxy_manager.mark_proxy_failed(proxy_info['id'])
            
            # Try to send error response
            try:
                self.send_error(502, f"Tunnel failed: {str(e)}")
            except Exception as send_error_exception:
                print(f"⚠️ Could not send error response: {send_error_exception}")


class RotatingProxyServer(HTTPServer):
    """HTTP Proxy Server that rotates through database proxies."""
    
    def __init__(self, host='localhost', port=3333, mode='rotating'):
        self.proxy_manager = ProxyManager()
        self.proxy_mode = mode  # 'rotating' or 'manual'
        
        print(f"🚀 Initializing HTTPS-Only Rotating Proxy Server...")
        print(f"   Mode: {mode}")
        print(f"   Host: {host}")
        print(f"   Port: {port}")
        print(f"   HTTPS Only: Yes (only uses HTTPS-capable proxies)")
        
        # Check if we have HTTPS proxies available
        https_count = self.proxy_manager.get_https_proxy_count()
        print(f"   HTTPS Proxies Available: {https_count}")
        
        if https_count == 0:
            print("\n❌ No HTTPS-capable proxies found in database!")
            print("💡 Please run proxy validation to identify HTTPS-capable proxies:")
            print("   python Worker/main.py validate")
            print("   python Worker/main.py scrape  # if you need more proxies")
            raise Exception("No HTTPS-capable proxies available")
        
        super().__init__((host, port), ProxyRequestHandler)
        
        print(f"✅ HTTPS-Only Proxy Server initialized successfully")
    
    def serve_forever(self):
        """Start serving requests."""
        print(f"""
🌐 HTTPS-Only Rotating Proxy Server Started
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📡 Proxy Server: {self.server_address[0]}:{self.server_address[1]}
🔄 Mode: {self.proxy_mode}
🔒 HTTPS Only: Yes (only uses HTTPS-capable proxies)

📋 Usage Instructions:

🌐 Browser Configuration:
   • HTTP Proxy: {self.server_address[0]}:{self.server_address[1]}
   • HTTPS Proxy: {self.server_address[0]}:{self.server_address[1]}
   
🖥️  Curl Usage:
   • curl --proxy {self.server_address[0]}:{self.server_address[1]} http://httpbin.org/ip
   • curl --proxy {self.server_address[0]}:{self.server_address[1]} https://httpbin.org/ip

🔄 Mode Specific Features:
""")
        
        if self.proxy_mode == 'rotating':
            print("   • Rotating Mode: Proxy changes for each request automatically")
        else:
            print("   • Manual Mode: Proxy stays same until refresh")
            print(f"   • Refresh: curl --proxy {self.server_address[0]}:{self.server_address[1]} http://localhost:{self.server_address[1]}/refresh")
        
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🔍 Press Ctrl+C to stop the server")
        print()
        
        try:
            super().serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Proxy server stopped")


def main():
    """Main function to start the proxy server."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Rotating HTTP Proxy Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python proxy_server.py                          # Start rotating mode on localhost:3333
  python proxy_server.py --mode manual            # Start manual refresh mode
  python proxy_server.py --host 0.0.0.0 --port 8080  # Custom host/port
  python proxy_server.py --mode manual --port 3333    # Manual mode on port 3333

Usage with curl:
  curl --proxy localhost:3333 http://httpbin.org/ip
  curl --proxy localhost:3333 https://httpbin.org/ip
  
For manual mode refresh:
  curl --proxy localhost:3333 http://localhost:3333/refresh
        """
    )
    
    parser.add_argument(
        '--host', 
        default='localhost',
        help='Host to bind to (default: localhost)'
    )
    
    parser.add_argument(
        '--port', 
        type=int, 
        default=3333,
        help='Port to bind to (default: 3333)'
    )
    
    parser.add_argument(
        '--mode',
        choices=['rotating', 'manual'],
        default='rotating',
        help='Proxy mode: rotating (changes each request) or manual (manual refresh)'
    )
    
    args = parser.parse_args()
    
    try:
        # Create and start the proxy server
        server = RotatingProxyServer(
            host=args.host,
            port=args.port,
            mode=args.mode
        )
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Failed to start server: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main() 