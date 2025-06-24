#!/usr/bin/env python3
"""
Test script for the distributed proxy validation system.
This demonstrates how the new distributed validator works.
"""

import sys
import os
import time

# Add the Worker directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Worker'))

from distributed_validator import LocalDistributedValidator, ValidationJobPooler, DistributedValidationWorker

def test_local_distributed_validation():
    """Test the local distributed validation system."""
    print("🧪 Testing Local Distributed Validation System")
    print("=" * 60)
    
    print("\n1️⃣ Initializing Local Distributed Validator...")
    validator = LocalDistributedValidator(
        num_workers=6,      # Use 6 workers for faster processing
        batch_size=25,      # Smaller batches for better distribution
        timeout=8           # Faster timeout for testing
    )
    
    print("\n2️⃣ Starting distributed validation...")
    print("   This will validate proxies using multiple worker threads")
    print("   Each worker processes batches of proxies in parallel")
    
    # Test with untested proxies
    proxy_filter = {'status': 'untested'}
    stats = validator.validate_proxies(proxy_filter, limit=200)  # Limit for testing
    
    print(f"\n✅ Test Results:")
    print(f"   • Total proxies processed: {stats['tested']}")
    print(f"   • Jobs created: {stats['jobs']}")
    print(f"   • Workers used: {stats['workers']}")
    print(f"   • Total duration: {stats['duration']} seconds")
    print(f"   • Processing speed: {stats['tested']/stats['duration']:.1f} proxies/second")
    
    return stats

def test_job_pooler():
    """Test the job pooler functionality."""
    print("\n🧪 Testing Job Pooler System")
    print("=" * 60)
    
    print("\n1️⃣ Creating Job Pooler...")
    pooler = ValidationJobPooler(batch_size=30, max_concurrent_jobs=5)
    
    print("\n2️⃣ Creating validation jobs...")
    proxy_filter = {'status': 'untested'}
    jobs = pooler.create_validation_jobs(proxy_filter, limit=100)
    
    if jobs:
        print(f"   • Created {len(jobs)} jobs")
        print(f"   • Total proxies: {sum(len(job.proxies) for job in jobs)}")
        
        # Add jobs to queue
        pooler.add_jobs_to_queue(jobs)
        
        print("\n3️⃣ Pooler Status:")
        status = pooler.get_status()
        print(f"   • Queued jobs: {status['queued_jobs']}")
        print(f"   • Active jobs: {status['active_jobs']}")
        print(f"   • Active workers: {status['active_workers']}")
        
        return len(jobs)
    else:
        print("   • No jobs created (no untested proxies found)")
        return 0

def test_worker_creation():
    """Test worker creation and basic functionality."""
    print("\n🧪 Testing Worker Creation")
    print("=" * 60)
    
    print("\n1️⃣ Creating Distributed Workers...")
    workers = []
    
    for i in range(3):
        worker = DistributedValidationWorker(
            worker_id=f"test_worker_{i+1}",
            timeout=5
        )
        workers.append(worker)
        print(f"   • Created worker: {worker.worker_id}")
    
    print(f"\n✅ Successfully created {len(workers)} workers")
    return workers

def performance_comparison():
    """Compare performance between traditional and distributed validation."""
    print("\n🧪 Performance Comparison Test")
    print("=" * 60)
    
    try:
        from proxy_validator import ProxyValidator
        
        print("\n1️⃣ Testing Traditional Validator...")
        traditional_validator = ProxyValidator(timeout=8, max_workers=30)
        
        start_time = time.time()
        traditional_stats = traditional_validator.validate_untested_proxies(limit=100)
        traditional_duration = time.time() - start_time
        
        print(f"   • Traditional validation took: {traditional_duration:.1f} seconds")
        print(f"   • Proxies tested: {traditional_stats['tested']}")
        
        print("\n2️⃣ Testing Distributed Validator...")
        distributed_validator = LocalDistributedValidator(
            num_workers=6,
            batch_size=20,
            timeout=8
        )
        
        start_time = time.time()
        distributed_stats = distributed_validator.validate_proxies({'status': 'untested'}, limit=100)
        distributed_duration = time.time() - start_time
        
        print(f"   • Distributed validation took: {distributed_duration:.1f} seconds")
        print(f"   • Proxies tested: {distributed_stats['tested']}")
        
        if traditional_duration > 0 and distributed_duration > 0:
            speedup = traditional_duration / distributed_duration
            print(f"\n📊 Performance Comparison:")
            print(f"   • Traditional: {traditional_stats['tested']/traditional_duration:.1f} proxies/sec")
            print(f"   • Distributed: {distributed_stats['tested']/distributed_duration:.1f} proxies/sec")
            print(f"   • Speedup: {speedup:.1f}x faster")
        
    except ImportError:
        print("   ⚠️ Traditional ProxyValidator not available for comparison")

def main():
    """Run all tests."""
    print("🚀 Distributed Proxy Validation System - Test Suite")
    print("=" * 80)
    
    try:
        # Test 1: Basic worker creation
        workers = test_worker_creation()
        
        # Test 2: Job pooler functionality
        job_count = test_job_pooler()
        
        # Test 3: Local distributed validation
        if job_count > 0:
            stats = test_local_distributed_validation()
            
            # Test 4: Performance comparison (if possible)
            performance_comparison()
        else:
            print("\n⚠️ Skipping validation tests - no untested proxies available")
            print("💡 Run the scraper first to get some proxies to validate")
        
        print("\n🎉 All tests completed successfully!")
        print("\n📋 Usage Examples:")
        print("   # Use distributed validation in CLI:")
        print("   python -m Worker.main validate --distributed --workers 8 --batch-size 30")
        print("")
        print("   # Use standalone distributed validator:")
        print("   python Worker/distributed_validator.py local --workers 6 --batch-size 50")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 