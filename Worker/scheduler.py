import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List
import os
import sys

# Add the parent directory to the path so we can import from Tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Tools.supabase_client import SupabaseClient
from Worker.proxy_scraper import ProxyScraper
from Worker.proxy_validator import ProxyValidator

class ProxyScheduler:
    """
    Scheduler for automating proxy scraping and validation tasks.
    Runs continuous background jobs to keep the proxy database fresh.
    """
    
    def __init__(self):
        """Initialize the scheduler with default configurations."""
        self.supabase_client = SupabaseClient()
        self.scraper = None
        self.validator = None
        self.is_running = False
        self.scheduler_thread = None
        
        # Job configurations
        self.config = {
            'scraping': {
                'interval_hours': 6,  # Scrape every 6 hours
                'enabled': True
            },
            'validation': {
                'interval_hours': 2,  # Validate every 2 hours
                'batch_size': 100,
                'enabled': True
            },
            'revalidation': {
                'interval_hours': 12,  # Revalidate old proxies every 12 hours
                'age_threshold_minutes': 60,  # Revalidate proxies older than 60 minutes
                'batch_size': 50,
                'enabled': True
            },
            'cleanup': {
                'interval_hours': 24,  # Cleanup every 24 hours
                'retention_days': 7,  # Keep failed proxies for 7 days
                'enabled': True
            }
        }
    
    def log_job_start(self, job_type: str, source_id: str = None) -> str:
        """
        Log the start of a scraping job in the database.
        
        Args:
            job_type (str): Type of job ('scraping', 'validation', etc.)
            source_id (str): Optional source ID for scraping jobs
            
        Returns:
            str: Job ID
        """
        try:
            client = self.supabase_client.get_client()
            
            job_data = {
                'source_id': source_id,
                'status': 'running',
                'started_at': datetime.now().isoformat()
            }
            
            result = client.table('scraping_jobs').insert(job_data).execute()
            job_id = result.data[0]['id']
            
            print(f"📝 Started {job_type} job: {job_id}")
            return job_id
            
        except Exception as e:
            print(f"⚠️ Failed to log job start: {str(e)}")
            return None
    
    def log_job_completion(self, job_id: str, status: str, stats: Dict = None, error_message: str = None):
        """
        Log the completion of a job in the database.
        
        Args:
            job_id (str): Job ID
            status (str): Job status ('completed', 'failed', etc.)
            stats (Dict): Job statistics
            error_message (str): Error message if failed
        """
        if not job_id:
            return
        
        try:
            client = self.supabase_client.get_client()
            
            update_data = {
                'status': status,
                'completed_at': datetime.now().isoformat()
            }
            
            if error_message:
                update_data['error_message'] = error_message
            
            if stats:
                update_data.update({
                    'proxies_found': stats.get('total_scraped', 0),
                    'proxies_added': stats.get('saved_to_db', 0)
                })
            
            client.table('scraping_jobs').update(update_data).eq('id', job_id).execute()
            
            print(f"✅ Completed job: {job_id} with status: {status}")
            
        except Exception as e:
            print(f"⚠️ Failed to log job completion: {str(e)}")
    
    def run_scraping_job(self):
        """Run a scheduled scraping job."""
        if not self.config['scraping']['enabled']:
            return
        
        print(f"\n🕐 {datetime.now()} - Starting scheduled scraping job")
        job_id = self.log_job_start('scraping')
        
        try:
            # Initialize scraper if needed
            if not self.scraper:
                self.scraper = ProxyScraper(headless=True, delay=2)
            
            # Run scraping
            stats = self.scraper.run_scraping_job()
            
            # Log successful completion
            self.log_job_completion(job_id, 'completed', stats)
            
            print(f"✅ Scheduled scraping job completed successfully")
            
        except Exception as e:
            error_msg = f"Scraping job failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.log_job_completion(job_id, 'failed', error_message=error_msg)
    
    def run_validation_job(self):
        """Run a scheduled validation job."""
        if not self.config['validation']['enabled']:
            return
        
        print(f"\n🕐 {datetime.now()} - Starting scheduled validation job")
        job_id = self.log_job_start('validation')
        
        try:
            # Initialize validator if needed
            if not self.validator:
                self.validator = ProxyValidator(timeout=10, max_workers=30)
            
            # Validate untested proxies
            batch_size = self.config['validation']['batch_size']
            stats = self.validator.validate_untested_proxies(limit=batch_size)
            
            # Log completion
            self.log_job_completion(job_id, 'completed', stats)
            
            print(f"✅ Scheduled validation job completed: {stats}")
            
        except Exception as e:
            error_msg = f"Validation job failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.log_job_completion(job_id, 'failed', error_message=error_msg)
    
    def run_revalidation_job(self):
        """Run a scheduled revalidation job for old proxies."""
        if not self.config['revalidation']['enabled']:
            return
        
        print(f"\n🕐 {datetime.now()} - Starting scheduled revalidation job")
        job_id = self.log_job_start('revalidation')
        
        try:
            # Initialize validator if needed
            if not self.validator:
                self.validator = ProxyValidator(timeout=10, max_workers=30)
            
            # Revalidate old proxies
            minutes_old = self.config['revalidation']['age_threshold_minutes']
            batch_size = self.config['revalidation']['batch_size']
            stats = self.validator.revalidate_old_proxies(minutes_old=minutes_old, limit=batch_size)
            
            # Log completion
            self.log_job_completion(job_id, 'completed', stats)
            
            print(f"✅ Scheduled revalidation job completed: {stats}")
            
        except Exception as e:
            error_msg = f"Revalidation job failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.log_job_completion(job_id, 'failed', error_message=error_msg)
    
    def run_cleanup_job(self):
        """Run a scheduled cleanup job to remove old failed proxies."""
        if not self.config['cleanup']['enabled']:
            return
        
        print(f"\n🕐 {datetime.now()} - Starting scheduled cleanup job")
        job_id = self.log_job_start('cleanup')
        
        try:
            client = self.supabase_client.get_client()
            retention_days = self.config['cleanup']['retention_days']
            
            # Delete old failed proxies
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            result = client.table('proxies').delete().eq('status', 'failed').filter(
                'updated_at', 'lt', cutoff_date.isoformat()
            ).execute()
            
            deleted_count = len(result.data) if result.data else 0
            
            # Delete old check history (keep last 30 days)
            history_cutoff = datetime.now() - timedelta(days=30)
            
            history_result = client.table('proxy_check_history').delete().filter(
                'created_at', 'lt', history_cutoff.isoformat()
            ).execute()
            
            history_deleted = len(history_result.data) if history_result.data else 0
            
            stats = {
                'deleted_proxies': deleted_count,
                'deleted_history': history_deleted
            }
            
            # Log completion
            self.log_job_completion(job_id, 'completed', stats)
            
            print(f"✅ Cleanup job completed: {stats}")
            
        except Exception as e:
            error_msg = f"Cleanup job failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.log_job_completion(job_id, 'failed', error_message=error_msg)
    
    def setup_schedules(self):
        """Set up all scheduled jobs."""
        print("📅 Setting up scheduled jobs...")
        
        if self.config['scraping']['enabled']:
            schedule.every(self.config['scraping']['interval_hours']).hours.do(self.run_scraping_job)
            print(f"   • Scraping: every {self.config['scraping']['interval_hours']} hours")
        
        if self.config['validation']['enabled']:
            schedule.every(self.config['validation']['interval_hours']).hours.do(self.run_validation_job)
            print(f"   • Validation: every {self.config['validation']['interval_hours']} hours")
        
        if self.config['revalidation']['enabled']:
            schedule.every(self.config['revalidation']['interval_hours']).hours.do(self.run_revalidation_job)
            print(f"   • Revalidation: every {self.config['revalidation']['interval_hours']} hours")
        
        if self.config['cleanup']['enabled']:
            schedule.every(self.config['cleanup']['interval_hours']).hours.do(self.run_cleanup_job)
            print(f"   • Cleanup: every {self.config['cleanup']['interval_hours']} hours")
        
        print("✅ All schedules configured")
    
    def run_scheduler(self):
        """Run the scheduler in a separate thread."""
        print("🚀 Starting proxy scheduler...")
        self.is_running = True
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                print("\n🛑 Scheduler interrupted by user")
                break
            except Exception as e:
                print(f"❌ Scheduler error: {str(e)}")
                time.sleep(60)  # Wait before retrying
        
        print("🔒 Scheduler stopped")
    
    def start(self, run_immediate: bool = False):
        """
        Start the scheduler.
        
        Args:
            run_immediate (bool): Run all jobs immediately before starting schedule
        """
        # Setup schedules
        self.setup_schedules()
        
        # Run immediate jobs if requested
        if run_immediate:
            print("🚀 Running immediate jobs...")
            self.run_scraping_job()
            self.run_validation_job()
        
        # Start scheduler in background thread
        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        print("✅ Proxy scheduler started successfully")
        return self.scheduler_thread
    
    def stop(self):
        """Stop the scheduler."""
        print("🛑 Stopping scheduler...")
        self.is_running = False
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        print("✅ Scheduler stopped")
    
    def get_next_run_times(self) -> Dict[str, str]:
        """Get the next scheduled run times for all jobs."""
        jobs = schedule.get_jobs()
        next_runs = {}
        
        for job in jobs:
            job_name = job.job_func.__name__.replace('run_', '').replace('_job', '')
            next_runs[job_name] = str(job.next_run) if job.next_run else "Not scheduled"
        
        return next_runs
    
    def get_job_stats(self, hours: int = 24) -> Dict:
        """
        Get statistics for jobs run in the last N hours.
        
        Args:
            hours (int): Number of hours to look back
            
        Returns:
            Dict: Job statistics
        """
        try:
            client = self.supabase_client.get_client()
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            result = client.table('scraping_jobs').select("*").filter(
                'created_at', 'gte', cutoff_time.isoformat()
            ).execute()
            
            jobs = result.data
            
            stats = {
                'total_jobs': len(jobs),
                'completed': len([j for j in jobs if j['status'] == 'completed']),
                'failed': len([j for j in jobs if j['status'] == 'failed']),
                'running': len([j for j in jobs if j['status'] == 'running']),
                'total_proxies_found': sum(j.get('proxies_found', 0) for j in jobs),
                'total_proxies_added': sum(j.get('proxies_added', 0) for j in jobs)
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting job stats: {str(e)}")
            return {}


# Example usage
if __name__ == "__main__":
    scheduler = ProxyScheduler()
    
    try:
        # Start scheduler with immediate execution
        thread = scheduler.start(run_immediate=True)
        
        print("\n📊 Scheduler is running. Press Ctrl+C to stop.")
        print("Next scheduled runs:")
        for job, next_run in scheduler.get_next_run_times().items():
            print(f"   • {job}: {next_run}")
        
        # Keep the main thread alive
        while True:
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping scheduler...")
        scheduler.stop()
        print("✅ Scheduler stopped successfully") 