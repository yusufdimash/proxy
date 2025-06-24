#!/usr/bin/env python3
"""
Test script specifically for manual refresh functionality.
"""

import requests
import time
import json


def test_manual_refresh(proxy_host='localhost', proxy_port=3333):
    """Test the manual refresh functionality step by step."""
    
    print("🧪 Testing Manual Refresh Functionality")
    print("=" * 50)
    
    proxies = {
        'http': f'http://{proxy_host}:{proxy_port}',
        'https': f'http://{proxy_host}:{proxy_port}'
    }
    
    try:
        # Step 1: Make initial request to get current proxy
        print("\n1️⃣ Getting initial proxy...")
        response1 = requests.get('http://httpbin.org/ip', proxies=proxies, timeout=10)
        if response1.status_code == 200:
            ip1 = response1.json().get('origin', 'Unknown')
            print(f"✅ Initial proxy IP: {ip1}")
        else:
            print(f"❌ Initial request failed with status {response1.status_code}")
            return False
        
        # Step 2: Make second request to confirm it's the same proxy (manual mode)
        print("\n2️⃣ Confirming proxy consistency (should be same IP)...")
        time.sleep(1)
        response2 = requests.get('http://httpbin.org/ip', proxies=proxies, timeout=10)
        if response2.status_code == 200:
            ip2 = response2.json().get('origin', 'Unknown')
            print(f"✅ Second request IP: {ip2}")
            if ip1 == ip2:
                print("✅ Manual mode working - same IP returned")
            else:
                print("⚠️ Different IPs returned - might be in rotating mode?")
        else:
            print(f"❌ Second request failed with status {response2.status_code}")
            return False
        
        # Step 3: Trigger manual refresh
        print("\n3️⃣ Triggering manual refresh...")
        try:
            # Try GET method first
            refresh_response = requests.get(
                f'http://{proxy_host}:{proxy_port}/refresh',
                proxies=proxies,
                timeout=10
            )
            
            if refresh_response.status_code == 200:
                refresh_data = refresh_response.json()
                print(f"✅ Manual refresh successful: {refresh_data['message']}")
            else:
                print(f"⚠️ Refresh returned status {refresh_response.status_code}")
                print(f"Response: {refresh_response.text}")
                
        except Exception as e:
            print(f"❌ Failed to trigger refresh: {str(e)}")
            return False
        
        # Step 4: Wait a moment and make request with new proxy
        print("\n4️⃣ Testing proxy after refresh...")
        time.sleep(2)
        response3 = requests.get('http://httpbin.org/ip', proxies=proxies, timeout=10)
        if response3.status_code == 200:
            ip3 = response3.json().get('origin', 'Unknown')
            print(f"✅ Post-refresh IP: {ip3}")
            
            if ip3 != ip1:
                print(f"🎉 SUCCESS! Manual refresh worked - IP changed from {ip1} to {ip3}")
                return True
            else:
                print(f"⚠️ IP didn't change after refresh ({ip1} -> {ip3})")
                print("   This might happen if:")
                print("   • Only one HTTPS proxy available")
                print("   • Proxy pool is very limited")
                print("   • Same proxy was randomly selected again")
                return False
        else:
            print(f"❌ Post-refresh request failed with status {response3.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")
        return False


def test_refresh_endpoint_directly(proxy_host='localhost', proxy_port=3333):
    """Test the refresh endpoint directly without using it as a proxy."""
    
    print("\n🔧 Testing Refresh Endpoint Directly")
    print("-" * 40)
    
    try:
        # Test with direct connection (not through proxy)
        refresh_url = f'http://{proxy_host}:{proxy_port}/refresh'
        print(f"📡 Calling: {refresh_url}")
        
        response = requests.get(refresh_url, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📄 Response Headers: {dict(response.headers)}")
        print(f"📝 Response Body: {response.text}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ Refresh endpoint working correctly")
                return True
            except json.JSONDecodeError:
                print("⚠️ Response is not valid JSON")
                return False
        else:
            print("❌ Refresh endpoint returned error status")
            return False
            
    except Exception as e:
        print(f"❌ Direct refresh test failed: {str(e)}")
        return False


def main():
    """Main test function."""
    
    print("🚀 Manual Refresh Test Suite")
    print("=" * 60)
    
    proxy_host = 'localhost'
    proxy_port = 3333
    
    # Check if proxy server is running
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((proxy_host, proxy_port))
        sock.close()
        
        if result != 0:
            print(f"❌ Proxy server is not running on {proxy_host}:{proxy_port}")
            print("💡 Start the server first:")
            print(f"   python Api/start_proxy_server.py --mode manual --port {proxy_port}")
            return
            
    except Exception:
        print(f"❌ Cannot check if proxy server is running")
        return
    
    print(f"✅ Proxy server is running on {proxy_host}:{proxy_port}")
    
    # Test 1: Direct refresh endpoint test
    direct_test_result = test_refresh_endpoint_directly(proxy_host, proxy_port)
    
    # Test 2: Full manual refresh flow
    manual_test_result = test_manual_refresh(proxy_host, proxy_port)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    print(f"Direct Refresh Endpoint: {'✅ PASS' if direct_test_result else '❌ FAIL'}")
    print(f"Manual Refresh Flow:     {'✅ PASS' if manual_test_result else '⚠️  LIMITED'}")
    
    if direct_test_result and manual_test_result:
        print("\n🎉 All tests passed! Manual refresh is working correctly.")
    elif direct_test_result and not manual_test_result:
        print("\n⚠️ Refresh endpoint works but proxy might not be changing.")
        print("   This could be due to limited proxy pool or same proxy selection.")
    else:
        print("\n❌ Manual refresh functionality has issues.")
        print("💡 Check server logs for more details.")
    
    print(f"\n💡 Manual usage:")
    print(f"   1. Make requests: curl --proxy {proxy_host}:{proxy_port} http://httpbin.org/ip")
    print(f"   2. Trigger refresh: curl http://{proxy_host}:{proxy_port}/refresh")
    print(f"   3. Verify change: curl --proxy {proxy_host}:{proxy_port} http://httpbin.org/ip")


if __name__ == '__main__':
    main() 