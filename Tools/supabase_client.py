import os
import json
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timezone

class SupabaseClient:
    """
    Enhanced Supabase client for proxy scraper with dynamic configuration support.
    Handles proxy data storage and AI-generated source configurations.
    """
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_ROLE_KEY) must be set in environment variables")
        
        self.client = None
    
    def get_client(self) -> Client:
        """Get or create Supabase client instance."""
        if self.client is None:
            self.client = create_client(self.url, self.key)
        return self.client
    
    def test_connection(self) -> bool:
        """
        Test connection to Supabase.
        
        Returns:
            bool: True if connection successful
        """
        try:
            client = self.get_client()
            # Test with a simple query
            result = client.table('proxies').select('count').limit(1).execute()
            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False
    
    # ============================================================================
    # Enhanced Proxy Source Configuration Management
    # ============================================================================
    
    def get_proxy_sources(self, active_only: bool = True) -> List[Dict]:
        """
        Get all proxy source configurations.
        
        Args:
            active_only (bool): Only return active sources
            
        Returns:
            List[Dict]: List of proxy source configurations
        """
        try:
            client = self.get_client()
            query = client.table('proxy_sources').select('*')
            
            if active_only:
                query = query.eq('is_active', True)
            
            result = query.order('name').execute()
            return result.data
            
        except Exception as e:
            print(f"❌ Failed to get proxy sources: {str(e)}")
            return []
    
    def get_proxy_source(self, source_name: str) -> Optional[Dict]:
        """
        Get a specific proxy source configuration.
        
        Args:
            source_name (str): Name of the source
            
        Returns:
            Optional[Dict]: Source configuration or None if not found
        """
        try:
            client = self.get_client()
            result = client.table('proxy_sources').select('*').eq('name', source_name).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            print(f"❌ Failed to get proxy source '{source_name}': {str(e)}")
            return None
    
    def save_proxy_source_config(self, config: Dict, ai_generated: bool = False, 
                                ai_model: str = None, confidence_score: float = None) -> bool:
        """
        Save or update a proxy source configuration.
        
        Args:
            config (Dict): Source configuration
            ai_generated (bool): Whether this was AI-generated
            ai_model (str): AI model used for generation
            confidence_score (float): AI confidence score
            
        Returns:
            bool: True if successful
        """
        try:
            client = self.get_client()
            
            # Prepare the data
            source_data = {
                'name': config['name'],
                'url': config['url'],
                'method': config.get('method', 'selenium'),
                'table_selector': config.get('table_selector'),
                'ip_column': config.get('ip_column'),
                'port_column': config.get('port_column'),
                'country_column': config.get('country_column'),
                'anonymity_column': config.get('anonymity_column'),
                'api_format': config.get('api_format'),
                'api_response_path': config.get('api_response_path'),
                'json_ip_field': config.get('json_ip_field'),
                'json_port_field': config.get('json_port_field'),
                'json_country_field': config.get('json_country_field'),
                'json_anonymity_field': config.get('json_anonymity_field'),
                'has_pagination': config.get('has_pagination', False),
                'pagination_selector': config.get('pagination_selector'),
                'request_delay_seconds': config.get('request_delay_seconds', 2),
                'expected_min_proxies': config.get('expected_min_proxies', 10),
                'ai_generated': ai_generated,
                'ai_model_used': ai_model,
                'ai_confidence_score': confidence_score,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            if ai_generated:
                source_data['ai_generation_date'] = datetime.now(timezone.utc).isoformat()
            
            # Try to update first, then insert if not exists
            try:
                result = client.table('proxy_sources').upsert(source_data).execute()
                
                if not result.data:
                    print(f"⚠️ No data returned from upsert for source '{config['name']}'")
                    return False
                
                print(f"✅ Saved proxy source config: {config['name']}")
                return True
                
            except Exception as db_error:
                # If JSON field columns don't exist, try without them
                if 'json_' in str(db_error):
                    print(f"⚠️ JSON field columns not found, saving without them...")
                    source_data_minimal = {k: v for k, v in source_data.items() 
                                         if not k.startswith('json_')}
                    
                    result = client.table('proxy_sources').upsert(source_data_minimal).execute()
                    
                    if not result.data:
                        print(f"⚠️ No data returned from minimal upsert for source '{config['name']}'")
                        return False
                    
                    print(f"✅ Saved proxy source config (without JSON fields): {config['name']}")
                    return True
                else:
                    raise db_error
            
        except Exception as e:
            print(f"❌ Failed to save proxy source config: {str(e)}")
            return False
    
    def check_if_needs_ai_refresh(self, source_name: str) -> Tuple[bool, str]:
        """
        Check if a proxy source needs AI configuration refresh.
        
        Args:
            source_name (str): Name of the source
            
        Returns:
            Tuple[bool, str]: (needs_refresh, reason)
        """
        try:
            client = self.get_client()
            
            # Get source info
            source = self.get_proxy_source(source_name)
            if not source:
                return True, "source_not_found"
            
            # Check using database function
            result = client.rpc('needs_ai_refresh', {'source_uuid': source['id']}).execute()
            
            if result.data and result.data[0]:
                if source.get('consecutive_failures', 0) >= source.get('max_failures_before_ai_refresh', 3):
                    return True, "consecutive_failures"
                else:
                    return True, "no_recent_success"
            
            return False, "no_refresh_needed"
            
        except Exception as e:
            print(f"❌ Failed to check AI refresh need: {str(e)}")
            return False, "check_failed"
    
    def log_ai_config_generation(self, source_id: str, trigger_reason: str, 
                                ai_model: str, prompt_used: str, website_analysis: str,
                                generated_config: Dict, confidence_score: float) -> bool:
        """
        Log an AI configuration generation attempt.
        
        Args:
            source_id (str): Source UUID
            trigger_reason (str): Why AI generation was triggered
            ai_model (str): AI model used
            prompt_used (str): The prompt sent to AI
            website_analysis (str): Website analysis results
            generated_config (Dict): Generated configuration
            confidence_score (float): AI confidence score
            
        Returns:
            bool: True if logged successfully
        """
        try:
            client = self.get_client()
            
            log_data = {
                'source_id': source_id,
                'trigger_reason': trigger_reason,
                'ai_model': ai_model,
                'prompt_used': prompt_used,
                'website_analysis': website_analysis,
                'generated_config': json.dumps(generated_config),
                'confidence_score': confidence_score,
                'applied': False  # Will be updated when config is applied
            }
            
            result = client.table('ai_config_generations').insert(log_data).execute()
            
            if result.data:
                print(f"✅ Logged AI config generation for source {source_id}")
                return True
            else:
                print(f"⚠️ No data returned from AI config generation log")
                return False
                
        except Exception as e:
            print(f"❌ Failed to log AI config generation: {str(e)}")
            return False
    
    def update_source_scrape_results(self, source_name: str, success: bool, 
                                   proxies_found: int = 0) -> bool:
        """
        Update source statistics after a scraping attempt.
        
        Args:
            source_name (str): Name of the source
            success (bool): Whether scraping was successful
            proxies_found (int): Number of proxies found
            
        Returns:
            bool: True if updated successfully
        """
        try:
            client = self.get_client()
            
            source = self.get_proxy_source(source_name)
            if not source:
                print(f"⚠️ Source '{source_name}' not found for stats update")
                return False
            
            update_data = {
                'last_scraped': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            if success:
                update_data['last_successful_scrape'] = datetime.now(timezone.utc).isoformat()
                update_data['total_proxies_found'] = (source.get('total_proxies_found', 0) or 0) + proxies_found
                update_data['consecutive_failures'] = 0
            else:
                update_data['consecutive_failures'] = (source.get('consecutive_failures', 0) or 0) + 1
            
            result = client.table('proxy_sources').update(update_data).eq('name', source_name).execute()
            
            if result.data:
                return True
            else:
                print(f"⚠️ No data returned from source stats update")
                return False
                
        except Exception as e:
            print(f"❌ Failed to update source stats: {str(e)}")
            return False

    # ============================================================================
    # Original Proxy Data Methods (Enhanced)
    # ============================================================================
    
    def insert_proxy(self, proxy_data: dict, silent: bool = False) -> dict:
        """
        Insert proxy data into the proxies table.
        
        Args:
            proxy_data (dict): Dictionary containing proxy information
            silent (bool): Whether to suppress duplicate error logging
            
        Returns:
            dict: Response from Supabase
        """
        try:
            client = self.get_client()
            result = client.table('proxies').insert(proxy_data).execute()
            
            if not silent:
                print(f"✅ Proxy inserted successfully: {proxy_data.get('ip', 'Unknown IP')}")
            return result
            
        except Exception as e:
            error_msg = str(e)
            # Check if it's a duplicate key error
            if 'duplicate key' in error_msg.lower() or 'unique constraint' in error_msg.lower():
                if not silent:
                    # Only print for non-duplicate errors
                    pass  # Skip duplicate logging when silent=True
                raise Exception("duplicate")
            else:
                if not silent:
                    print(f"❌ Failed to insert proxy: {error_msg}")
                raise
    
    def get_proxies(self, limit: int = 100, country: str = None, proxy_type: str = None, 
                    sort_by_last_checked: bool = False) -> List[Dict]:
        """
        Get proxies from the database with optional filtering.
        
        Args:
            limit (int): Maximum number of proxies to return
            country (str): Filter by country code
            proxy_type (str): Filter by proxy type
            sort_by_last_checked (bool): If True, sort by last_checked ASC (oldest first)
            
        Returns:
            List[Dict]: List of proxy dictionaries
        """
        try:
            client = self.get_client()
            query = client.table('proxies').select('*')
            
            if country:
                query = query.eq('country', country)
            if proxy_type:
                query = query.eq('type', proxy_type)
            
            query = query.eq('status', 'active')
            
            # Sort by last_checked if requested (oldest first)
            if sort_by_last_checked:
                query = query.order('last_checked', desc=False)
            
            result = query.limit(limit).execute()
            return result.data
            
        except Exception as e:
            print(f"❌ Failed to get proxies: {str(e)}")
            return []
    
    def update_proxy_status(self, proxy_id: str, status: str, response_time_ms: int = None) -> bool:
        """
        Update proxy status and performance metrics.
        
        Args:
            proxy_id (str): Proxy UUID
            status (str): New status (active, inactive, testing)
            response_time_ms (int): Response time in milliseconds
            
        Returns:
            bool: True if update successful
        """
        try:
            client = self.get_client()
            update_data = {
                'status': status,
                'last_checked': datetime.now(timezone.utc).isoformat()
            }
            
            if response_time_ms is not None:
                update_data['response_time_ms'] = response_time_ms
            
            result = client.table('proxies').update(update_data).eq('id', proxy_id).execute()
            return len(result.data) > 0
            
        except Exception as e:
            print(f"❌ Failed to update proxy status: {str(e)}")
            return False


# Example usage
if __name__ == "__main__":
    # Initialize Supabase client
    supabase_client = SupabaseClient()
    
    # Test connection
    if supabase_client.test_connection():
        print("Supabase client is ready to use!")
    else:
        print("Please check your Supabase credentials in the .env file") 