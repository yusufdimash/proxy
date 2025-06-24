import threading
import time
import random
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path so we can import from Tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Tools.supabase_client import SupabaseClient


class ProxyManager:
    """
    Manages proxy rotation and health checking for the API server.
    
    Features:
    - Automatic proxy rotation
    - Proxy health monitoring
    - Manual proxy refresh capability
    - Thread-safe operations
    """
    
    def __init__(self):
        self.supabase_client = SupabaseClient()
        self.current_proxy_index = 0
        self.proxy_list = []
        self.last_refresh = None
        self.refresh_lock = threading.Lock()
        self.rotation_lock = threading.Lock()
        self.manual_refresh_needed = False
        
        # Load initial proxy list
        self.refresh_proxy_list()
    
    def refresh_proxy_list(self) -> bool:
        """
        Refresh the proxy list from the database.
        Only loads HTTPS-capable proxies for secure connections.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.refresh_lock:
                # Get working HTTPS-capable proxies, ordered by response time
                proxies = self.supabase_client.get_client().table('proxies') \
                    .select('*') \
                    .eq('is_working', True) \
                    .eq('supports_https', True) \
                    .order('https_response_time_ms', desc=False) \
                    .limit(100) \
                    .execute()
                
                if proxies.data:
                    self.proxy_list = proxies.data
                    self.current_proxy_index = 0
                    self.last_refresh = datetime.now()
                    self.manual_refresh_needed = False
                    print(f"✅ Refreshed HTTPS proxy list: {len(self.proxy_list)} proxies loaded")
                    return True
                else:
                    print("❌ No HTTPS-capable proxies found in database")
                    print("💡 Run proxy validation to identify HTTPS-capable proxies:")
                    print("   python Worker/main.py validate")
                    return False
                        
        except Exception as e:
            print(f"❌ Failed to refresh proxy list: {str(e)}")
            return False
    
    def get_rotating_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Get the next proxy in rotation (always changes).
        If current proxy fails, automatically switch to next.
        
        Returns:
            Optional[Dict]: Proxy information or None if no proxies available
        """
        if not self.proxy_list:
            print("⚠️ No proxies available, attempting refresh...")
            if not self.refresh_proxy_list():
                return None
        
        with self.rotation_lock:
            # Always rotate to the next proxy
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
            current_proxy = self.proxy_list[self.current_proxy_index]
            
            return {
                'id': current_proxy['id'],
                'ip': str(current_proxy['ip']),
                'port': current_proxy['port'],
                'type': current_proxy['type'],
                'country': current_proxy.get('country'),
                'anonymity_level': current_proxy.get('anonymity_level'),
                'response_time_ms': current_proxy.get('https_response_time_ms') or current_proxy.get('response_time_ms'),
                'supports_https': current_proxy.get('supports_https', False),
                'last_checked': current_proxy.get('last_checked'),
                'proxy_url': self._format_proxy_url(current_proxy)
            }
    
    def get_manual_refresh_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Get a proxy that only changes when manual refresh is triggered.
        
        Returns:
            Optional[Dict]: Proxy information or None if no proxies available
        """
        if not self.proxy_list:
            print("⚠️ No proxies available, attempting refresh...")
            if not self.refresh_proxy_list():
                return None
        
        # Check if manual refresh was requested
        if self.manual_refresh_needed:
            print("🔄 Manual refresh triggered - changing proxy...")
            old_proxy_id = self.proxy_list[self.current_proxy_index]['id'] if self.proxy_list else None
            
            # Refresh the proxy list
            if self.refresh_proxy_list():
                # Force change to a different proxy if possible
                if len(self.proxy_list) > 1:
                    # Find a different proxy than the current one
                    for i in range(len(self.proxy_list)):
                        if self.proxy_list[i]['id'] != old_proxy_id:
                            self.current_proxy_index = i
                            break
                    else:
                        # If all proxies have same ID (unlikely), just move to next index
                        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
                
                print(f"✅ Manual refresh complete - switched to proxy {self.current_proxy_index + 1}/{len(self.proxy_list)}")
            else:
                print("❌ Manual refresh failed - keeping current proxy")
            
            # Reset the manual refresh flag
            self.manual_refresh_needed = False
        
        # Return the current proxy (doesn't rotate automatically)
        with self.rotation_lock:
            current_proxy = self.proxy_list[self.current_proxy_index]
            
            return {
                'id': current_proxy['id'],
                'ip': str(current_proxy['ip']),
                'port': current_proxy['port'],
                'type': current_proxy['type'],
                'country': current_proxy.get('country'),
                'anonymity_level': current_proxy.get('anonymity_level'),
                'response_time_ms': current_proxy.get('https_response_time_ms') or current_proxy.get('response_time_ms'),
                'supports_https': current_proxy.get('supports_https', False),
                'last_checked': current_proxy.get('last_checked'),
                'proxy_url': self._format_proxy_url(current_proxy)
            }
    
    def trigger_manual_refresh(self) -> bool:
        """
        Trigger a manual refresh for the manual refresh endpoint.
        The actual refresh happens on the next call to get_manual_refresh_proxy().
        
        Returns:
            bool: True if refresh was triggered successfully
        """
        try:
            print("🔄 Manual refresh requested - will change proxy on next request")
            self.manual_refresh_needed = True
            return True
        except Exception as e:
            print(f"❌ Failed to trigger manual refresh: {str(e)}")
            return False
    
    def mark_proxy_failed(self, proxy_id: str) -> None:
        """
        Mark a proxy as failed and potentially remove it from current rotation.
        
        Args:
            proxy_id (str): The ID of the failed proxy
        """
        try:
            # Update proxy status in database
            self.supabase_client.update_proxy_status(proxy_id, 'failed')
            
            # Remove from current proxy list if present
            with self.rotation_lock:
                self.proxy_list = [p for p in self.proxy_list if p['id'] != proxy_id]
                
                # Adjust current index if needed
                if self.current_proxy_index >= len(self.proxy_list) and self.proxy_list:
                    self.current_proxy_index = 0
                    
            print(f"⚠️ Marked proxy {proxy_id} as failed and removed from rotation")
            
        except Exception as e:
            print(f"❌ Failed to mark proxy as failed: {str(e)}")
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """
        Get current proxy rotation statistics.
        
        Returns:
            Dict: Statistics about the current proxy pool
        """
        try:
            # Get total counts from database
            client = self.supabase_client.get_client()
            
            total_result = client.table('proxies').select('*', count='exact').execute()
            working_result = client.table('proxies').select('*', count='exact').eq('is_working', True).execute()
            https_result = client.table('proxies').select('*', count='exact').eq('supports_https', True).execute()
            
            return {
                'total_proxies_in_db': total_result.count,
                'working_proxies_in_db': working_result.count,
                'https_proxies_in_db': https_result.count,
                'proxies_in_rotation': len(self.proxy_list),
                'current_proxy_index': self.current_proxy_index,
                'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None,
                'manual_refresh_needed': self.manual_refresh_needed
            }
            
        except Exception as e:
            print(f"❌ Failed to get proxy stats: {str(e)}")
            return {
                'error': str(e),
                'proxies_in_rotation': len(self.proxy_list),
                'current_proxy_index': self.current_proxy_index,
                'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None
            }
    
    def _format_proxy_url(self, proxy: Dict[str, Any]) -> str:
        """
        Format proxy information as a URL.
        
        Args:
            proxy: Proxy information dictionary
            
        Returns:
            str: Formatted proxy URL
        """
        proxy_type = proxy.get('type', 'http')
        ip = str(proxy['ip'])
        port = proxy['port']
        
        if proxy_type in ['http', 'https']:
            return f"http://{ip}:{port}"
        elif proxy_type == 'socks4':
            return f"socks4://{ip}:{port}"
        elif proxy_type == 'socks5':
            return f"socks5://{ip}:{port}"
        else:
            return f"{proxy_type}://{ip}:{port}"
    
    def get_https_proxy_count(self) -> int:
        """
        Get the count of available HTTPS-capable proxies in the database.
        
        Returns:
            int: Number of working HTTPS proxies
        """
        try:
            client = self.supabase_client.get_client()
            result = client.table('proxies').select('*', count='exact') \
                .eq('is_working', True) \
                .eq('supports_https', True) \
                .execute()
            return result.count
        except Exception as e:
            print(f"❌ Failed to get HTTPS proxy count: {str(e)}")
            return 0
    
    def health_check(self) -> bool:
        """
        Perform a health check on the proxy manager.
        Ensures we have HTTPS-capable proxies available.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # Check database connection
            if not self.supabase_client.test_connection():
                print("❌ Database connection failed")
                return False
            
            # Check if we have HTTPS proxies available
            https_count = self.get_https_proxy_count()
            if https_count == 0:
                print("❌ No HTTPS-capable proxies found in database")
                print("💡 Run proxy validation to identify HTTPS-capable proxies:")
                print("   python Worker/main.py validate")
                return False
            
            # Check if we have proxies in rotation
            if not self.proxy_list:
                print("⚠️ No proxies loaded, attempting refresh...")
                return self.refresh_proxy_list()
            
            # Check if last refresh was recent (within 1 hour)
            if self.last_refresh and datetime.now() - self.last_refresh > timedelta(hours=1):
                print("⚠️ Proxy list is stale, refreshing...")
                return self.refresh_proxy_list()
            
            return True
            
        except Exception as e:
            print(f"❌ Health check failed: {str(e)}")
            return False 