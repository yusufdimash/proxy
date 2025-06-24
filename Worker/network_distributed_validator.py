#!/usr/bin/env python3
"""
Network Distributed Proxy Validation System

This module provides a network-based distributed validation system that can
scale across multiple computers. It includes:

1. ValidationServer: Central server that manages jobs and coordinates workers
2. RemoteValidationWorker: Client that runs on worker computers
3. NetworkDistributedValidator: Client interface for submitting validation jobs

Architecture:
- Master Computer: Runs ValidationServer
- Worker Computers: Run RemoteValidationWorker instances
- Communication: HTTP REST API between server and workers
"""

import json
import time
import socket
import threading
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify
import uuid

# Import existing components
from .distributed_validator import ValidationJob, JobStatus, DistributedValidationWorker
from Tools.supabase_client import SupabaseClient

class ValidationServer:
    """
    Central server that manages validation jobs and coordinates remote workers.
    Runs on the master computer.
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8000, batch_size: int = 50):
        self.host = host
        self.port = port
        self.batch_size = batch_size
        self.app = Flask(__name__)
        self.supabase_client = SupabaseClient()
        
        # Job management
        self.job_queue = []
        self.active_jobs = {}
        self.completed_jobs = {}
        self.job_lock = threading.Lock()
        
        # Worker management
        self.active_workers = {}
        self.worker_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'total_jobs_created': 0,
            'total_jobs_completed': 0,
            'total_proxies_validated': 0,
            'total_working_proxies': 0,
            'server_start_time': datetime.now()
        }
        
        self._setup_routes()
        self._start_cleanup_thread()
    
    def _setup_routes(self):
        """Setup Flask routes for the API."""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
        
        @self.app.route('/register_worker', methods=['POST'])
        def register_worker():
            data = request.json
            worker_id = data.get('worker_id')
            worker_info = data.get('worker_info', {})
            
            with self.worker_lock:
                self.active_workers[worker_id] = {
                    'info': worker_info,
                    'last_heartbeat': datetime.now(),
                    'jobs_completed': 0,
                    'total_proxies_processed': 0
                }
            
            print(f"🤖 Worker registered: {worker_id} from {worker_info.get('hostname', 'unknown')}")
            return jsonify({'status': 'registered', 'worker_id': worker_id})
        
        @self.app.route('/get_job/<worker_id>', methods=['GET'])
        def get_job(worker_id):
            job = self._assign_job_to_worker(worker_id)
            if job:
                return jsonify(asdict(job))
            return jsonify({}), 204  # No content
        
        @self.app.route('/complete_job', methods=['POST'])
        def complete_job():
            data = request.json
            job_id = data.get('job_id')
            results = data.get('results', [])
            error_message = data.get('error_message')
            
            self._complete_job(job_id, results, error_message)
            return jsonify({'status': 'completed'})
        
        @self.app.route('/heartbeat/<worker_id>', methods=['POST'])
        def heartbeat(worker_id):
            with self.worker_lock:
                if worker_id in self.active_workers:
                    self.active_workers[worker_id]['last_heartbeat'] = datetime.now()
            return jsonify({'status': 'acknowledged'})
        
        @self.app.route('/stats', methods=['GET'])
        def get_stats():
            with self.worker_lock:
                worker_count = len(self.active_workers)
                worker_stats = {
                    wid: {
                        'last_seen': info['last_heartbeat'].isoformat(),
                        'jobs_completed': info['jobs_completed'],
                        'hostname': info['info'].get('hostname', 'unknown')
                    }
                    for wid, info in self.active_workers.items()
                }
            
            with self.job_lock:
                queue_size = len(self.job_queue)
                active_jobs_count = len(self.active_jobs)
            
            return jsonify({
                'server_stats': self.stats,
                'worker_count': worker_count,
                'queue_size': queue_size,
                'active_jobs': active_jobs_count,
                'workers': worker_stats
            })
        
        @self.app.route('/submit_validation_job', methods=['POST'])
        def submit_validation_job():
            data = request.json
            proxy_filter = data.get('proxy_filter', {})
            limit = data.get('limit')
            
            job_count = self._create_validation_jobs(proxy_filter, limit)
            return jsonify({
                'status': 'submitted',
                'jobs_created': job_count,
                'message': f'Created {job_count} validation jobs'
            })
    
    def _create_validation_jobs(self, proxy_filter: Dict = None, limit: int = None) -> int:
        """Create validation jobs from database proxies."""
        try:
            # Build query based on filter
            client = self.supabase_client.get_client()
            query = client.table('proxies').select("*")
            
            if proxy_filter:
                if proxy_filter.get('status'):
                    query = query.eq('status', proxy_filter['status'])
                if proxy_filter.get('type'):
                    query = query.eq('type', proxy_filter['type'])
                if proxy_filter.get('country'):
                    query = query.eq('country', proxy_filter['country'])
            
            if limit:
                query = query.limit(limit)
            
            response = query.execute()
            proxies = response.data
            
            if not proxies:
                print("📭 No proxies found matching the filter criteria")
                return 0
            
            # Split proxies into batches and create jobs
            jobs = []
            for i in range(0, len(proxies), self.batch_size):
                batch = proxies[i:i + self.batch_size]
                job = ValidationJob(
                    job_id=str(uuid.uuid4()),
                    proxies=batch,
                    status=JobStatus.PENDING
                )
                jobs.append(job)
            
            # Add jobs to queue
            with self.job_lock:
                self.job_queue.extend(jobs)
                self.stats['total_jobs_created'] += len(jobs)
            
            print(f"📋 Created {len(jobs)} validation jobs for {len(proxies)} proxies")
            return len(jobs)
            
        except Exception as e:
            print(f"❌ Error creating validation jobs: {str(e)}")
            return 0
    
    def _assign_job_to_worker(self, worker_id: str) -> Optional[ValidationJob]:
        """Assign the next available job to a worker."""
        with self.job_lock:
            if not self.job_queue:
                return None
            
            job = self.job_queue.pop(0)
            job.status = JobStatus.IN_PROGRESS
            job.worker_id = worker_id
            job.started_at = datetime.now()
            
            self.active_jobs[job.job_id] = job
            
        print(f"📤 Assigned job {job.job_id[:8]} to worker {worker_id} ({len(job.proxies)} proxies)")
        return job
    
    def _complete_job(self, job_id: str, results: List[Dict], error_message: str = None):
        """Mark a job as completed and save results."""
        with self.job_lock:
            if job_id not in self.active_jobs:
                print(f"⚠️ Unknown job completion: {job_id[:8]}")
                return
            
            job = self.active_jobs.pop(job_id)
            job.status = JobStatus.COMPLETED if not error_message else JobStatus.FAILED
            job.completed_at = datetime.now()
            job.results = results
            job.error_message = error_message
            
            self.completed_jobs[job_id] = job
            
            # Update statistics
            self.stats['total_jobs_completed'] += 1
            self.stats['total_proxies_validated'] += len(results)
            self.stats['total_working_proxies'] += sum(1 for r in results if r.get('is_working'))
        
        # Update worker statistics
        if job.worker_id:
            with self.worker_lock:
                if job.worker_id in self.active_workers:
                    self.active_workers[job.worker_id]['jobs_completed'] += 1
                    self.active_workers[job.worker_id]['total_proxies_processed'] += len(results)
        
        # Save results to database
        if results and not error_message:
            self._save_validation_results(results)
        
        working_count = sum(1 for r in results if r.get('is_working')) if results else 0
        total_count = len(results) if results else 0
        
        print(f"✅ Job {job_id[:8]} completed by {job.worker_id}: {working_count}/{total_count} working")
    
    def _save_validation_results(self, results: List[Dict]):
        """Save validation results to database."""
        try:
            client = self.supabase_client.get_client()
            
            for result in results:
                if result.get('proxy_id'):
                    # Update proxy status
                    status = 'active' if result['is_working'] else 'inactive'
                    self.supabase_client.update_proxy_status(result['proxy_id'], status)
                    
                    # Insert check history
                    check_data = {
                        'proxy_id': result['proxy_id'],
                        'is_working': result['is_working'],
                        'response_time_ms': result['response_time_ms'],
                        'error_message': result['error_message'],
                        'check_method': result.get('check_method', 'distributed'),
                        'target_url': result.get('target_url', 'http://httpbin.org/ip'),
                        'worker_id': result.get('worker_id')
                    }
                    
                    client.table('proxy_check_history').insert(check_data).execute()
        
        except Exception as e:
            print(f"⚠️ Error saving validation results: {str(e)}")
    
    def _start_cleanup_thread(self):
        """Start background thread for cleanup tasks."""
        def cleanup_loop():
            while True:
                try:
                    self._cleanup_stale_jobs()
                    self._cleanup_inactive_workers()
                    time.sleep(60)  # Run cleanup every minute
                except Exception as e:
                    print(f"⚠️ Cleanup error: {str(e)}")
        
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
    
    def _cleanup_stale_jobs(self):
        """Clean up jobs that have been running too long."""
        stale_threshold = datetime.now() - timedelta(minutes=10)
        
        with self.job_lock:
            stale_jobs = [
                job_id for job_id, job in self.active_jobs.items()
                if job.started_at and job.started_at < stale_threshold
            ]
            
            for job_id in stale_jobs:
                job = self.active_jobs.pop(job_id)
                job.status = JobStatus.FAILED
                job.error_message = "Job timeout - returned to queue"
                job.worker_id = None
                job.started_at = None
                
                # Return to queue for retry
                self.job_queue.append(job)
                print(f"🔄 Returned stale job {job_id[:8]} to queue")
    
    def _cleanup_inactive_workers(self):
        """Remove workers that haven't sent heartbeat recently."""
        inactive_threshold = datetime.now() - timedelta(minutes=5)
        
        with self.worker_lock:
            inactive_workers = [
                worker_id for worker_id, info in self.active_workers.items()
                if info['last_heartbeat'] < inactive_threshold
            ]
            
            for worker_id in inactive_workers:
                del self.active_workers[worker_id]
                print(f"🚫 Removed inactive worker: {worker_id}")
    
    def start_server(self):
        """Start the validation server."""
        print(f"🚀 Starting ValidationServer on {self.host}:{self.port}")
        print(f"📊 Server will be available at http://{self.host}:{self.port}")
        print(f"📈 Stats endpoint: http://{self.host}:{self.port}/stats")
        
        self.app.run(host=self.host, port=self.port, threaded=True, debug=False)


class RemoteValidationWorker:
    """
    Worker client that runs on remote computers and connects to ValidationServer.
    """
    
    def __init__(self, server_host: str, server_port: int = 8000, worker_id: str = None, 
                 timeout: int = 10, max_concurrent: int = 20):
        self.server_url = f"http://{server_host}:{server_port}"
        self.worker_id = worker_id or f"worker-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.running = False
        
        # Get worker info
        self.worker_info = {
            'hostname': socket.gethostname(),
            'max_concurrent': max_concurrent,
            'timeout': timeout,
            'version': '1.0.0'
        }
        
        # Use the existing validation logic
        self.validator = DistributedValidationWorker(
            worker_id=self.worker_id,
            timeout=timeout
        )
    
    def register_with_server(self) -> bool:
        """Register this worker with the server."""
        try:
            response = requests.post(
                f"{self.server_url}/register_worker",
                json={
                    'worker_id': self.worker_id,
                    'worker_info': self.worker_info
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Worker {self.worker_id} registered with server")
                return True
            else:
                print(f"❌ Failed to register worker: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Registration error: {str(e)}")
            return False
    
    def request_job(self) -> Optional[ValidationJob]:
        """Request a new job from the server."""
        try:
            response = requests.get(
                f"{self.server_url}/get_job/{self.worker_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                job_data = response.json()
                if job_data:
                    return ValidationJob(**job_data)
            elif response.status_code == 204:
                # No jobs available
                return None
            else:
                print(f"⚠️ Error requesting job: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Error requesting job: {str(e)}")
        
        return None
    
    def submit_results(self, job_id: str, results: List[Dict], error_message: str = None):
        """Submit job results to the server."""
        try:
            data = {
                'job_id': job_id,
                'results': results,
                'error_message': error_message
            }
            
            response = requests.post(
                f"{self.server_url}/complete_job",
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"⚠️ Error submitting results: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Error submitting results: {str(e)}")
    
    def send_heartbeat(self):
        """Send heartbeat to server."""
        try:
            requests.post(f"{self.server_url}/heartbeat/{self.worker_id}", timeout=5)
        except:
            pass  # Heartbeat failures are not critical
    
    def start_worker(self, poll_interval: int = 5):
        """Start the worker to continuously process jobs."""
        print(f"🚀 Starting RemoteValidationWorker: {self.worker_id}")
        print(f"🔗 Connecting to server: {self.server_url}")
        
        # Register with server
        if not self.register_with_server():
            print("❌ Failed to register with server. Exiting.")
            return
        
        self.running = True
        consecutive_failures = 0
        
        while self.running:
            try:
                # Send heartbeat
                self.send_heartbeat()
                
                # Request new job
                job = self.request_job()
                
                if job:
                    consecutive_failures = 0
                    try:
                        # Process the job using existing validator
                        results = self.validator.process_validation_job(job)
                        
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
                consecutive_failures += 1
                print(f"⚠️ Worker error #{consecutive_failures}: {str(e)}")
                
                if consecutive_failures >= 5:
                    print("❌ Too many consecutive failures. Stopping worker.")
                    break
                
                time.sleep(poll_interval * consecutive_failures)  # Exponential backoff
        
        self.running = False
        print(f"✅ Worker {self.worker_id} stopped")


class NetworkDistributedValidator:
    """
    Client interface for submitting validation jobs to the network distributed system.
    """
    
    def __init__(self, server_host: str, server_port: int = 8000):
        self.server_url = f"http://{server_host}:{server_port}"
    
    def validate_proxies(self, proxy_filter: Dict = None, limit: int = None) -> Dict:
        """Submit a validation job to the distributed system."""
        try:
            # Submit validation job
            response = requests.post(
                f"{self.server_url}/submit_validation_job",
                json={
                    'proxy_filter': proxy_filter or {},
                    'limit': limit
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                job_count = result.get('jobs_created', 0)
                
                print(f"📋 Submitted validation job: {job_count} jobs created")
                
                # Wait for completion and monitor progress
                return self._monitor_validation_progress()
            else:
                print(f"❌ Failed to submit job: HTTP {response.status_code}")
                return {'error': 'Failed to submit validation job'}
                
        except Exception as e:
            print(f"❌ Error submitting validation job: {str(e)}")
            return {'error': str(e)}
    
    def _monitor_validation_progress(self) -> Dict:
        """Monitor validation progress and return final statistics."""
        initial_stats = self.get_server_stats()
        if not initial_stats:
            return {'error': 'Cannot connect to server'}
        
        initial_completed = initial_stats['server_stats']['total_jobs_completed']
        start_time = time.time()
        
        print("🔍 Monitoring validation progress...")
        print("Press Ctrl+C to stop monitoring (jobs will continue in background)")
        
        try:
            while True:
                time.sleep(5)
                
                current_stats = self.get_server_stats()
                if not current_stats:
                    continue
                
                completed_jobs = current_stats['server_stats']['total_jobs_completed']
                queue_size = current_stats['queue_size']
                active_jobs = current_stats['active_jobs']
                worker_count = current_stats['worker_count']
                
                elapsed = time.time() - start_time
                jobs_processed = completed_jobs - initial_completed
                
                print(f"📊 Progress: {jobs_processed} jobs completed, "
                      f"{queue_size} queued, {active_jobs} active, "
                      f"{worker_count} workers, {elapsed:.1f}s elapsed")
                
                # Check if all jobs are done
                if queue_size == 0 and active_jobs == 0:
                    print("✅ All validation jobs completed!")
                    break
                    
        except KeyboardInterrupt:
            print("\n⏸️ Monitoring stopped (jobs continue in background)")
        
        # Return final statistics
        final_stats = self.get_server_stats()
        if final_stats:
            return final_stats['server_stats']
        else:
            return {'error': 'Cannot get final statistics'}
    
    def get_server_stats(self) -> Optional[Dict]:
        """Get current server statistics."""
        try:
            response = requests.get(f"{self.server_url}/stats", timeout=10)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None


def main():
    """CLI interface for network distributed validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Network Distributed Proxy Validation')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Start validation server')
    server_parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    server_parser.add_argument('--port', type=int, default=8000, help='Server port (default: 8000)')
    server_parser.add_argument('--batch-size', type=int, default=50, help='Job batch size (default: 50)')
    
    # Worker command
    worker_parser = subparsers.add_parser('worker', help='Start validation worker')
    worker_parser.add_argument('server_host', help='Server hostname or IP')
    worker_parser.add_argument('--port', type=int, default=8000, help='Server port (default: 8000)')
    worker_parser.add_argument('--worker-id', help='Custom worker ID')
    worker_parser.add_argument('--timeout', type=int, default=10, help='Proxy timeout (default: 10)')
    worker_parser.add_argument('--concurrent', type=int, default=20, help='Max concurrent validations (default: 20)')
    
    # Client command
    client_parser = subparsers.add_parser('validate', help='Submit validation job')
    client_parser.add_argument('server_host', help='Server hostname or IP')
    client_parser.add_argument('--port', type=int, default=8000, help='Server port (default: 8000)')
    client_parser.add_argument('--status', help='Filter by proxy status')
    client_parser.add_argument('--type', help='Filter by proxy type')
    client_parser.add_argument('--country', help='Filter by country')
    client_parser.add_argument('--limit', type=int, help='Limit number of proxies')
    
    args = parser.parse_args()
    
    if args.command == 'server':
        server = ValidationServer(host=args.host, port=args.port, batch_size=args.batch_size)
        server.start_server()
        
    elif args.command == 'worker':
        worker = RemoteValidationWorker(
            server_host=args.server_host,
            server_port=args.port,
            worker_id=args.worker_id,
            timeout=args.timeout,
            max_concurrent=args.concurrent
        )
        worker.start_worker()
        
    elif args.command == 'validate':
        proxy_filter = {}
        if args.status:
            proxy_filter['status'] = args.status
        if args.type:
            proxy_filter['type'] = args.type
        if args.country:
            proxy_filter['country'] = args.country
            
        validator = NetworkDistributedValidator(args.server_host, args.port)
        result = validator.validate_proxies(proxy_filter, args.limit)
        print(f"\n📊 Final Results: {result}")
        
    else:
        parser.print_help()


if __name__ == '__main__':
    main() 