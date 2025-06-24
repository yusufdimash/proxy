#!/usr/bin/env python3
"""
Main runner script for the Proxy Scraper Worker.
Provides command-line interface to run different worker functions.
"""

import argparse
import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import from Tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Worker.proxy_scraper import ProxyScraper
from Worker.proxy_validator import ProxyValidator
from Worker.scheduler import ProxyScheduler
from Tools.supabase_client import SupabaseClient

def run_scraping(args):
    """Run proxy scraping job."""
    print("🚀 Starting proxy scraping...")
    
    scraper = ProxyScraper(
        headless=args.headless,
        delay=args.delay
    )
    
    if args.sources:
        # Scrape specific sources
        print(f"🎯 Targeting specific sources: {', '.join(args.sources)}")
        
        # Validate source names
        available_sources = scraper._load_dynamic_configurations()
        invalid_sources = [s for s in args.sources if s not in available_sources]
        
        if invalid_sources:
            print(f"❌ Invalid source names: {', '.join(invalid_sources)}")
            print(f"📋 Available sources:")
            for name in sorted(available_sources.keys()):
                source = available_sources[name]
                method = source.get('method', 'unknown')
                pagination = "📄" if source.get('has_pagination', False) else "📋"
                print(f"   {pagination} {name} ({method})")
            return
        
        # Run scraping for specific sources
        stats = scraper.scrape_proxies(sources=args.sources)
        
        print(f"\n📊 Specific Source Scraping Results:")
        print(f"   • Sources scraped: {len(args.sources)}")
        print(f"   • Total proxies found: {len(stats)}")
        
        # Show per-source breakdown
        for source_name in args.sources:
            source_proxies = [p for p in stats if p.get('source_name') == source_name]
            print(f"   • {source_name}: {len(source_proxies)} proxies")
    
    else:
        # Run full scraping job for all sources
        stats = scraper.run_scraping_job()
        
        print(f"\n📊 Full Scraping Results:")
        print(f"   • Total scraped: {stats['total_scraped']}")
        print(f"   • Unique proxies: {stats['unique_proxies']}")
        print(f"   • Saved to DB: {stats['saved_to_db']}")
        print(f"   • Duration: {stats['duration_seconds']:.1f}s")

def run_validation(args):
    """Run proxy validation job."""
    print("🔍 Starting proxy validation...")
    
    if args.distributed:
        # Use distributed validation
        from Worker.distributed_validator import LocalDistributedValidator
        
        validator = LocalDistributedValidator(
            num_workers=args.workers,
            batch_size=args.batch_size,
            timeout=args.timeout
        )
        
        # Set up proxy filter
        proxy_filter = {}
        if args.revalidate:
            proxy_filter['older_than_minutes'] = args.minutes_old
        else:
            proxy_filter['status'] = 'untested'
        
        stats = validator.validate_proxies(proxy_filter, args.limit)
        
        print(f"\n📊 Distributed Validation Results:")
        print(f"   • Proxies tested: {stats['tested']}")
        print(f"   • Jobs processed: {stats['jobs']}")
        print(f"   • Workers used: {stats['workers']}")
        print(f"   • Duration: {stats['duration']} seconds")
        print(f"   • Speed: {stats['tested']/stats['duration']:.1f} proxies/second")
        
    else:
        # Use traditional single-threaded validation
        validator = ProxyValidator(
            timeout=args.timeout,
            max_workers=args.workers
        )
        
        if args.revalidate:
            stats = validator.revalidate_old_proxies(
                minutes_old=args.minutes_old,
                limit=args.limit
            )
        else:
            stats = validator.validate_untested_proxies(limit=args.limit)
        
        print(f"\n📊 Validation Results:")
        print(f"   • Proxies tested: {stats['tested']}")
        print(f"   • Working proxies: {stats['working']}")
        print(f"   • Records updated: {stats['updated']}")
        if stats['tested'] > 0:
            print(f"   • Success rate: {(stats['working']/stats['tested']*100):.1f}%")

def run_scheduler(args):
    """Run the automated scheduler."""
    print("📅 Starting proxy scheduler...")
    
    scheduler = ProxyScheduler()
    
    # Customize config if needed
    if args.scrape_interval:
        scheduler.config['scraping']['interval_hours'] = args.scrape_interval
    if args.validate_interval:
        scheduler.config['validation']['interval_hours'] = args.validate_interval
    
    try:
        thread = scheduler.start(run_immediate=args.immediate)
        
        print("\n📊 Scheduler is running. Press Ctrl+C to stop.")
        print("Next scheduled runs:")
        for job, next_run in scheduler.get_next_run_times().items():
            print(f"   • {job}: {next_run}")
        
        # Keep alive
        import time
        while True:
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping scheduler...")
        scheduler.stop()
        print("✅ Scheduler stopped successfully")

def show_stats(args):
    """Show database and job statistics."""
    print("📊 Proxy Database Statistics\n")
    
    try:
        client = SupabaseClient()
        supabase = client.get_client()
        
        # Proxy statistics
        print("🗄️ Proxy Counts:")
        
        # Total proxies
        total_result = supabase.table('proxies').select('*', count='exact').execute()
        total_count = total_result.count
        print(f"   • Total proxies: {total_count}")
        
        # Active proxies
        active_result = supabase.table('proxies').select('*', count='exact').eq('status', 'active').execute()
        active_count = active_result.count
        print(f"   • Active proxies: {active_count}")
        
        # Untested proxies
        untested_result = supabase.table('proxies').select('*', count='exact').eq('status', 'untested').execute()
        untested_count = untested_result.count
        print(f"   • Untested proxies: {untested_count}")
        
        # Working proxies
        working_result = supabase.table('proxies').select('*', count='exact').eq('is_working', True).execute()
        working_count = working_result.count
        print(f"   • Working proxies: {working_count}")
        
        # Success rate
        if total_count > 0:
            success_rate = (working_count / total_count) * 100
            print(f"   • Overall success rate: {success_rate:.1f}%")
        
        # Recent job statistics
        print("\n📈 Recent Job Statistics (24h):")
        scheduler = ProxyScheduler()
        job_stats = scheduler.get_job_stats(24)
        
        if job_stats:
            print(f"   • Total jobs: {job_stats['total_jobs']}")
            print(f"   • Completed: {job_stats['completed']}")
            print(f"   • Failed: {job_stats['failed']}")
            print(f"   • Running: {job_stats['running']}")
            print(f"   • Proxies found: {job_stats['total_proxies_found']}")
            print(f"   • Proxies added: {job_stats['total_proxies_added']}")
        
        # Proxy types breakdown
        print("\n🔧 Proxy Types:")
        types_result = supabase.rpc('get_proxy_type_counts').execute()
        if hasattr(types_result, 'data') and types_result.data:
            for type_stat in types_result.data:
                print(f"   • {type_stat['type']}: {type_stat['count']}")
        
    except Exception as e:
        print(f"❌ Error retrieving statistics: {str(e)}")

def debug_scrape(args):
    """Debug scraping for a specific site."""
    print(f"🔍 Debug scraping for site: {args.source}")
    
    # List available sources
    scraper = ProxyScraper(headless=False, delay=args.delay)  # Always visible for debugging
    available_sources = list(scraper.proxy_sources.keys())
    
    if args.source not in available_sources:
        print(f"❌ Invalid source. Available sources:")
        for i, source in enumerate(available_sources, 1):
            source_info = scraper.proxy_sources[source]
            print(f"   {i}. {source} ({source_info['method']}) - {source_info['url']}")
        return
    
    source_config = scraper.proxy_sources[args.source]
    print(f"🎯 Target: {source_config['url']}")
    print(f"📊 Method: {source_config['method']}")
    print(f"⏱️  Delay: {args.delay}s")
    print(f"🖥️  Browser: Visible (debug mode)")
    
    if args.pause:
        print("\n⏸️  Pausing after page load for manual inspection...")
    
    try:
        if source_config['method'] == 'selenium':
            # Table-based scraping with debug features
            proxies = scraper.debug_table_scraping(
                url=source_config['url'],
                table_selector=source_config.get('table_selector', '#proxylisttable'),
                source_name=args.source,
                pause_after_load=args.pause,
                take_screenshot=args.screenshot
            )
        else:
            # API-based scraping
            proxies = scraper.scrape_api_source(
                url=source_config['url'],
                source_name=args.source
            )
        
        print(f"\n📊 Debug Results:")
        print(f"   • Proxies found: {len(proxies)}")
        
        if proxies and args.show_sample:
            print(f"\n📋 Sample proxies (first 5):")
            for i, proxy in enumerate(proxies[:5], 1):
                print(f"   {i}. {proxy['ip']}:{proxy['port']} ({proxy.get('type', 'unknown')}) [{proxy.get('country', 'unknown')}]")
        
        if not args.no_save and proxies:
            saved = scraper.save_proxies_to_database(proxies, silent=True)
        elif args.no_save:
            print("   • Skipped database save (--no-save)")
            
    except Exception as e:
        print(f"❌ Debug scraping failed: {str(e)}")
        import traceback
        if args.verbose:
            traceback.print_exc()
    
    finally:
        # Keep browser open if requested
        if args.keep_open and hasattr(scraper, 'driver') and scraper.driver:
            input("\n⏸️  Browser will stay open. Press Enter to close...")
        
        # Clean up
        if hasattr(scraper, 'driver') and scraper.driver:
            scraper.driver.quit()

def handle_ai_config(args):
    """Handle AI configuration management commands."""
    from Tools.gemini_client import GeminiConfigGenerator
    from Worker.proxy_scraper import ProxyScraper
    
    if not args.ai_command:
        print("❌ No AI command specified. Use --help for available commands.")
        return
    
    try:
        supabase_client = SupabaseClient()
        
        if args.ai_command == 'generate':
            print(f"🤖 Generating AI configuration for: {args.name}")
            print(f"🌐 URL: {args.url}")
            
            # Initialize Gemini client and scraper for enhanced analysis
            gemini_client = GeminiConfigGenerator()
            scraper = ProxyScraper(headless=True)  # Use headless for analysis
            
            try:
                # Setup driver for analysis
                if not scraper.driver:
                    scraper.driver = scraper.setup_driver()
                
                print("🔍 Analyzing website with Selenium...")
                # Use enhanced analysis with Selenium
                analysis = gemini_client.analyze_website_structure_with_driver(args.url, scraper.driver)
                
                print("🧠 Generating configuration with Gemini AI...")
                # Generate the configuration using the enhanced analysis
                prompt = gemini_client.generate_config_prompt(args.url, analysis, args.name)
                response = gemini_client.model.generate_content(prompt)
                
                if not response.text:
                    raise Exception("Empty response from Gemini API")
                
                # Parse JSON response
                import json
                try:
                    response_text = response.text
                    if '```json' in response_text:
                        json_start = response_text.find('```json') + 7
                        json_end = response_text.find('```', json_start)
                        response_text = response_text[json_start:json_end]
                    elif '```' in response_text:
                        json_start = response_text.find('```') + 3
                        json_end = response_text.find('```', json_start)
                        response_text = response_text[json_start:json_end]
                    
                    config_data = json.loads(response_text.strip())
                    confidence = config_data.get('confidence_score', 0.5)
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON parsing error: {e}")
                    print(f"Response: {response.text}")
                    raise Exception(f"Failed to parse AI response as JSON: {e}")
                
                # Create a config dict (simplified from the old ProxySourceConfig object)
                config = {
                    'name': args.name,
                    'url': args.url,
                    'method': config_data.get('method', 'selenium'),
                    'table_selector': config_data.get('table_selector'),
                    'ip_column': config_data.get('ip_column'),
                    'port_column': config_data.get('port_column'),
                    'country_column': config_data.get('country_column'),
                    'anonymity_column': config_data.get('anonymity_column'),
                    'api_format': config_data.get('api_format'),
                    'api_response_path': config_data.get('api_response_path'),
                    'json_ip_field': config_data.get('json_ip_field'),
                    'json_port_field': config_data.get('json_port_field'),
                    'json_country_field': config_data.get('json_country_field'),
                    'json_anonymity_field': config_data.get('json_anonymity_field'),
                    'has_pagination': config_data.get('has_pagination', False),
                    'pagination_selector': config_data.get('pagination_selector'),
                    'request_delay_seconds': config_data.get('request_delay_seconds', 2),
                    'expected_min_proxies': config_data.get('expected_min_proxies', 10)
                }
                
            finally:
                scraper.cleanup_driver()
            
            print(f"\n📊 Generated Configuration:")
            print(f"   • Method: {config['method']}")
            print(f"   • Table Selector: {config['table_selector']}")
            print(f"   • IP Column: {config['ip_column']}")
            print(f"   • Port Column: {config['port_column']}")
            print(f"   • Country Column: {config['country_column']}")
            print(f"   • Anonymity Column: {config['anonymity_column']}")
            print(f"   • Expected Min Proxies: {config['expected_min_proxies']}")
            print(f"   • Confidence Score: {confidence:.2f}")
            
            if args.save:
                success = supabase_client.save_proxy_source_config(
                    config, 
                    ai_generated=True, 
                    ai_model='gemini-2.5-flash',
                    confidence_score=confidence
                )
                
                if success:
                    print("✅ Configuration saved to database!")
                else:
                    print("❌ Failed to save configuration")
            
            if args.test:
                print("\n🧪 Testing generated configuration...")
                test_scraper = ProxyScraper(headless=False)
                
                try:
                    if config['method'] == 'selenium':
                        proxies = test_scraper.scrape_table_source(config['name'], config)
                    else:
                        proxies = test_scraper.scrape_api_source(config['name'], config)
                    
                    print(f"📊 Test Results: Found {len(proxies)} proxies")
                    if proxies:
                        print("✅ Configuration appears to be working!")
                        # Show sample
                        for i, proxy in enumerate(proxies[:3], 1):
                            print(f"   {i}. {proxy['ip']}:{proxy['port']} ({proxy.get('type', 'unknown')})")
                    else:
                        print("⚠️ No proxies found - configuration may need adjustment")
                        
                except Exception as e:
                    print(f"❌ Test failed: {str(e)}")
                finally:
                    test_scraper.cleanup_driver()
        
        elif args.ai_command == 'refresh':
            print(f"🔄 Refreshing configuration for: {args.source}")
            
            # Check if source exists
            source = supabase_client.get_proxy_source(args.source)
            if not source:
                print(f"❌ Source '{args.source}' not found in database")
                return
            
            # Check if refresh is needed (unless forced)
            if not args.force:
                needs_refresh, reason = supabase_client.check_if_needs_ai_refresh(args.source)
                if not needs_refresh:
                    print(f"ℹ️ Source '{args.source}' doesn't need refresh. Use --force to refresh anyway.")
                    return
            
            # Initialize scraper and trigger refresh
            from Worker.proxy_scraper import ProxyScraper
            scraper = ProxyScraper()
            refreshed = scraper._check_and_refresh_config(args.source)
            
            if refreshed:
                print("✅ Configuration refreshed successfully!")
                
                if args.test:
                    print("\n🧪 Testing refreshed configuration...")
                    # Test the refreshed config...
                    
            else:
                print("❌ Failed to refresh configuration")
        
        elif args.ai_command == 'list':
            print("📋 Proxy Source Configurations:")
            
            sources = supabase_client.get_proxy_sources(active_only=False)
            
            if args.ai_only:
                sources = [s for s in sources if s.get('ai_generated', False)]
            
            if not sources:
                print("   No sources found.")
                return
            
            for source in sources:
                ai_indicator = "🤖" if source.get('ai_generated', False) else "👤"
                status = "✅" if source.get('is_active', True) else "❌"
                print(f"   {status} {ai_indicator} {source['name']}")
                print(f"      URL: {source['url']}")
                print(f"      Method: {source.get('method', 'unknown')}")
                
                if source.get('ai_generated'):
                    print(f"      AI Confidence: {source.get('ai_confidence_score', 0):.2f}")
                    print(f"      Failures: {source.get('consecutive_failures', 0)}")
                
                if args.show_details:
                    print(f"      Table Selector: {source.get('table_selector', 'N/A')}")
                    print(f"      Columns: IP={source.get('ip_column')}, Port={source.get('port_column')}")
                    print(f"      Expected Proxies: {source.get('expected_min_proxies', 'N/A')}")
                
                print()
        
        elif args.ai_command == 'stats':
            print("📊 AI Configuration Statistics:")
            
            # Get all sources
            sources = supabase_client.get_proxy_sources(active_only=False)
            ai_sources = [s for s in sources if s.get('ai_generated', False)]
            
            print(f"   • Total Sources: {len(sources)}")
            print(f"   • AI-Generated: {len(ai_sources)}")
            print(f"   • Manual: {len(sources) - len(ai_sources)}")
            
            if ai_sources:
                avg_confidence = sum(s.get('ai_confidence_score', 0) for s in ai_sources) / len(ai_sources)
                print(f"   • Average AI Confidence: {avg_confidence:.2f}")
                
                failing_sources = [s for s in ai_sources if s.get('consecutive_failures', 0) > 0]
                print(f"   • Sources with Failures: {len(failing_sources)}")
            
            if args.history:
                print("\n📈 Recent AI Generations:")
                # Query ai_config_generations table for recent activity
                client = supabase_client.get_client()
                result = client.table('ai_config_generations').select('*').order('created_at', desc=True).limit(10).execute()
                
                if result.data:
                    for gen in result.data:
                        print(f"   • {gen['created_at'][:10]} - {gen.get('trigger_reason', 'unknown')} - Confidence: {gen.get('confidence_score', 0):.2f}")
                else:
                    print("   No generation history found.")
        
    except Exception as e:
        print(f"❌ AI configuration error: {str(e)}")
        import traceback
        traceback.print_exc()

def test_connection(args):
    """Test database connection."""
    print("🔍 Testing Supabase connection...")
    
    try:
        client = SupabaseClient()
        
        # Simple connection test that doesn't rely on specific tables
        supabase = client.get_client()
        
        # Test basic connectivity - try a simple operation
        print("✅ Basic connection successful!")
        
        # Test if enhanced schema is applied
        try:
            result = supabase.table('proxy_sources').select('*', count='exact').limit(1).execute()
            print(f"✅ Enhanced schema detected! Found {result.count} proxy sources configured")
            
            # Show source configurations
            if result.count > 0:
                sources = client.get_proxy_sources(active_only=False)
                print(f"📊 Configured sources:")
                for source in sources[:3]:  # Show first 3
                    ai_indicator = "🤖" if source.get('ai_generated', False) else "👤"
                    print(f"   {ai_indicator} {source['name']} ({source.get('method', 'unknown')})")
        except Exception as e:
            if 'does not exist' in str(e):
                print("⚠️ Enhanced schema not yet applied")
                print("📝 Please run the database_schema.sql in your Supabase SQL editor")
                print("🔗 Go to: Supabase Dashboard → SQL Editor → New Query")
            else:
                print(f"⚠️ Schema check error: {str(e)}")
        
        # Test if basic proxies table exists
        try:
            result = supabase.table('proxies').select('*', count='exact').limit(1).execute()
            print(f"📊 Found {result.count} proxies in database")
        except Exception as e:
            if 'does not exist' in str(e):
                print("⚠️ Basic proxies table not found")
                print("📝 Please run the complete database_schema.sql first")
            else:
                print(f"⚠️ Proxies table error: {str(e)}")
                
    except Exception as e:
        print(f"❌ Connection error: {str(e)}")
        print("🔧 Check your .env file:")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY")

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Proxy Scraper Worker - Command line interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scrape --delay 3 --headless
  %(prog)s scrape --sources free-proxy-list ssl-proxies --no-headless
  %(prog)s validate --limit 100 --workers 30
              %(prog)s validate --revalidate --minutes-old 120
  %(prog)s debug free-proxy-list --pause --screenshot --show-sample
  %(prog)s debug ssl-proxies --keep-open --no-save --verbose
  %(prog)s ai-config generate my-new-source https://example.com/proxies --save --test
  # AI will auto-detect pagination and generate XPath/CSS selectors
  %(prog)s ai-config refresh free-proxy-list --force --test
  %(prog)s ai-config list --ai-only --show-details
  %(prog)s ai-config stats --history
  %(prog)s schedule --immediate --scrape-interval 8
  %(prog)s stats
  %(prog)s test
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Scraping command
    scrape_parser = subparsers.add_parser('scrape', help='Run proxy scraping')
    scrape_parser.add_argument('--sources', nargs='+', help='Specific source names to scrape (e.g. --sources free-proxy-list ssl-proxies)')
    scrape_parser.add_argument('--delay', type=int, default=2, help='Delay between requests (seconds)')
    scrape_parser.add_argument('--headless', action='store_true', default=True, help='Run browser in headless mode')
    scrape_parser.add_argument('--no-headless', dest='headless', action='store_false', help='Run browser with GUI')
    
    # Validation command
    validate_parser = subparsers.add_parser('validate', help='Run proxy validation')
    validate_parser.add_argument('--limit', type=int, default=100, help='Maximum proxies to validate')
    validate_parser.add_argument('--timeout', type=int, default=10, help='Request timeout (seconds)')
    validate_parser.add_argument('--workers', type=int, default=30, help='Number of worker threads')
    validate_parser.add_argument('--revalidate', action='store_true', help='Revalidate old proxies instead of untested')
    validate_parser.add_argument('--minutes-old', type=int, default=60, help='Consider proxies older than N minutes (for revalidation)')
    validate_parser.add_argument('--distributed', action='store_true', help='Use distributed validation with multiple workers')
    validate_parser.add_argument('--batch-size', type=int, default=50, help='Batch size for distributed validation')
    
    # Debug command
    debug_parser = subparsers.add_parser('debug', help='Debug scraping for specific site')
    debug_parser.add_argument('source', help='Source name to debug (e.g., free-proxy-list, ssl-proxies)')
    debug_parser.add_argument('--delay', type=int, default=5, help='Delay between requests (seconds)')
    debug_parser.add_argument('--pause', action='store_true', help='Pause after page load for manual inspection')
    debug_parser.add_argument('--screenshot', action='store_true', help='Take screenshot of the page')
    debug_parser.add_argument('--show-sample', action='store_true', help='Show sample of found proxies')
    debug_parser.add_argument('--no-save', action='store_true', help='Skip saving to database')
    debug_parser.add_argument('--keep-open', action='store_true', help='Keep browser open after scraping')
    debug_parser.add_argument('--verbose', action='store_true', help='Show detailed error traces')
    
    # AI Configuration Management
    ai_parser = subparsers.add_parser('ai-config', help='Manage AI-generated configurations')
    ai_subparsers = ai_parser.add_subparsers(dest='ai_command', help='AI configuration commands')
    
    # Generate configuration
    generate_parser = ai_subparsers.add_parser('generate', help='Generate configuration for a new source')
    generate_parser.add_argument('name', help='Name for the new proxy source')
    generate_parser.add_argument('url', help='URL of the proxy source website')
    generate_parser.add_argument('--save', action='store_true', help='Save generated configuration to database')
    generate_parser.add_argument('--test', action='store_true', help='Test the generated configuration')
    
    # Refresh existing source
    refresh_parser = ai_subparsers.add_parser('refresh', help='Refresh configuration for existing source')
    refresh_parser.add_argument('source', help='Name of existing source to refresh')
    refresh_parser.add_argument('--force', action='store_true', help='Force refresh even if not needed')
    refresh_parser.add_argument('--test', action='store_true', help='Test the refreshed configuration')
    
    # List configurations
    list_parser = ai_subparsers.add_parser('list', help='List current source configurations')
    list_parser.add_argument('--ai-only', action='store_true', help='Show only AI-generated configurations')
    list_parser.add_argument('--show-details', action='store_true', help='Show detailed configuration')
    
    # Configuration stats
    ai_stats_parser = ai_subparsers.add_parser('stats', help='Show AI configuration statistics')
    ai_stats_parser.add_argument('--history', action='store_true', help='Show generation history')
    
    # Scheduler command
    schedule_parser = subparsers.add_parser('schedule', help='Run automated scheduler')
    schedule_parser.add_argument('--immediate', action='store_true', help='Run jobs immediately before starting schedule')
    schedule_parser.add_argument('--scrape-interval', type=int, help='Scraping interval in hours')
    schedule_parser.add_argument('--validate-interval', type=int, help='Validation interval in hours')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test database connection')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    print(f"🚀 Proxy Scraper Worker - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        if args.command == 'scrape':
            run_scraping(args)
        elif args.command == 'validate':
            run_validation(args)
        elif args.command == 'debug':
            debug_scrape(args)
        elif args.command == 'ai-config':
            handle_ai_config(args)
        elif args.command == 'schedule':
            run_scheduler(args)
        elif args.command == 'stats':
            show_stats(args)
        elif args.command == 'test':
            test_connection(args)
        
        print("\n✅ Command completed successfully!")
        return 0
        
    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main()) 