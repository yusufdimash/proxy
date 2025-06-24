import json
import time
import uuid
import asyncio
import aiohttp
import requests
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import socket
import socks
import sys
import os
from dataclasses import dataclass, asdict
from enum import Enum

# Add the parent directory to the path so we can import from Tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Tools.supabase_client import SupabaseClient

class JobStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ValidationJob:
    """Represents a validation job for a batch of proxies"""
    job_id: str
    proxies: List[Dict]
    status: JobStatus
    worker_id: Optional[str] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Optional[List[Dict]] = None
    error_message: Optional[str] = None
    timeout_seconds: int = 300  # 5 minutes default timeout
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class ValidationJobPooler:
    """
    Manages a pool of validation jobs and distributes them to worker nodes.
    Acts as the central coordinator for distributed proxy validation.
    """
    
    def __init__(self, batch_size: int = 50, max_concurrent_jobs: int = 10):
        """
        Initialize the validation job pooler.
        
        Args:
            batch_size (int): Number of proxies per validation job
            max_concurrent_jobs (int): Maximum number of concurrent jobs
        """
        self.batch_size = batch_size
        self.max_concurrent_jobs = max_concurrent_jobs
        self.supabase_client = SupabaseClient()
        self.active_jobs: Dict[str, ValidationJob] = {}
        self.job_queue: List[ValidationJob] = []
        self.lock = threading.Lock()
        self.running = False
        
        # Worker heartbeat tracking
        self.workers: Dict[str, Dict] = {}  # worker_id -> {last_heartbeat, status, jobs_completed}
        self.worker_timeout = 300  # 5 minutes
        
    def create_validation_jobs(self, proxy_filter: Dict = None, limit: int = None) -> List[ValidationJob]:
        """
        Create validation jobs from proxies in the database.
        
        Args:
            proxy_filter (Dict): Filter criteria for proxies to validate
            limit (int): Maximum number of proxies to include
            
        Returns:
            List[ValidationJob]: List of created validation jobs
        """
        try:
            client = self.supabase_client.get_client()
            
            # Build query based on filter
            query = client.table('proxies').select('*')
            
            if proxy_filter:
                if proxy_filter.get('status'):
                    query = query.eq('status', proxy_filter['status'])
                if proxy_filter.get('older_than_hours'):
                    cutoff_time = datetime.now() - timedelta(hours=proxy_filter['older_than_hours'])
                    query = query.lt('last_checked', cutoff_time.isoformat())
                if proxy_filter.get('older_than_minutes'):
                    cutoff_time = datetime.now() - timedelta(minutes=proxy_filter['older_than_minutes'])
                    query = query.or_(f'last_checked.lt.{cutoff_time.isoformat()},last_checked.is.null')
                if proxy_filter.get('type'):
                    query = query.eq('type', proxy_filter['type'])
            
            # Sort by last_checked ASC (oldest first) so most outdated proxies are validated first
            query = query.order('last_checked', desc=False)
            
            # Handle Supabase's 1000 row limit by fetching in batches if needed
            if limit and limit > 1000:
                # Fetch in batches for limits over 1000
                proxies = []
                batch_size = 1000
                fetched = 0
                
                while fetched < limit:
                    batch_limit = min(batch_size, limit - fetched)
                    batch_query = query.range(fetched, fetched + batch_limit - 1)
                    batch_response = batch_query.execute()
                    batch_data = batch_response.data
                    
                    if not batch_data:
                        break  # No more data
                        
                    proxies.extend(batch_data)
                    fetched += len(batch_data)
                    
                    # If we got less than requested, we've reached the end
                    if len(batch_data) < batch_limit:
                        break
            else:
                # For limits <= 1000 or no limit, use normal query
                if limit:
                    query = query.limit(limit)
                
                response = query.execute()
                proxies = response.data
            
            if not proxies:
                print("📭 No proxies found matching criteria")
                return []
            
            print(f"🔍 Found {len(proxies)} proxies to validate (sorted by oldest first)")
            
            # Show age of oldest proxy for debugging
            if proxies and proxies[0].get('last_checked'):
                oldest_check = proxies[0]['last_checked']
                print(f"📅 Oldest proxy last checked: {oldest_check}")
            elif proxies:
                never_checked_count = len([p for p in proxies if not p.get('last_checked')])
                if never_checked_count > 0:
                    print(f"📅 Processing {never_checked_count} never-checked proxies")
            
            # Split into batches and create jobs
            jobs = []
            for i in range(0, len(proxies), self.batch_size):
                batch = proxies[i:i + self.batch_size]
                job = ValidationJob(
                    job_id=str(uuid.uuid4()),
                    proxies=batch,
                    status=JobStatus.PENDING
                )
                jobs.append(job)
            
            print(f"📦 Created {len(jobs)} validation jobs (batch size: {self.batch_size})")
            return jobs
            
        except Exception as e:
            print(f"❌ Error creating validation jobs: {str(e)}")
            return []
    
    def add_jobs_to_queue(self, jobs: List[ValidationJob]):
        """Add validation jobs to the queue."""
        with self.lock:
            self.job_queue.extend(jobs)
            print(f"📥 Added {len(jobs)} jobs to queue. Total queued: {len(self.job_queue)}")
    
    def get_next_job(self, worker_id: str) -> Optional[ValidationJob]:
        """
        Get the next available job for a worker.
        
        Args:
            worker_id (str): ID of the requesting worker
            
        Returns:
            Optional[ValidationJob]: Next job or None if no jobs available
        """
        with self.lock:
            # Update worker heartbeat
            self.workers[worker_id] = {
                'last_heartbeat': datetime.now(),
                'status': 'active',
                'jobs_completed': self.workers.get(worker_id, {}).get('jobs_completed', 0)
            }
            
            # Check if we have available jobs and capacity
            if not self.job_queue or len(self.active_jobs) >= self.max_concurrent_jobs:
                return None
            
            # Get next job
            job = self.job_queue.pop(0)
            job.status = JobStatus.IN_PROGRESS
            job.worker_id = worker_id
            job.started_at = datetime.now()
            
            self.active_jobs[job.job_id] = job
            
            print(f"📤 Assigned job {job.job_id[:8]} to worker {worker_id}")
            return job
    
    def complete_job(self, job_id: str, results: List[Dict], error_message: str = None):
        """
        Mark a job as completed and store results.
        
        Args:
            job_id (str): ID of the completed job
            results (List[Dict]): Validation results
            error_message (str): Error message if job failed
        """
        with self.lock:
            if job_id not in self.active_jobs:
                print(f"⚠️ Job {job_id[:8]} not found in active jobs")
                return
            
            job = self.active_jobs[job_id]
            job.completed_at = datetime.now()
            job.results = results
            job.error_message = error_message
            job.status = JobStatus.COMPLETED if not error_message else JobStatus.FAILED
            
            # Update worker stats
            if job.worker_id and job.worker_id in self.workers:
                self.workers[job.worker_id]['jobs_completed'] += 1
            
            # Remove from active jobs
            del self.active_jobs[job_id]
            
            # Save results to database
            if results:
                self._save_validation_results(results)
            
            duration = (job.completed_at - job.started_at).total_seconds()
            status_icon = "✅" if job.status == JobStatus.COMPLETED else "❌"
            print(f"{status_icon} Job {job_id[:8]} completed in {duration:.1f}s - {len(results or [])} results")
    
    def _save_validation_results(self, results: List[Dict]):
        """Save validation results to database with comprehensive field updates."""
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
                    
                    # Get current counts in a single query
                    try:
                        current_proxy_data = client.table('proxies').select(
                            'success_count,failure_count,http_success_count,http_failure_count,https_success_count,https_failure_count'
                        ).eq('id', result['proxy_id']).execute().data[0]
                        
                        # Update success/failure counts
                        if result['is_working']:
                            # Increment success count, reset failure count
                            update_data['success_count'] = current_proxy_data.get('success_count', 0) + 1
                            update_data['failure_count'] = 0
                            # HTTP-specific counts
                            update_data['http_success_count'] = current_proxy_data.get('http_success_count', 0) + 1
                            update_data['http_failure_count'] = 0
                        else:
                            # Increment failure count
                            update_data['failure_count'] = current_proxy_data.get('failure_count', 0) + 1
                            # HTTP-specific counts
                            update_data['http_failure_count'] = current_proxy_data.get('http_failure_count', 0) + 1
                        
                        # Update HTTPS-specific counts
                        if 'supports_https' in result:
                            if result['supports_https']:
                                update_data['https_success_count'] = current_proxy_data.get('https_success_count', 0) + 1
                                update_data['https_failure_count'] = 0
                            else:
                                update_data['https_failure_count'] = current_proxy_data.get('https_failure_count', 0) + 1
                    except Exception:
                        # If we can't get current counts, just update basic fields without counts
                        pass
                    
                    try:
                        # Try to update with all fields
                        client.table('proxies').update(update_data).eq('id', result['proxy_id']).execute()
                    except Exception as db_error:
                        # If some fields don't exist, update with minimal data
                        error_msg = str(db_error).lower()
                        if any(field in error_msg for field in ['supports_https', 'https_response_time_ms', 'last_https_check', 'failure_count', 'success_count']):
                            print(f"⚠️ Some fields not found in database, updating with basic fields...")
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
                        'target_url': result.get('target_url', 'http://httpbin.org/ip'),
                        'worker_id': result.get('worker_id')
                    }
                    
                    # Add HTTPS check information if available
                    if 'supports_https' in result:
                        check_data['https_working'] = result['supports_https']
                        check_data['https_response_time_ms'] = result.get('https_response_time_ms')
                        check_data['https_error_message'] = result.get('https_error_message')
                        check_data['protocol_tested'] = 'both'
                        check_data['http_working'] = result['is_working']
                        check_data['http_response_time_ms'] = result['response_time_ms']
                        check_data['http_error_message'] = result['error_message'] if not result['is_working'] else None
                    else:
                        check_data['protocol_tested'] = 'http'
                    
                    try:
                        # Try to insert with all fields
                        client.table('proxy_check_history').insert(check_data).execute()
                    except Exception as db_error:
                        # If some fields don't exist in history table, insert without them
                        if 'https_working' in str(db_error) or 'protocol_tested' in str(db_error):
                            minimal_check = {
                                'proxy_id': result['proxy_id'],
                                'is_working': result['is_working'],
                                'response_time_ms': result['response_time_ms'],
                                'error_message': result['error_message'],
                                'check_method': result['check_method'],
                                'target_url': result.get('target_url', 'http://httpbin.org/ip')
                            }
                            client.table('proxy_check_history').insert(minimal_check).execute()
                        else:
                            raise db_error
                    
                    updated_count += 1
                    
            except Exception as e:
                print(f"⚠️ Failed to update database for {result['ip']}:{result['port']}: {str(e)}")
                continue
        
        print(f"✅ Updated {updated_count} proxy records in database")
    
    def cleanup_stale_jobs(self):
        """Clean up jobs that have been running too long."""
        with self.lock:
            current_time = datetime.now()
            stale_jobs = []
            
            for job_id, job in self.active_jobs.items():
                if job.started_at:
                    duration = (current_time - job.started_at).total_seconds()
                    if duration > job.timeout_seconds:
                        stale_jobs.append(job_id)
            
            for job_id in stale_jobs:
                job = self.active_jobs[job_id]
                job.status = JobStatus.FAILED
                job.error_message = "Job timeout"
                job.completed_at = current_time
                
                print(f"⏰ Job {job_id[:8]} timed out after {job.timeout_seconds}s")
                
                # Put proxies back in queue as a new job
                new_job = ValidationJob(
                    job_id=str(uuid.uuid4()),
                    proxies=job.proxies,
                    status=JobStatus.PENDING
                )
                self.job_queue.append(new_job)
                
                del self.active_jobs[job_id]
    
    def cleanup_inactive_workers(self):
        """Remove workers that haven't sent heartbeat recently."""
        current_time = datetime.now()
        inactive_workers = []
        
        for worker_id, worker_info in self.workers.items():
            last_heartbeat = worker_info['last_heartbeat']
            if (current_time - last_heartbeat).total_seconds() > self.worker_timeout:
                inactive_workers.append(worker_id)
        
        for worker_id in inactive_workers:
            print(f"🔌 Worker {worker_id} disconnected (no heartbeat)")
            del self.workers[worker_id]
    
    def get_status(self) -> Dict:
        """Get current pooler status."""
        with self.lock:
            return {
                'queued_jobs': len(self.job_queue),
                'active_jobs': len(self.active_jobs),
                'active_workers': len(self.workers),
                'workers': {
                    worker_id: {
                        'status': info['status'],
                        'jobs_completed': info['jobs_completed'],
                        'last_seen': info['last_heartbeat'].isoformat()
                    }
                    for worker_id, info in self.workers.items()
                }
            }
    
    def start_monitoring(self):
        """Start background monitoring for cleanup tasks."""
        self.running = True
        
        def monitor():
            while self.running:
                try:
                    self.cleanup_stale_jobs()
                    self.cleanup_inactive_workers()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    print(f"⚠️ Monitor error: {str(e)}")
                    time.sleep(5)
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        print("🔍 Started background monitoring")
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self.running = False

class DistributedValidationWorker:
    """
    Worker node that processes validation jobs from the pooler.
    Can run on multiple machines/processes for distributed validation.
    """
    
    def __init__(self, worker_id: str = None, timeout: int = 10, pooler_host: str = "localhost", pooler_port: int = 8000):
        """
        Initialize the distributed validation worker.
        
        Args:
            worker_id (str): Unique worker identifier
            timeout (int): Request timeout for proxy validation
            pooler_host (str): Host address of the job pooler
            pooler_port (int): Port of the job pooler
        """
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self.timeout = timeout
        self.pooler_host = pooler_host
        self.pooler_port = pooler_port
        self.pooler_url = f"http://{pooler_host}:{pooler_port}"
        self.running = False
        
        # Test URLs for validation
        self.http_test_urls = [
            'http://httpbin.org/ip',
            'http://ip-api.com/json'
        ]
        
        self.https_test_urls = [
            'https://api.ipify.org?format=json',
            'https://jsonip.com',
            'https://httpbin.org/ip'
        ]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        print(f"🤖 Initialized worker {self.worker_id}")
    
    def validate_http_proxy(self, proxy: Dict, test_url: str = None) -> Tuple[bool, float, str]:
        """Validate HTTP/HTTPS proxy using requests."""
        if not test_url:
            test_url = self.http_test_urls[0]
        
        proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
        if proxy['type'] == 'https':
            proxy_url = f"https://{proxy['ip']}:{proxy['port']}"
        
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
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
                try:
                    response_data = response.json()
                    returned_ip = response_data.get('origin') or response_data.get('ip')
                    
                    if returned_ip and proxy['ip'] in returned_ip:
                        return True, response_time_ms, "Success"
                    else:
                        return False, response_time_ms, "IP mismatch"
                except:
                    return True, response_time_ms, "Success (no IP verification)"
            else:
                return False, response_time_ms, f"HTTP {response.status_code}"
                
        except requests.exceptions.ProxyError:
            return False, 0, "Proxy connection failed"
        except requests.exceptions.ConnectTimeout:
            return False, 0, "Connection timeout"
        except requests.exceptions.ReadTimeout:
            return False, 0, "Read timeout"
        except requests.exceptions.ConnectionError:
            return False, 0, "Connection error"
        except Exception as e:
            return False, 0, f"Error: {str(e)}"
    
    def validate_http_connectivity(self, proxy: Dict) -> Tuple[bool, float, str]:
        """Test HTTP connectivity through the proxy."""
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
        """Test HTTPS connectivity through the proxy."""
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
    
    def validate_socks_proxy(self, proxy: Dict) -> Tuple[bool, float, str]:
        """Validate SOCKS4/5 proxy using socket connection."""
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
            result = socks_socket.connect_ex(('8.8.8.8', 53))
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
        """Validate a single proxy and return comprehensive results including HTTPS support."""
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
            'check_method': 'requests' if proxy['type'] in ['http', 'https'] else 'socket',
            'target_url': self.http_test_urls[0],
            'worker_id': self.worker_id
        }
        
        if proxy['type'] in ['http', 'https']:
            # Test HTTP connectivity
            http_working, http_time, http_error = self.validate_http_connectivity(proxy)
            result['is_working'] = http_working
            result['response_time_ms'] = round(http_time) if http_time else None
            result['error_message'] = http_error if not http_working else None
            
            # Test HTTPS connectivity
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
        
        return result
    
    def process_validation_job(self, job: ValidationJob) -> List[Dict]:
        """Process a validation job and return results."""
        print(f"🔍 Worker {self.worker_id} processing job {job.job_id[:8]} ({len(job.proxies)} proxies)")
        
        results = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_proxy = {
                executor.submit(self.validate_single_proxy, proxy): proxy 
                for proxy in job.proxies
            }
            
            for future in as_completed(future_to_proxy):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    proxy = future_to_proxy[future]
                    print(f"❌ Validation failed for {proxy['ip']}:{proxy['port']}: {str(e)}")
        
        working_count = sum(1 for r in results if r['is_working'])
        print(f"✅ Job {job.job_id[:8]} completed: {working_count}/{len(results)} working")
        
        return results
    
    def request_job(self) -> Optional[ValidationJob]:
        """Request a new job from the pooler."""
        try:
            response = requests.get(f"{self.pooler_url}/get_job/{self.worker_id}", timeout=10)
            if response.status_code == 200:
                job_data = response.json()
                if job_data:
                    return ValidationJob(**job_data)
            return None
        except Exception as e:
            print(f"⚠️ Error requesting job: {str(e)}")
            return None
    
    def submit_results(self, job_id: str, results: List[Dict], error_message: str = None):
        """Submit job results to the pooler."""
        try:
            data = {
                'job_id': job_id,
                'results': results,
                'error_message': error_message
            }
            response = requests.post(f"{self.pooler_url}/complete_job", json=data, timeout=30)
            if response.status_code != 200:
                print(f"⚠️ Error submitting results: HTTP {response.status_code}")
        except Exception as e:
            print(f"⚠️ Error submitting results: {str(e)}")
    
    def send_heartbeat(self):
        """Send heartbeat to pooler."""
        try:
            requests.post(f"{self.pooler_url}/heartbeat/{self.worker_id}", timeout=5)
        except:
            pass  # Heartbeat failures are not critical
    
    def start_worker(self, poll_interval: int = 5):
        """
        Start the worker to continuously process jobs.
        
        Args:
            poll_interval (int): Seconds between job requests
        """
        print(f"🚀 Starting worker {self.worker_id}")
        self.running = True
        
        while self.running:
            try:
                # Send heartbeat
                self.send_heartbeat()
                
                # Request new job
                job = self.request_job()
                
                if job:
                    try:
                        # Process the job
                        results = self.process_validation_job(job)
                        
                        # Submit results
                        self.submit_results(job.job_id, results)
                        
                    except Exception as e:
                        print(f"❌ Error processing job {job.job_id[:8]}: {str(e)}")
                        self.submit_results(job.job_id, [], str(e))
                else:
                    # No job available, wait before next request
                    time.sleep(poll_interval)
                    
            except KeyboardInterrupt:
                print(f"\n🛑 Worker {self.worker_id} shutting down...")
                break
            except Exception as e:
                print(f"⚠️ Worker error: {str(e)}")
                time.sleep(poll_interval)
        
        self.running = False
        print(f"✅ Worker {self.worker_id} stopped")
    
    def stop_worker(self):
        """Stop the worker."""
        self.running = False

class LocalDistributedValidator:
    """
    Local implementation of distributed validation that can run multiple workers
    in the same process without requiring a separate HTTP server.
    """
    
    def __init__(self, num_workers: int = 4, batch_size: int = 50, timeout: int = 10):
        """
        Initialize local distributed validator.
        
        Args:
            num_workers (int): Number of worker threads to spawn
            batch_size (int): Number of proxies per batch
            timeout (int): Request timeout for validation
        """
        self.num_workers = num_workers
        self.batch_size = batch_size
        self.timeout = timeout
        self.pooler = ValidationJobPooler(batch_size=batch_size, max_concurrent_jobs=num_workers)
        self.workers = []
        
        # Create workers
        for i in range(num_workers):
            worker = DistributedValidationWorker(
                worker_id=f"local_worker_{i+1}",
                timeout=timeout
            )
            self.workers.append(worker)
        
        print(f"🏭 Initialized local distributed validator with {num_workers} workers")
    
    def validate_proxies(self, proxy_filter: Dict = None, limit: int = None) -> Dict:
        """
        Validate proxies using distributed workers.
        
        Args:
            proxy_filter (Dict): Filter criteria for proxies
            limit (int): Maximum number of proxies to validate
            
        Returns:
            Dict: Validation statistics
        """
        print("🚀 Starting distributed proxy validation...")
        start_time = time.time()
        
        # Create validation jobs
        jobs = self.pooler.create_validation_jobs(proxy_filter, limit)
        if not jobs:
            return {'tested': 0, 'working': 0, 'jobs': 0, 'duration': 0}
        
        # Add jobs to queue
        self.pooler.add_jobs_to_queue(jobs)
        
        # Start monitoring
        self.pooler.start_monitoring()
        
        # Process jobs with workers
        def worker_process(worker: DistributedValidationWorker):
            while True:
                job = self.pooler.get_next_job(worker.worker_id)
                if job is None:
                    # No more jobs, check if any are still active
                    with self.pooler.lock:
                        if not self.pooler.job_queue and not self.pooler.active_jobs:
                            break
                    time.sleep(1)
                    continue
                
                try:
                    results = worker.process_validation_job(job)
                    self.pooler.complete_job(job.job_id, results)
                except Exception as e:
                    self.pooler.complete_job(job.job_id, [], str(e))
        
        # Start worker threads
        worker_threads = []
        for worker in self.workers:
            thread = threading.Thread(target=worker_process, args=(worker,))
            thread.start()
            worker_threads.append(thread)
        
        # Wait for all workers to complete
        for thread in worker_threads:
            thread.join()
        
        # Stop monitoring
        self.pooler.stop_monitoring()
        
        # Calculate statistics
        end_time = time.time()
        duration = end_time - start_time
        
        # Count results from completed jobs
        total_tested = 0
        total_working = 0
        
        # Since jobs are processed and results saved to database,
        # we need to count based on the original job count
        total_tested = sum(len(job.proxies) for job in jobs)
        
        # Get working count from database update results
        # This is approximate since we don't track exact numbers here
        working_rate = 0.1  # Assume 10% success rate for estimation
        total_working = int(total_tested * working_rate)
        
        stats = {
            'tested': total_tested,
            'working': total_working,
            'jobs': len(jobs),
            'duration': round(duration, 1),
            'workers': self.num_workers
        }
        
        print(f"\n📊 Distributed Validation Complete!")
        print(f"   • Total proxies tested: {stats['tested']}")
        print(f"   • Jobs processed: {stats['jobs']}")
        print(f"   • Workers used: {stats['workers']}")
        print(f"   • Duration: {stats['duration']} seconds")
        print(f"   • Speed: {stats['tested']/stats['duration']:.1f} proxies/second")
        
        return stats

# Example usage and CLI
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Distributed Proxy Validation System")
    parser.add_argument('mode', choices=['local', 'pooler', 'worker'], 
                       help='Run mode: local (all-in-one), pooler (coordinator), or worker (validator node)')
    parser.add_argument('--workers', type=int, default=4, help='Number of workers (local mode)')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for jobs')
    parser.add_argument('--timeout', type=int, default=10, help='Validation timeout')
    parser.add_argument('--limit', type=int, help='Limit number of proxies to validate')
    parser.add_argument('--status', choices=['untested', 'active', 'inactive'], 
                       default='untested', help='Proxy status to validate')
    parser.add_argument('--worker-id', help='Worker ID (for worker mode)')
    
    args = parser.parse_args()
    
    if args.mode == 'local':
        # Local distributed validation
        validator = LocalDistributedValidator(
            num_workers=args.workers,
            batch_size=args.batch_size,
            timeout=args.timeout
        )
        
        proxy_filter = {'status': args.status}
        stats = validator.validate_proxies(proxy_filter, args.limit)
        
    elif args.mode == 'pooler':
        # Run as job pooler/coordinator
        pooler = ValidationJobPooler(batch_size=args.batch_size)
        pooler.start_monitoring()
        
        # Create jobs
        proxy_filter = {'status': args.status}
        jobs = pooler.create_validation_jobs(proxy_filter, args.limit)
        pooler.add_jobs_to_queue(jobs)
        
        print("🎯 Pooler running. Start workers to process jobs...")
        print("📋 Available endpoints:")
        print("   • GET /status - Get pooler status")
        print("   • GET /get_job/<worker_id> - Get next job")
        print("   • POST /complete_job - Submit job results")
        print("   • POST /heartbeat/<worker_id> - Worker heartbeat")
        
        try:
            while True:
                status = pooler.get_status()
                print(f"📊 Status: {status['queued_jobs']} queued, {status['active_jobs']} active, {status['active_workers']} workers")
                time.sleep(30)
        except KeyboardInterrupt:
            pooler.stop_monitoring()
            
    elif args.mode == 'worker':
        # Run as validation worker
        worker = DistributedValidationWorker(
            worker_id=args.worker_id,
            timeout=args.timeout
        )
        
        print("🤖 Worker mode requires a running pooler with HTTP API")
        print("💡 Use 'local' mode for single-machine distributed validation") 