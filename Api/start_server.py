#!/usr/bin/env python3
"""
Startup script for the Rotating Proxy API Server.
This script provides an easy way to start the server with common configurations.
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Api.server import run_server

def main():
    """Main startup function."""
    
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description='Start the Rotating Proxy API Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_server.py                          # Start with defaults (0.0.0.0:5000)
  python start_server.py --port 8080              # Start on port 8080
  python start_server.py --host localhost         # Start on localhost only
  python start_server.py --debug                  # Start in debug mode
  python start_server.py --host 0.0.0.0 --port 3000 --debug  # Custom config
        """
    )
    
    parser.add_argument(
        '--host', 
        default=os.getenv('API_HOST', '0.0.0.0'),
        help='Host to bind to (default: 0.0.0.0, env: API_HOST)'
    )
    
    parser.add_argument(
        '--port', 
        type=int, 
        default=int(os.getenv('API_PORT', 5000)),
        help='Port to bind to (default: 5000, env: API_PORT)'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true',
        default=os.getenv('API_DEBUG', 'False').lower() == 'true',
        help='Enable debug mode (default: False, env: API_DEBUG)'
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
        optional_vars = ['API_HOST', 'API_PORT', 'API_DEBUG']
        
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
        
        print(f"\n🚀 Server would start with:")
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   Debug: {args.debug}")
        
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
    
    # Start the server
    try:
        print("🔧 Starting Rotating Proxy API Server...")
        run_server(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Failed to start server: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 