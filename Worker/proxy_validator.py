import requests
import time
import asyncio
import aiohttp
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import socket
import socks
import sys
import os

# Add the parent directory to the path so we can import from Tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Tools.supabase_client import SupabaseClient

class ProxyValidator:
    """
    Comprehensive proxy validator that tests proxy functionality
    using multiple methods and target websites, including HTTPS support testing.
    """
    
    def __init__(self, timeout: int = 10, max_workers: int = 50):
        """
        Initialize the proxy validator.
        
        Args:
            timeout (int): Request timeout in seconds
            max_workers (int): Maximum number of concurrent validation threads
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.supabase_client = SupabaseClient()
        
        # Test URLs to validate proxies against
        self.http_test_urls = [
            'http://httpbin.org/ip',
            'http://ip-api.com/json'
        ]
        
        self.https_test_urls = [
            'https://api.ipify.org?format=json',
            'https://jsonip.com',
            'https://httpbin.org/ip'
        ]
        
        # Headers to use for validation requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
    def validate_http_connectivity(self, proxy: Dict) -> Tuple[bool, float, str]:
        """
        Test HTTP connectivity through the proxy.
        
        Args:
            proxy (Dict): Proxy information dictionary
            
        Returns:
            Tuple[bool, float, str]: (is_working, response_time_ms, error_message)
        """
        proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
        if proxy['type'] == 'https':
            proxy_url = f"https://{proxy['ip']}:{proxy['port']}"
        
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        for test_url in self.http_test_urls:
            try:
                start_time = time.time()
                
                response = requests.get(
                    test_url,
                    proxies=proxies,
                    timeout=self.timeout,
                    headers=self.headers,
                    verify=False
                )
                
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                if response.status_code == 200:
                    # Verify that we're actually using the proxy
                    try:
                        response_data = response.json()
                        returned_ip = response_data.get('origin') or response_data.get('ip') or response_data.get('query')
                        
                        if returned_ip and proxy['ip'] in returned_ip:
                            return True, response_time_ms, "HTTP Success"
                        else:
                            # Try next URL before failing
                            continue
                    except:
                        # If we can't parse JSON, consider it working if status is 200
                        return True, response_time_ms, "HTTP Success (no IP verification)"
                else:
                    continue  # Try next URL
                    
            except requests.exceptions.ProxyError:
                continue  # Try next URL
            except requests.exceptions.ConnectTimeout:
                continue  # Try next URL
            except requests.exceptions.ReadTimeout:
                continue  # Try next URL
            except requests.exceptions.ConnectionError:
                continue  # Try next URL
            except Exception:
                continue  # Try next URL
        
        return False, 0, "HTTP connection failed"
    
    def validate_https_connectivity(self, proxy: Dict) -> Tuple[bool, float, str]:
        """
        Test HTTPS connectivity through the proxy.
        
        Args:
            proxy (Dict): Proxy information dictionary
            
        Returns:
            Tuple[bool, float, str]: (supports_https, response_time_ms, error_message)
        """
        proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
        if proxy['type'] == 'https':
            proxy_url = f"https://{proxy['ip']}:{proxy['port']}"
        
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        for test_url in self.https_test_urls:
            try:
                start_time = time.time()
                
                response = requests.get(
                    test_url,
                    proxies=proxies,
                    timeout=self.timeout,
                    headers=self.headers,
                    verify=False  # Skip SSL verification for testing
                )
                
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                if response.status_code == 200:
                    # Verify that we're actually using the proxy
                    try:
                        response_data = response.json()
                        returned_ip = response_data.get('origin') or response_data.get('ip') or response_data.get('query')
                        
                        if returned_ip and proxy['ip'] in returned_ip:
                            return True, response_time_ms, "HTTPS Success"
                        else:
                            # Try next URL before failing
                            continue
                    except:
                        # If we can't parse JSON, consider it working if status is 200
                        return True, response_time_ms, "HTTPS Success (no IP verification)"
                else:
                    continue  # Try next URL
                    
            except requests.exceptions.SSLError:
                continue  # Try next URL
            except requests.exceptions.ProxyError:
                continue  # Try next URL
            except requests.exceptions.ConnectTimeout:
                continue  # Try next URL
            except requests.exceptions.ReadTimeout:
                continue  # Try next URL
            except requests.exceptions.ConnectionError:
                continue  # Try next URL
            except Exception:
                continue  # Try next URL
        
        return False, 0, "HTTPS connection failed"

    def validate_http_proxy(self, proxy: Dict, test_url: str = None) -> Tuple[bool, float, str]:
        """
        Validate HTTP/HTTPS proxy using requests (legacy method for backward compatibility).
        
        Args:
            proxy (Dict): Proxy information dictionary
            test_url (str): URL to test against (optional)
            
        Returns:
            Tuple[bool, float, str]: (is_working, response_time_ms, error_message)
        """
        # Use the new HTTP connectivity test
        return self.validate_http_connectivity(proxy)
    
    def validate_socks_proxy(self, proxy: Dict) -> Tuple[bool, float, str]:
        """
        Validate SOCKS4/5 proxy using socket connection.
        
        Args:
            proxy (Dict): Proxy information dictionary
            
        Returns:
            Tuple[bool, float, str]: (is_working, response_time_ms, error_message)
        """
        # Store original socket for restoration
        original_socket = socket.socket
        
        try:
            start_time = time.time()
            
            # Create a SOCKS socket directly without modifying global socket
            if proxy['type'] == 'socks4':
                socks_socket = socks.socksocket()
                socks_socket.set_proxy(socks.SOCKS4, proxy['ip'], proxy['port'])
            elif proxy['type'] == 'socks5':
                socks_socket = socks.socksocket()
                socks_socket.set_proxy(socks.SOCKS5, proxy['ip'], proxy['port'])
            else:
                return False, 0, "Unsupported SOCKS type"
            
            socks_socket.settimeout(self.timeout)
            
            # Test connection to a reliable server
            result = socks_socket.connect_ex(('8.8.8.8', 53))  # Google DNS
            socks_socket.close()
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            if result == 0:
                return True, response_time_ms, "Success"
            else:
                return False, response_time_ms, "Connection failed"
                
        except Exception as e:
            return False, 0, f"SOCKS error: {str(e)}"
        finally:
            # Restore original socket (not needed with direct approach, but good practice)
            socket.socket = original_socket
    
    def validate_single_proxy(self, proxy: Dict) -> Dict:
        """
        Validate a single proxy and return comprehensive results including HTTPS support.
        
        Args:
            proxy (Dict): Proxy information dictionary
            
        Returns:
            Dict: Comprehensive validation results
        """
        print(f"🔍 Testing {proxy['ip']}:{proxy['port']} ({proxy['type']})")
        
        # Initialize results
        result = {
            'proxy_id': proxy.get('id'),
            'ip': proxy['ip'],
            'port': proxy['port'],
            'type': proxy['type'],
            'is_working': False,
            'response_time_ms': None,
            'error_message': None,
            'supports_https': False,
            'https_response_time_ms': None,
            'https_error_message': None,
            'check_time': datetime.now().isoformat(),
            'check_method': 'requests' if proxy['type'] in ['http', 'https'] else 'socket'
        }
        
        if proxy['type'] in ['http', 'https']:
            # Test HTTP connectivity
            http_working, http_time, http_error = self.validate_http_connectivity(proxy)
            result['is_working'] = http_working
            result['response_time_ms'] = round(http_time) if http_time else None
            result['error_message'] = http_error if not http_working else None
            
            # Test HTTPS connectivity (only if HTTP works or if we want to test anyway)
            https_working, https_time, https_error = self.validate_https_connectivity(proxy)
            result['supports_https'] = https_working
            result['https_response_time_ms'] = round(https_time) if https_time else None
            result['https_error_message'] = https_error if not https_working else None
            
        elif proxy['type'] in ['socks4', 'socks5']:
            # For SOCKS proxies, test basic connectivity
            socks_working, socks_time, socks_error = self.validate_socks_proxy(proxy)
            result['is_working'] = socks_working
            result['response_time_ms'] = round(socks_time) if socks_time else None
            result['error_message'] = socks_error if not socks_working else None
            
            # SOCKS proxies can typically handle HTTPS, but we'll test it
            if socks_working:
                https_working, https_time, https_error = self.validate_https_connectivity(proxy)
                result['supports_https'] = https_working
                result['https_response_time_ms'] = round(https_time) if https_time else None
                result['https_error_message'] = https_error if not https_working else None
        else:
            result['error_message'] = "Unsupported proxy type"
        
        # Print results
        status_icon = "✅" if result['is_working'] else "❌"
        https_icon = "🔒" if result['supports_https'] else "🚫"
        
        if result['is_working']:
            print(f"{status_icon} {proxy['ip']}:{proxy['port']} - HTTP: ✅ ({result['response_time_ms']}ms), HTTPS: {https_icon}")
        else:
            print(f"{status_icon} {proxy['ip']}:{proxy['port']} - {result['error_message']}")
        
        return result
    
    def validate_proxy_list(self, proxies: List[Dict]) -> List[Dict]:
        """
        Validate a list of proxies using multithreading.
        
        Args:
            proxies (List[Dict]): List of proxy dictionaries
            
        Returns:
            List[Dict]: List of validation results
        """
        print(f"🚀 Starting validation of {len(proxies)} proxies...")
        start_time = time.time()
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all validation tasks
            future_to_proxy = {
                executor.submit(self.validate_single_proxy, proxy): proxy 
                for proxy in proxies
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_proxy):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    proxy = future_to_proxy[future]
                    print(f"❌ Validation failed for {proxy['ip']}:{proxy['port']}: {str(e)}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        working_count = sum(1 for r in results if r['is_working'])
        
        print(f"\n📊 Validation Complete!")
        print(f"   • Total tested: {len(results)}")
        print(f"   • Working proxies: {working_count}")
        print(f"   • Success rate: {(working_count/len(results)*100):.1f}%")
        print(f"   • Duration: {duration:.1f} seconds")
        
        return results
    
    def update_database_with_results(self, results: List[Dict]) -> int:
        """
        Update database with validation results including HTTPS support.
        
        Args:
            results (List[Dict]): List of validation results
            
        Returns:
            int: Number of records updated
        """
        updated_count = 0
        
        for result in results:
            try:
                if result.get('proxy_id'):
                    client = self.supabase_client.get_client()
                    
                    # Update existing proxy in database with comprehensive data
                    status = 'active' if result['is_working'] else 'inactive'
                    current_time = datetime.now().isoformat()
                    
                    update_data = {
                        'status': status,
                        'is_working': result['is_working'],
                        'last_checked': current_time,
                        'response_time_ms': result['response_time_ms']
                    }
                    
                    # Update last_working timestamp if proxy is working
                    if result['is_working']:
                        update_data['last_working'] = current_time
                        
                    # Add HTTP connectivity information
                    update_data['supports_http'] = result['is_working']  # If it's working, it supports HTTP
                    if result['is_working']:
                        update_data['http_response_time_ms'] = result['response_time_ms']
                        update_data['last_http_check'] = current_time
                        update_data['last_http_working'] = current_time
                    
                    # Add HTTPS support information if available
                    if 'supports_https' in result:
                        update_data['supports_https'] = result['supports_https']
                        update_data['last_https_check'] = current_time
                        if result['supports_https']:
                            if result.get('https_response_time_ms'):
                                update_data['https_response_time_ms'] = result['https_response_time_ms']
                            update_data['last_https_working'] = current_time
                    
                    try:
                        # Try to update with HTTPS fields
                        client.table('proxies').update(update_data).eq('id', result['proxy_id']).execute()
                    except Exception as db_error:
                        # If HTTPS fields don't exist, update without them
                        if 'supports_https' in str(db_error) or 'https_response_time_ms' in str(db_error) or 'last_https_check' in str(db_error):
                            print(f"⚠️ HTTPS fields not found in database, updating without them...")
                            minimal_update = {
                                'status': status,
                                'is_working': result['is_working'],
                                'last_checked': current_time,
                                'response_time_ms': result['response_time_ms']
                            }
                            if result['is_working']:
                                minimal_update['last_working'] = current_time
                            client.table('proxies').update(minimal_update).eq('id', result['proxy_id']).execute()
                        else:
                            raise db_error
                    
                    # Insert comprehensive check history
                    check_data = {
                        'proxy_id': result['proxy_id'],
                        'is_working': result['is_working'],
                        'response_time_ms': result['response_time_ms'],
                        'error_message': result['error_message'],
                        'check_method': result['check_method'],
                        'target_url': self.http_test_urls[0]
                    }
                    
                    # Add HTTPS check information if available
                    if 'supports_https' in result:
                        check_data['supports_https'] = result['supports_https']
                        check_data['https_response_time_ms'] = result.get('https_response_time_ms')
                        check_data['https_error_message'] = result.get('https_error_message')
                    
                    try:
                        # Try to insert with HTTPS fields
                        client.table('proxy_check_history').insert(check_data).execute()
                    except Exception as db_error:
                        # If HTTPS fields don't exist in history table, insert without them
                        if 'supports_https' in str(db_error) or 'https_response_time_ms' in str(db_error):
                            minimal_check = {
                                'proxy_id': result['proxy_id'],
                                'is_working': result['is_working'],
                                'response_time_ms': result['response_time_ms'],
                                'error_message': result['error_message'],
                                'check_method': result['check_method'],
                                'target_url': self.http_test_urls[0]
                            }
                            client.table('proxy_check_history').insert(minimal_check).execute()
                        else:
                            raise db_error
                    
                    updated_count += 1
                    
            except Exception as e:
                print(f"⚠️ Failed to update database for {result['ip']}:{result['port']}: {str(e)}")
                continue
        
        print(f"✅ Updated {updated_count} proxy records in database")
        return updated_count
    
    def validate_untested_proxies(self, limit: int = 100) -> Dict:
        """
        Fetch and validate untested proxies from database.
        
        Args:
            limit (int): Maximum number of proxies to validate
            
        Returns:
            Dict: Validation statistics
        """
        try:
            # Fetch untested proxies from database, sorted by last_checked (oldest first)
            client = self.supabase_client.get_client()
            response = client.table('proxies').select("*").eq('status', 'untested').order('last_checked', desc=False).limit(limit).execute()
            
            untested_proxies = response.data
            
            if not untested_proxies:
                print("📭 No untested proxies found in database")
                return {'tested': 0, 'working': 0, 'updated': 0}
            
            print(f"🔍 Found {len(untested_proxies)} untested proxies (sorted by oldest first)")
            
            # Show information about the oldest untested proxy
            if untested_proxies and untested_proxies[0].get('created_at'):
                oldest_created = untested_proxies[0]['created_at']
                print(f"📅 Oldest untested proxy created: {oldest_created}")
            
            # Validate the proxies
            results = self.validate_proxy_list(untested_proxies)
            
            # Update database with results
            updated_count = self.update_database_with_results(results)
            
            working_count = sum(1 for r in results if r['is_working'])
            
            return {
                'tested': len(results),
                'working': working_count,
                'updated': updated_count
            }
            
        except Exception as e:
            print(f"❌ Error validating untested proxies: {str(e)}")
            return {'tested': 0, 'working': 0, 'updated': 0}
    
    def revalidate_old_proxies(self, minutes_old: int = 60, limit: int = 50) -> Dict:
        """
        Revalidate proxies that haven't been checked recently.
        
        Args:
            minutes_old (int): Consider proxies older than this many minutes
            limit (int): Maximum number of proxies to revalidate
            
        Returns:
            Dict: Validation statistics
        """
        try:
            client = self.supabase_client.get_client()
            
            # Calculate the timestamp for comparison
            from datetime import datetime, timedelta
            cutoff_time = (datetime.now() - timedelta(minutes=minutes_old)).isoformat()
            
            # Fetch proxies that haven't been checked recently or have never been checked
            # Sort by last_checked ASC (oldest first) so most outdated proxies are validated first
            response = client.table('proxies').select("*").or_(
                f'last_checked.lt.{cutoff_time},last_checked.is.null'
            ).order('last_checked', desc=False).limit(limit).execute()
            
            old_proxies = response.data
            
            if not old_proxies:
                print(f"📭 No proxies older than {minutes_old} minutes found")
                return {'tested': 0, 'working': 0, 'updated': 0}
            
            print(f"🔍 Found {len(old_proxies)} proxies to revalidate (sorted by oldest first)")
            
            # Show age of oldest proxy for debugging
            if old_proxies and old_proxies[0].get('last_checked'):
                oldest_check = old_proxies[0]['last_checked']
                print(f"📅 Oldest proxy last checked: {oldest_check}")
            elif old_proxies:
                print(f"📅 Processing {len([p for p in old_proxies if not p.get('last_checked')])} never-checked proxies")
            
            # Validate the proxies
            results = self.validate_proxy_list(old_proxies)
            
            # Update database with results
            updated_count = self.update_database_with_results(results)
            
            working_count = sum(1 for r in results if r['is_working'])
            
            return {
                'tested': len(results),
                'working': working_count,
                'updated': updated_count
            }
            
        except Exception as e:
            print(f"❌ Error revalidating old proxies: {str(e)}")
            return {'tested': 0, 'working': 0, 'updated': 0}


# Example usage
if __name__ == "__main__":
    validator = ProxyValidator(timeout=10, max_workers=30)
    
    # Validate untested proxies
    stats = validator.validate_untested_proxies(limit=50)
    print(f"Validation stats: {stats}") 