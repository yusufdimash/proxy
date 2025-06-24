#!/usr/bin/env python3
"""
Test script for the Rotating HTTP Proxy Server.
Tests the actual proxy functionality by making requests through the proxy.
"""

import requests
import time
import json
import subprocess
import threading
import signal
import sys
from datetime import datetime


class ProxyServerTester:
    """Test client for the rotating proxy server."""
    
    def __init__(self, proxy_host='localhost', proxy_port=3333):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_url = f"http://{proxy_host}:{proxy_port}"
        self.proxies = {
            'http': self.proxy_url,
            'https': self.proxy_url
        }
    
    def test_http_request(self, url="http://httpbin.org/ip", timeout=10):
        """Test HTTP request through the proxy."""
        try:
            print(f"🔍 Testing HTTP request to {url}")
            response = requests.get(url, proxies=self.proxies, timeout=timeout)
            
            if response.status_code == 200:
                result = response.json()
                external_ip = result.get('origin', 'Unknown')
                print(f"✅ HTTP request successful! External IP: {external_ip}")
                return external_ip
            else:
                print(f"⚠️ HTTP request returned status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ HTTP request failed: {str(e)}")
            return None
    
    def test_https_request(self, url="https://httpbin.org/ip", timeout=10):
        """Test HTTPS request through the proxy."""
        try:
            print(f"🔍 Testing HTTPS request to {url} (HTTPS-only proxy)")
            response = requests.get(url, proxies=self.proxies, timeout=timeout, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                external_ip = result.get('origin', 'Unknown')
                print(f"✅ HTTPS request successful! External IP: {external_ip}")
                return external_ip
            else:
                print(f"⚠️ HTTPS request returned status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ HTTPS request failed: {str(e)}")
            return None
    
    def test_proxy_rotation(self, num_requests=5):
        """Test if proxy actually rotates by making multiple requests."""
        print(f"\n🔄 Testing proxy rotation with {num_requests} requests")
        
        external_ips = []
        for i in range(num_requests):
            print(f"\n   Request #{i+1}:")
            ip = self.test_http_request()
            if ip:
                external_ips.append(ip)
            time.sleep(2)  # Small delay between requests
        
        unique_ips = set(external_ips)
        print(f"\n📊 Rotation Results:")
        print(f"   • Total requests: {len(external_ips)}")
        print(f"   • Unique IPs: {len(unique_ips)}")
        print(f"   • IPs found: {list(unique_ips)}")
        
        if len(unique_ips) > 1:
            print("✅ Proxy rotation is working - got different IPs!")
            return True
        elif len(unique_ips) == 1:
            print("⚠️ All requests used the same IP (limited proxy pool or manual mode)")
            return False
        else:
            print("❌ No successful requests")
            return False
    
    def test_manual_refresh(self):
        """Test manual refresh functionality."""
        print(f"\n🔧 Testing manual refresh functionality")
        
        # Make initial request
        print("   Making initial request...")
        ip1 = self.test_http_request()
        
        if not ip1:
            print("❌ Initial request failed, cannot test refresh")
            return False
        
        time.sleep(1)
        
        # Make second request (should be same IP in manual mode)
        print("   Making second request (should be same IP)...")
        ip2 = self.test_http_request()
        
        if ip1 == ip2:
            print(f"✅ Manual mode working - same IP ({ip1}) returned")
        else:
            print(f"⚠️ Different IPs returned: {ip1} vs {ip2}")
        
        # Trigger refresh
        print("   Triggering manual refresh...")
        try:
            refresh_response = requests.get(
                f"http://{self.proxy_host}:{self.proxy_port}/refresh",
                proxies=self.proxies,
                timeout=10
            )
            
            if refresh_response.status_code == 200:
                print("✅ Manual refresh triggered successfully")
            else:
                print(f"⚠️ Refresh returned status {refresh_response.status_code}")
                
        except Exception as e:
            print(f"❌ Failed to trigger refresh: {str(e)}")
            return False
        
        time.sleep(2)
        
        # Make request after refresh
        print("   Making request after refresh...")
        ip3 = self.test_http_request()
        
        if ip3 and ip3 != ip1:
            print(f"✅ Manual refresh worked - IP changed from {ip1} to {ip3}")
            return True
        elif ip3 == ip1:
            print(f"⚠️ IP didn't change after refresh (might be limited proxy pool)")
            return False
        else:
            print("❌ Request after refresh failed")
            return False
    
    def test_different_websites(self):
        """Test proxy with different websites."""
        print(f"\n🌐 Testing proxy with different websites")
        
        test_urls = [
            "http://httpbin.org/ip",
            "http://ipinfo.io/json",
            "https://httpbin.org/ip",
            "http://httpbin.org/user-agent"
        ]
        
        successful_requests = 0
        
        for url in test_urls:
            try:
                print(f"   Testing {url}...")
                response = requests.get(url, proxies=self.proxies, timeout=15, verify=False)
                
                if response.status_code == 200:
                    print(f"   ✅ Success ({response.status_code})")
                    successful_requests += 1
                else:
                    print(f"   ⚠️ Status {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
        
        print(f"\n📊 Website Test Results:")
        print(f"   • Successful requests: {successful_requests}/{len(test_urls)}")
        
        return successful_requests > 0
    
    def check_proxy_server_running(self):
        """Check if the proxy server is running."""
        try:
            # Try to connect to the proxy port
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.proxy_host, self.proxy_port))
            sock.close()
            
            return result == 0
            
        except Exception:
            return False


def main():
    """Main test function."""
    print("🧪 Testing HTTPS-Only Rotating HTTP Proxy Server")
    print("🔒 This proxy server only uses HTTPS-capable proxies")
    print("=" * 60)
    
    # Get proxy settings
    proxy_host = 'localhost'
    proxy_port = 3333
    
    tester = ProxyServerTester(proxy_host, proxy_port)
    
    # Check if server is running
    print(f"\n1️⃣ Checking if proxy server is running on {proxy_host}:{proxy_port}")
    if not tester.check_proxy_server_running():
        print("❌ Proxy server is not running!")
        print("\n💡 Start the proxy server first:")
        print("   # For rotating mode:")
        print("   python Api/proxy_server.py --mode rotating --port 3333")
        print("\n   # For manual mode:")
        print("   python Api/proxy_server.py --mode manual --port 3333")
        return
    
    print("✅ Proxy server is running!")
    
    # Test basic HTTP request
    print(f"\n2️⃣ Testing Basic HTTP Request")
    http_success = tester.test_http_request()
    
    if not http_success:
        print("❌ Basic HTTP test failed. Check if you have working proxies in your database.")
        print("\n💡 Make sure you have scraped and validated proxies:")
        print("   python Worker/main.py scrape")
        print("   python Worker/main.py validate")
        return
    
    # Test HTTPS request
    print(f"\n3️⃣ Testing HTTPS Request")
    https_success = tester.test_https_request()
    
    # Test rotation (works for both modes)
    print(f"\n4️⃣ Testing Proxy Functionality")
    rotation_success = tester.test_proxy_rotation(3)
    
    # Test with different websites
    print(f"\n5️⃣ Testing Different Websites")
    website_success = tester.test_different_websites()
    
    # Test manual refresh (only relevant for manual mode)
    print(f"\n6️⃣ Testing Manual Refresh (works only in manual mode)")
    refresh_success = tester.test_manual_refresh()
    
    # Summary
    print(f"\n🎉 Test Results Summary")
    print("=" * 30)
    print(f"HTTP Requests:     {'✅ PASS' if http_success else '❌ FAIL'}")
    print(f"HTTPS Requests:    {'✅ PASS' if https_success else '❌ FAIL'}")
    print(f"Proxy Rotation:    {'✅ PASS' if rotation_success else '⚠️  LIMITED'}")
    print(f"Multiple Websites: {'✅ PASS' if website_success else '❌ FAIL'}")
    print(f"Manual Refresh:    {'✅ PASS' if refresh_success else '⚠️  CHECK MODE'}")
    
    print(f"\n💡 Usage Examples:")
    print(f"   # Test with curl:")
    print(f"   curl --proxy {proxy_host}:{proxy_port} http://httpbin.org/ip")
    print(f"   curl --proxy {proxy_host}:{proxy_port} https://httpbin.org/ip")
    
    print(f"\n   # Configure your browser:")
    print(f"   HTTP Proxy:  {proxy_host}:{proxy_port}")
    print(f"   HTTPS Proxy: {proxy_host}:{proxy_port}")
    
    if refresh_success:
        print(f"\n   # Manual refresh (manual mode only):")
        print(f"   curl --proxy {proxy_host}:{proxy_port} http://localhost:{proxy_port}/refresh")


if __name__ == '__main__':
    main() 