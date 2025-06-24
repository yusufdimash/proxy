#!/usr/bin/env python3
"""
Test script for the Rotating Proxy API Server.
Demonstrates all three main endpoints and their functionality.
"""

import requests
import time
import json
from typing import Dict, Any, Optional

class ProxyAPIClient:
    """Client for testing the Rotating Proxy API."""
    
    def __init__(self, base_url: str = "http://localhost:3333"):
        self.base_url = base_url.rstrip('/')
        
    def health_check(self) -> Dict[str, Any]:
        """Check API server health."""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            return response.json()
        except Exception as e:
            return {"error": str(e), "status": "connection_failed"}
    
    def get_rotating_proxy(self) -> Optional[Dict[str, Any]]:
        """Get a rotating proxy (changes each time)."""
        try:
            response = requests.get(f"{self.base_url}/api/proxy/rotate", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting rotating proxy: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception getting rotating proxy: {e}")
            return None
    
    def get_manual_proxy(self) -> Optional[Dict[str, Any]]:
        """Get a manual refresh proxy (stays same until refresh)."""
        try:
            response = requests.get(f"{self.base_url}/api/proxy/manual", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting manual proxy: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception getting manual proxy: {e}")
            return None
    
    def trigger_refresh(self) -> bool:
        """Trigger manual refresh."""
        try:
            response = requests.post(f"{self.base_url}/api/proxy/refresh", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Exception triggering refresh: {e}")
            return False
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """Get proxy statistics."""
        try:
            response = requests.get(f"{self.base_url}/api/stats", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting stats: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception getting stats: {e}")
            return None
    
    def list_endpoints(self) -> Optional[Dict[str, Any]]:
        """List all available endpoints."""
        try:
            response = requests.get(f"{self.base_url}/api/endpoints", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error listing endpoints: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception listing endpoints: {e}")
            return None

def print_proxy_info(proxy_data: Dict[str, Any], label: str):
    """Print formatted proxy information."""
    if proxy_data and proxy_data.get('status') == 'success':
        proxy = proxy_data['proxy']
        print(f"🔗 {label}:")
        print(f"   • IP: {proxy['ip']}:{proxy['port']}")
        print(f"   • Type: {proxy['type']}")
        print(f"   • Country: {proxy.get('country', 'Unknown')}")
        print(f"   • Anonymity: {proxy.get('anonymity_level', 'Unknown')}")
        print(f"   • Response Time: {proxy.get('response_time_ms', 'Unknown')}ms")
        print(f"   • Proxy URL: {proxy['proxy_url']}")
        print(f"   • ID: {proxy['id']}")
        return proxy['id']
    else:
        print(f"❌ {label}: Failed to get proxy")
        if proxy_data:
            print(f"   Error: {proxy_data.get('error', 'Unknown error')}")
        return None

def main():
    """Main test function."""
    print("🧪 Testing Rotating Proxy API Server")
    print("=" * 50)
    
    client = ProxyAPIClient()
    
    # 1. Health Check
    print("\n1️⃣ Health Check")
    health = client.health_check()
    if health.get('status') == 'healthy':
        print("✅ Server is healthy")
    else:
        print("❌ Server is not healthy")
        print(f"   Status: {health}")
        print("\n💡 Make sure the server is running:")
        print("   python Api/start_server.py")
        return
    
    # 2. List available endpoints
    print("\n2️⃣ Available Endpoints")
    endpoints = client.list_endpoints()
    if endpoints:
        print("📋 Available endpoints:")
        for endpoint in endpoints.get('endpoints', []):
            print(f"   • {endpoint['method']:4} {endpoint['path']:25} - {endpoint['description']}")
    
    # 3. Get statistics
    print("\n3️⃣ Proxy Statistics")
    stats = client.get_stats()
    if stats and stats.get('status') == 'success':
        stats_data = stats['stats']
        print("📊 Current proxy pool:")
        print(f"   • Total proxies in DB: {stats_data.get('total_proxies_in_db', 'Unknown')}")
        print(f"   • Working proxies in DB: {stats_data.get('working_proxies_in_db', 'Unknown')}")
        print(f"   • HTTPS proxies in DB: {stats_data.get('https_proxies_in_db', 'Unknown')}")
        print(f"   • Proxies in rotation: {stats_data.get('proxies_in_rotation', 'Unknown')}")
        print(f"   • Last refresh: {stats_data.get('last_refresh', 'Never')}")
        
        if stats_data.get('proxies_in_rotation', 0) == 0:
            print("\n⚠️ No proxies in rotation! Run the proxy scraper first:")
            print("   python Worker/main.py scrape")
            return
    
    # 4. Test rotating proxy (should change each time)
    print("\n4️⃣ Testing Rotating Proxy (changes each request)")
    print("Getting 3 rotating proxies to show they change:")
    
    rotating_ids = []
    for i in range(3):
        print(f"\n   Request #{i+1}:")
        proxy_data = client.get_rotating_proxy()
        proxy_id = print_proxy_info(proxy_data, f"Rotating Proxy #{i+1}")
        if proxy_id:
            rotating_ids.append(proxy_id)
        time.sleep(1)  # Small delay between requests
    
    if len(set(rotating_ids)) > 1:
        print("✅ Rotating proxy is working - got different proxies!")
    else:
        print("⚠️ Rotating proxy returned same proxy (might be limited proxy pool)")
    
    # 5. Test manual refresh proxy (should stay same until refresh)
    print("\n5️⃣ Testing Manual Refresh Proxy")
    print("Getting manual proxy twice (should be same):")
    
    manual_proxy_1 = client.get_manual_proxy()
    id1 = print_proxy_info(manual_proxy_1, "Manual Proxy #1")
    
    time.sleep(1)
    
    manual_proxy_2 = client.get_manual_proxy()
    id2 = print_proxy_info(manual_proxy_2, "Manual Proxy #2")
    
    if id1 and id2 and id1 == id2:
        print("✅ Manual proxy is consistent - same proxy returned!")
    else:
        print("⚠️ Manual proxy changed unexpectedly")
    
    # 6. Test manual refresh trigger
    print("\n6️⃣ Testing Manual Refresh Trigger")
    print("Triggering refresh and getting new manual proxy:")
    
    if client.trigger_refresh():
        print("✅ Manual refresh triggered successfully")
        
        time.sleep(1)
        
        manual_proxy_3 = client.get_manual_proxy()
        id3 = print_proxy_info(manual_proxy_3, "Manual Proxy After Refresh")
        
        if id3 and id1 and id3 != id1:
            print("✅ Manual refresh worked - proxy changed!")
        else:
            print("⚠️ Manual refresh might not have changed the proxy")
    else:
        print("❌ Failed to trigger manual refresh")
    
    # 7. Test practical usage
    print("\n7️⃣ Practical Usage Example")
    print("Using a proxy to make an actual HTTP request:")
    
    proxy_data = client.get_rotating_proxy()
    if proxy_data and proxy_data.get('status') == 'success':
        proxy = proxy_data['proxy']
        proxy_url = proxy['proxy_url']
        
        print(f"   Using proxy: {proxy_url}")
        
        try:
            # Test the proxy with a real request
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            response = requests.get(
                'http://httpbin.org/ip', 
                proxies=proxies, 
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Proxy works! External IP: {result.get('origin', 'Unknown')}")
            else:
                print(f"⚠️ Proxy request failed with status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Proxy test failed: {e}")
            print("💡 This might be normal if the proxy is not actually working")
    
    print("\n🎉 API Testing Complete!")
    print("\n💡 Usage Tips:")
    print("   • Use /api/proxy/rotate for always-changing proxies")
    print("   • Use /api/proxy/manual for consistent proxy until refresh")
    print("   • Use /api/proxy/refresh to update the manual proxy")
    print("   • Check /api/stats for proxy pool information")
    print("   • Report failed proxies with /api/proxy/report-failed")

if __name__ == '__main__':
    main() 