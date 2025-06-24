#!/usr/bin/env python3
"""
Startup script for the Rotating HTTP Proxy Server.
This script provides an easy way to start the actual proxy server.
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Api.proxy_server import main as start_proxy_server

def main():
    """Main startup function."""
    
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description='Start the HTTPS-Only Rotating HTTP Proxy Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🔒 HTTPS-ONLY PROXY SERVER: Only uses proxies that support HTTPS connections!

Examples:
  python start_proxy_server.py                           # Start rotating mode on localhost:3333
  python start_proxy_server.py --mode manual             # Start manual refresh mode
  python start_proxy_server.py --host 0.0.0.0 --port 8080  # Custom host/port
  python start_proxy_server.py --mode manual --port 3333    # Manual mode on port 3333

How to use the proxy server:
  
  🌐 Browser Configuration:
     Set HTTP Proxy:  localhost:3333
     Set HTTPS Proxy: localhost:3333
  
  🖥️  Curl Usage:
     curl --proxy localhost:3333 http://httpbin.org/ip
     curl --proxy localhost:3333 https://httpbin.org/ip
  
  🔧 Manual Refresh (manual mode only):
     curl --proxy localhost:3333 http://localhost:3333/refresh

Three Server Modes:
  1. ROTATING MODE: Proxy changes for each request automatically (HTTPS-capable only)
  2. MANUAL MODE: Proxy stays same until refresh (HTTPS-capable only)
  3. Refresh endpoint only works in manual mode

Prerequisites:
  ⚠️  Requires HTTPS-capable proxies in database!
  💡 Run validation if you get "no HTTPS proxies" error:
     python Worker/main.py validate
        """
    )
    
    parser.add_argument(
        '--host', 
        default=os.getenv('PROXY_HOST', 'localhost'),
        help='Host to bind to (default: localhost, env: PROXY_HOST)'
    )
    
    parser.add_argument(
        '--port', 
        type=int, 
        default=int(os.getenv('PROXY_PORT', 3333)),
        help='Port to bind to (default: 3333, env: PROXY_PORT)'
    )
    
    parser.add_argument(
        '--mode',
        choices=['rotating', 'manual'],
        default=os.getenv('PROXY_MODE', 'rotating'),
        help='Proxy mode: rotating (changes each request) or manual (manual refresh) (default: rotating, env: PROXY_MODE)'
    )
    
    parser.add_argument(
        '--check-env',
        action='store_true',
        help='Check environment variables and exit'
    )
    
    args = parser.parse_args()
    
    if args.check_env:
        print("🔍 Checking environment variables...")
        
        required_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY']
        optional_vars = ['PROXY_HOST', 'PROXY_PORT', 'PROXY_MODE']
        
        print("\n📋 Required environment variables:")
        for var in required_vars:
            value = os.getenv(var)
            status = "✅ SET" if value else "❌ MISSING"
            print(f"   {var}: {status}")
            if value and var == 'SUPABASE_URL':
                print(f"      URL: {value[:50]}...")
        
        print("\n⚙️ Optional environment variables:")
        for var in optional_vars:
            value = os.getenv(var)
            status = f"✅ {value}" if value else "⚪ NOT SET"
            print(f"   {var}: {status}")
        
        print(f"\n🚀 Proxy server would start with:")
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   Mode: {args.mode}")
        
        print(f"\n💡 Usage after starting:")
        print(f"   curl --proxy {args.host}:{args.port} http://httpbin.org/ip")
        
        return
    
    # Validate required environment variables
    required_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   • {var}")
        print("\n💡 Please set these variables in your .env file or environment")
        print("   You can copy env.template to .env and fill in your values")
        sys.exit(1)
    
    # Override sys.argv for the proxy server main function
    sys.argv = [
        'proxy_server.py',
        '--host', args.host,
        '--port', str(args.port),
        '--mode', args.mode
    ]
    
    # Start the proxy server
    try:
        print("🔧 Starting Rotating HTTP Proxy Server...")
        start_proxy_server()
    except KeyboardInterrupt:
        print("\n\n🛑 Proxy server stopped by user")
    except Exception as e:
        print(f"\n❌ Failed to start proxy server: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 