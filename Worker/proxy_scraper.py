import time
import re
import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
import os
import sys
import json
from loguru import logger

# Add the parent directory to the path so we can import from Tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Tools.supabase_client import SupabaseClient
from Tools.gemini_client import GeminiConfigGenerator

class ProxyScraper:
    """
    Enhanced proxy scraper with dynamic AI-powered configurations.
    Loads scraping rules from Supabase and uses AI to generate new ones when needed.
    """
    
    def __init__(self, headless: bool = True, delay: int = 2):
        """
        Initialize the proxy scraper.
        
        Args:
            headless (bool): Run browser in headless mode
            delay (int): Delay between requests in seconds
        """
        self.headless = headless
        self.delay = delay
        self.driver = None
        self.supabase_client = SupabaseClient()
        self.gemini_client = None  # Initialize lazily when needed
        
        # Load dynamic configurations from database
        self.proxy_sources = self._load_dynamic_configurations()
        
        logger.info(f"ProxyScraper initialized with {len(self.proxy_sources)} sources")
        
        # Common user agents to rotate
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
    
    def _load_dynamic_configurations(self) -> Dict[str, Dict]:
        """
        Load proxy source configurations from Supabase database.
        
        Returns:
            Dict[str, Dict]: Source configurations keyed by source name
        """
        try:
            sources_data = self.supabase_client.get_proxy_sources(active_only=True)
            
            if not sources_data:
                logger.warning("No proxy sources found in database, using fallback configs")
                return self._get_fallback_configurations()
            
            # Convert list to dict keyed by name
            sources_dict = {}
            for source in sources_data:
                source_name = source['name']
                
                # Convert database record to scraper format
                config = {
                    'id': source['id'],
                    'url': source['url'],
                    'method': source.get('method', 'selenium'),
                    'table_selector': source.get('table_selector'),
                    'ip_column': source.get('ip_column', 0),
                    'port_column': source.get('port_column', 1),
                    'country_column': source.get('country_column'),
                    'anonymity_column': source.get('anonymity_column'),
                    'api_format': source.get('api_format'),
                    'api_response_path': source.get('api_response_path'),
                                    'has_pagination': source.get('has_pagination', False),
                'pagination_selector': source.get('pagination_selector'),
                'pagination_type': source.get('pagination_type', 'click'),
                'max_pages': source.get('max_pages', 10),
                    'request_delay_seconds': source.get('request_delay_seconds', 2),
                    'expected_min_proxies': source.get('expected_min_proxies', 10),
                    'ai_generated': source.get('ai_generated', False),
                    'ai_confidence_score': source.get('ai_confidence_score'),
                    'consecutive_failures': source.get('consecutive_failures', 0)
                }
                
                sources_dict[source_name] = config
                
            logger.info(f"Loaded {len(sources_dict)} dynamic configurations from database")
            return sources_dict
            
        except Exception as e:
            logger.error(f"Failed to load dynamic configurations: {str(e)}")
            return self._get_fallback_configurations()
    
    def _get_fallback_configurations(self) -> Dict[str, Dict]:
        """Get hardcoded fallback configurations if database fails."""
        return {
            'free-proxy-list': {
                'url': 'https://free-proxy-list.net/',
                'method': 'selenium',
                'table_selector': '.table-striped',
                'ip_column': 0,
                'port_column': 1,
                'country_column': 2,
                'anonymity_column': 4,
                'has_pagination': False,
                'pagination_type': 'click',
                'max_pages': 10,
                'request_delay_seconds': 3,
                'expected_min_proxies': 50
            }
        }
    
    def _initialize_gemini_client(self):
        """Initialize Gemini client lazily when needed."""
        if self.gemini_client is None:
            try:
                self.gemini_client = GeminiConfigGenerator()
                logger.info("✅ Gemini AI client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Gemini client: {str(e)}")
                self.gemini_client = None
    
    def _check_and_refresh_config(self, source_name: str) -> bool:
        """
        Check if a source configuration needs AI refresh and update it if needed.
        
        Args:
            source_name (str): Name of the source to check
            
        Returns:
            bool: True if configuration was refreshed
        """
        try:
            # Check if refresh is needed
            needs_refresh, reason = self.supabase_client.check_if_needs_ai_refresh(source_name)
            
            if not needs_refresh:
                return False
            
            logger.info(f"🔄 Source '{source_name}' needs AI refresh. Reason: {reason}")
            
            # Initialize Gemini client if needed
            self._initialize_gemini_client()
            if not self.gemini_client:
                logger.error("❌ Cannot refresh config: Gemini client not available")
                return False
            
            # Get current source info
            current_source = self.supabase_client.get_proxy_source(source_name)
            if not current_source:
                logger.error(f"❌ Source '{source_name}' not found in database")
                return False
            
            # Generate new configuration with AI using our existing driver
            url = current_source['url']
            
            # Ensure we have a driver for analysis
            if not self.driver:
                self.setup_driver()
            
            # Use the enhanced analysis method with our driver
            analysis = self.gemini_client.analyze_website_structure_with_driver(url, self.driver)
            
            # Generate the configuration using the enhanced analysis
            prompt = self.gemini_client.generate_config_prompt(url, analysis, source_name)
            response = self.gemini_client.model.generate_content(prompt)
            
            if not response.text:
                raise Exception("Empty response from Gemini API")
            
            # Parse JSON response
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
                logger.error(f"⚠️ JSON parsing error: {e}")
                logger.error(f"Response: {response.text}")
                raise Exception(f"Failed to parse AI response as JSON: {e}")
            
            # Create a simplified config object (just the dict we need)
            config = {
                'name': source_name,
                'url': url,
                'method': config_data.get('method', 'selenium'),
                'table_selector': config_data.get('table_selector'),
                'ip_column': config_data.get('ip_column'),
                'port_column': config_data.get('port_column'),
                'country_column': config_data.get('country_column'),
                'anonymity_column': config_data.get('anonymity_column'),
                'api_format': config_data.get('api_format'),
                'api_response_path': config_data.get('api_response_path'),
                'has_pagination': config_data.get('has_pagination', False),
                'pagination_selector': config_data.get('pagination_selector'),
                'pagination_type': config_data.get('pagination_type', 'click'),
                'max_pages': config_data.get('max_pages', 10),
                'request_delay_seconds': config_data.get('request_delay_seconds', 2),
                'expected_min_proxies': config_data.get('expected_min_proxies', 10)
            }
            
            # Log the AI generation attempt
            self.supabase_client.log_ai_config_generation(
                source_id=current_source['id'],
                trigger_reason=reason,
                ai_model='gemini-2.5-flash',
                prompt_used=f"Generated config for {source_name}",
                website_analysis=analysis,
                generated_config=config,
                confidence_score=confidence
            )
            
            # The config is already in the right format (dict)
            config_dict = config
            
            success = self.supabase_client.save_proxy_source_config(
                config_dict, 
                ai_generated=True, 
                ai_model='gemini-1.5-flash',
                confidence_score=confidence
            )
            
            if success:
                # Update our local configuration
                self.proxy_sources[source_name] = config_dict
                logger.info(f"✅ Successfully refreshed config for '{source_name}' with AI")
                return True
            else:
                logger.error(f"❌ Failed to save AI-generated config for '{source_name}'")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error refreshing config for '{source_name}': {str(e)}")
            return False
    
    def cleanup_driver(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def setup_driver(self) -> webdriver.Chrome:
        """
        Set up Chrome WebDriver with optimal settings.
        
        Returns:
            webdriver.Chrome: Configured Chrome driver
        """
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Performance and stealth options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")
            
            # Random user agent
            user_agent = random.choice(self.user_agents)
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Set up the service - prefer system ChromeDriver, fallback to WebDriverManager
            try:
                # First try to use system ChromeDriver (installed via Homebrew)
                import shutil
                system_chromedriver = shutil.which('chromedriver')
                
                if system_chromedriver:
                    print(f"📍 Using system ChromeDriver: {system_chromedriver}")
                    service = Service(system_chromedriver)
                else:
                    print("🔄 System ChromeDriver not found, using WebDriverManager...")
                    driver_path = ChromeDriverManager().install()
                    print(f"📍 Downloaded ChromeDriver: {driver_path}")
                    
                    # Verify the driver path exists and is executable
                    if not os.path.exists(driver_path):
                        raise Exception(f"ChromeDriver not found at {driver_path}")
                    
                    # Make sure it's executable
                    os.chmod(driver_path, 0o755)
                    service = Service(driver_path)
                
            except Exception as e:
                print(f"⚠️ ChromeDriver setup failed: {str(e)}")
                raise Exception("Please install ChromeDriver: 'brew install chromedriver' or ensure Chrome is installed")
            
            # Create driver
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ Chrome WebDriver initialized successfully")
            return driver
            
        except Exception as e:
            print(f"❌ Failed to initialize WebDriver: {str(e)}")
            print("💡 Try installing Chrome manually or check if Chrome is properly installed")
            raise
    
    def scrape_proxies(self, sources: List[str] = None, refresh_configs: bool = True) -> List[Dict]:
        """
        Scrape proxies from specified sources with AI-powered config refresh.
        
        Args:
            sources (List[str]): List of source names to scrape (None for all)
            refresh_configs (bool): Whether to check and refresh configs with AI
            
        Returns:
            List[Dict]: List of scraped proxy dictionaries
        """
        if sources is None:
            sources = list(self.proxy_sources.keys())
        
        all_proxies = []
        
        for source_name in sources:
            if source_name not in self.proxy_sources:
                logger.warning(f"⚠️ Unknown source: {source_name}")
                continue
            
            logger.info(f"📡 Scraping from source: {source_name}")
            
            # Check and refresh configuration if needed
            if refresh_configs:
                self._check_and_refresh_config(source_name)
            
            source_config = self.proxy_sources[source_name]
            proxies = []
            
            try:
                if source_config['method'] == 'selenium':
                    proxies = self.scrape_table_source(source_name, source_config, update_stats=False)
                elif source_config['method'] == 'api':
                    proxies = self.scrape_api_source(source_name, source_config, update_stats=False)
                else:
                    logger.warning(f"⚠️ Unknown method '{source_config['method']}' for {source_name}")
                
                # Update source statistics
                success = len(proxies) > 0
                self.supabase_client.update_source_scrape_results(
                    source_name, success, len(proxies)
                )
                
                if proxies:
                    logger.info(f"✅ Found {len(proxies)} proxies from {source_name}")
                    all_proxies.extend(proxies)
                else:
                    logger.warning(f"⚠️ No proxies found from {source_name}")
                    
            except Exception as e:
                logger.error(f"❌ Error scraping {source_name}: {str(e)}")
                # Update failure statistics
                self.supabase_client.update_source_scrape_results(source_name, False, 0)
        
        # Remove duplicates
        unique_proxies = self.remove_duplicates(all_proxies)
        logger.info(f"📊 Total unique proxies: {len(unique_proxies)} (removed {len(all_proxies) - len(unique_proxies)} duplicates)")
        
        print("Saving to database...")
        
        # Save to database
        saved_count = self.save_proxies_to_database(unique_proxies, silent=False)
        logger.info(f"💾 Saved {saved_count} new proxies to database")
        
        return unique_proxies

    def _is_xpath_selector(self, selector: str) -> bool:
        """
        Determine if a selector is an XPath expression.
        
        Args:
            selector (str): The selector string to analyze
            
        Returns:
            bool: True if the selector is likely an XPath expression
        """
        if not selector or not isinstance(selector, str):
            return False
        
        selector = selector.strip()
        
        # If starts with known CSS selector patterns, it's probably CSS
        css_indicators = [
            '#',     # ID selector
            '>',     # Direct child combinator
            '+',     # Adjacent sibling combinator
            '~',     # General sibling combinator
            '::',    # Pseudo-elements
        ]
        
        # Check if it starts with clear CSS indicators
        if any(selector.startswith(indicator) for indicator in css_indicators):
            return False
        
        # CSS pseudo-classes and functions that shouldn't be confused with XPath
        css_pseudo_patterns = [
            ':hover', ':focus', ':active', ':visited', ':link',
            ':first-child', ':last-child', ':nth-child', ':nth-of-type',
            ':not(', ':has(', ':is(', ':where('
        ]
        
        if any(pattern in selector for pattern in css_pseudo_patterns):
            return False
        
        # Strong XPath indicators that are unlikely to be CSS
        strong_xpath_indicators = [
            '//',           # Descendant axis (most common XPath pattern)
            'text()',       # Text node function
            'contains(',    # Contains function
            'starts-with(', # Starts-with function
            'ends-with(',   # Ends-with function
            'normalize-space(', # Normalize-space function
            'count(',       # Count function
            'position(',    # Position function
            'last(',        # Last function
            'first(',       # First function
            'following:',   # Following axis
            'preceding:',   # Preceding axis
            'ancestor:',    # Ancestor axis
            'descendant:',  # Descendant axis
            'parent:',      # Parent axis
            'child:',       # Child axis
            'following-sibling:', # Following-sibling axis
            'preceding-sibling:', # Preceding-sibling axis
            'self:',        # Self axis
            'attribute:',   # Attribute axis
            'parent::',     # Parent axis with ::
            '/parent::',    # Parent axis in path
            '/child::',     # Child axis in path
        ]
        
        # Check for strong XPath indicators
        for indicator in strong_xpath_indicators:
            if indicator in selector:
                return True
        
        # Check for XPath-specific syntax patterns
        import re
        xpath_patterns = [
            # XPath functions and expressions that are clearly not CSS
            r'\btext\(\)\s*=',          # text()="value"
            r'\bcontains\s*\(',         # contains(...)
            r'\bstarts-with\s*\(',      # starts-with(...)
            r'\bends-with\s*\(',        # ends-with(...)
            r'\bnormalize-space\s*\(',  # normalize-space(...)
            r'\bposition\s*\(\)',       # position()
            r'\blast\s*\(\)',           # last()
            r'\bcount\s*\(',            # count(...)
            # Attribute checks with XPath syntax
            r'@\w+\s*=',                # @attr="value"
            r'@\w+\]',                  # [@attr]
            # Positional selectors that are XPath-style
            r'\[\d+\]$',                # [1], [2] at end of selector
            r'\[position\(\)',          # [position()...]
            r'\[last\(\)',              # [last()...]
            # Union expressions
            r'\s*\|\s*\w+',             # element1 | element2
        ]
        
        for pattern in xpath_patterns:
            if re.search(pattern, selector):
                return True
        
        # Special handling for selectors that start with '.' but might be XPath
        if selector.startswith('.'):
            # If it starts with '.' but contains strong XPath indicators, it might be XPath
            if any(indicator in selector for indicator in strong_xpath_indicators):
                return True
            # Otherwise, it's likely CSS
            return False
        
        # Check for parentheses grouping (common in XPath but can also be CSS functions)
        if selector.startswith('(') and selector.endswith(')'):
            # Look inside parentheses for XPath indicators
            inner_content = selector[1:-1]
            if any(indicator in inner_content for indicator in strong_xpath_indicators):
                return True
        
        # Additional checks for complex XPath expressions
        # If it contains square brackets with XPath-specific content
        if '[' in selector and ']' in selector:
            bracket_content = re.findall(r'\[([^\]]+)\]', selector)
            for content in bracket_content:
                # First check if it looks like a simple CSS attribute selector
                # CSS pattern: [attr="value"] or [attr='value'] or [attr]
                css_attr_pattern = r'^(\w+)(=(["\'])[^"\']*\3)?$'
                if re.match(css_attr_pattern, content.strip()):
                    # This looks like a simple CSS attribute selector
                    continue
                
                # Check if bracket content looks like XPath predicate
                xpath_predicate_patterns = [
                    r'@\w+',                    # @attribute
                    r'text\(\)',                # text()
                    r'contains\(',              # contains(
                    r'position\(\)',            # position()
                    r'last\(\)',                # last()
                    r'normalize-space\(',       # normalize-space(
                    r'\w+\s*=\s*["\']',        # attr="value" (but only if not simple CSS)
                    r'and\s+',                  # and operator
                    r'or\s+',                   # or operator
                ]
                
                for pattern in xpath_predicate_patterns:
                    if re.search(pattern, content):
                        return True
                
                # Simple numeric indices are XPath-style
                if re.match(r'^\d+$', content.strip()):
                    return True
        
        # If we reach here and it starts with '/' (but not '//' which was caught earlier)
        if selector.startswith('/') and not selector.startswith('//'):
            return True
        
        # Default to CSS for simple selectors without clear XPath indicators
        return False

    def scrape_table_source(self, source_name: str, config: Dict, update_stats: bool = True) -> List[Dict]:
        """
        Scrape proxies from a table-based source using dynamic configuration.
        
        Args:
            source_name (str): Name of the source
            config (Dict): Source configuration
            
        Returns:
            List[Dict]: List of proxy dictionaries
        """
        if not config:
            logger.error(f"❌ No configuration provided for {source_name}")
            return []
            
        if not isinstance(config, dict):
            logger.error(f"❌ Configuration for {source_name} is not a dictionary: {type(config)}")
            return []
            
        if 'url' not in config:
            logger.error(f"❌ No URL in configuration for {source_name}")
            return []
        
        if not self.driver:
            self.driver = self.setup_driver()
        
        proxies = []
        url = config['url']
        table_selector = config.get('table_selector', 'table')
        has_pagination = config.get('has_pagination', False)
        pagination_selector = config.get('pagination_selector')
        max_pages = config.get('max_pages', 10)  # Default limit to prevent infinite loops
        pagination_type = config.get('pagination_type', 'click')
        
        # Enhanced pagination selector logging
        if has_pagination and pagination_selector:
            is_xpath = self._is_xpath_selector(pagination_selector)
            logger.info(f"🔧 Pagination enabled: {pagination_type} type")
            logger.info(f"🎯 Selector: {pagination_selector} ({'XPath' if is_xpath else 'CSS'})")
        
        try:
            current_page = 1
            
            while current_page <= max_pages:
                logger.info(f"📄 Scraping page {current_page} of {source_name}")
                
                # For URL-based pagination on subsequent pages
                if pagination_type == 'url' and current_page > 1:
                    # URL modification is handled at the end of the loop
                    pass
                else:
                    # Load the initial page or click-based pagination
                    if current_page == 1:
                        self.driver.get(url)
                        time.sleep(config.get('request_delay_seconds', 2))
                
                # Wait for table to load with enhanced error handling
                try:
                    wait = WebDriverWait(self.driver, 15)
                    
                    # Try to find table with multiple selector strategies
                    table = None
                    selectors_to_try = [table_selector]
                    
                    # Add fallback selectors if the main one fails
                    if table_selector != 'table':
                        selectors_to_try.append('table')
                    
                    for selector in selectors_to_try:
                        try:
                            if self._is_xpath_selector(selector):
                                table = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                            else:
                                table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                            logger.info(f"✅ Table found with selector: {selector}")
                            break
                        except TimeoutException:
                            logger.warning(f"⚠️ Table selector '{selector}' failed, trying next...")
                            continue
                    
                    if not table:
                        logger.error(f"❌ No table found with any selector on page {current_page}")
                        break
                        
                except TimeoutException:
                    logger.error(f"❌ Timeout waiting for table on page {current_page}")
                    break
                
                # Extract table data
                page_proxies_count = 0
                try:
                    # Get table HTML and parse with BeautifulSoup for better data extraction
                    table_html = table.get_attribute('outerHTML')
                    soup = BeautifulSoup(table_html, 'html.parser')
                    
                    # Find all table rows (skip header)
                    rows = soup.find_all('tr')[1:]  # Skip header row
                    logger.info(f"📊 Found {len(rows)} data rows in table")
                    
                    for i, row in enumerate(rows):
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:  # Need at least IP and Port
                            try:
                                # Extract IP and Port
                                ip_col = config.get('ip_column', 0)
                                port_col = config.get('port_column', 1)
                                
                                if len(cells) <= max(ip_col, port_col):
                                    continue  # Skip if not enough columns
                                
                                ip = cells[ip_col].get_text(strip=True)
                                port_text = cells[port_col].get_text(strip=True)
                                
                                # Clean port text (remove any non-numeric characters except for ranges)
                                import re
                                port_match = re.search(r'\d+', port_text)
                                if not port_match:
                                    continue
                                port = int(port_match.group())
                                
                                # Validate IP and Port
                                if not self.is_valid_ip(ip) or not (1 <= port <= 65535):
                                    continue
                                
                                # Extract additional columns
                                country = None
                                country_col = config.get('country_column')
                                if country_col is not None and len(cells) > country_col:
                                    country = cells[country_col].get_text(strip=True)
                                
                                # Determine proxy type
                                proxy_type = config.get('default_type', 'http')
                                type_col = config.get('type_column')
                                if type_col is not None and len(cells) > type_col:
                                    type_text = cells[type_col].get_text(strip=True).lower()
                                    if 'socks5' in type_text:
                                        proxy_type = 'socks5'
                                    elif 'socks4' in type_text:
                                        proxy_type = 'socks4'
                                    elif 'https' in type_text or 'ssl' in type_text:
                                        proxy_type = 'https'
                                    elif 'http' in type_text:
                                        proxy_type = 'http'
                                
                                # Extract anonymity level
                                anonymity_level = None
                                anon_col = config.get('anonymity_column')
                                if anon_col is not None and len(cells) > anon_col:
                                    anonymity_text = cells[anon_col].get_text(strip=True)
                                    anonymity_level = self.normalize_anonymity_level(anonymity_text)
                                
                                proxy = {
                                    'ip': ip,
                                    'port': port,
                                    'type': proxy_type,
                                    'country': country[:3] if country else None,
                                    'country_name': country if country else None,
                                    'anonymity_level': anonymity_level,
                                    'source_url': self.driver.current_url,  # Use current URL for paginated sources
                                    'source_name': source_name,
                                    'status': 'untested'
                                }
                                
                                proxies.append(proxy)
                                page_proxies_count += 1
                                
                            except (ValueError, IndexError) as e:
                                continue  # Skip invalid rows
                    
                    logger.info(f"📊 Found {page_proxies_count} proxies on page {current_page}")
                    
                    # Check if pagination is enabled and we should continue to next page
                    if not has_pagination or current_page >= max_pages:
                        break
                    
                    # For click-based pagination, we need a pagination selector
                    if pagination_type == 'click' and not pagination_selector:
                        break
                    
                    # Handle pagination based on type
                    try:
                        if pagination_type == 'url':
                            # URL-based pagination: modify the URL with page parameter
                            base_url = url
                            if '&page=' in base_url or '?page=' in base_url:
                                # Replace existing page parameter
                                import re
                                if '?page=' in base_url:
                                    next_url = re.sub(r'\?page=\d+', f'?page={current_page + 1}', base_url)
                                else:
                                    next_url = re.sub(r'&page=\d+', f'&page={current_page + 1}', base_url)
                            else:
                                # Add page parameter
                                separator = '&' if '?' in base_url else '?'
                                next_url = f"{base_url}{separator}page={current_page + 1}"
                            
                            logger.info(f"🔄 Navigating to page {current_page + 1}: {next_url}")
                            self.driver.get(next_url)
                            time.sleep(config.get('request_delay_seconds', 2))
                            
                        else:
                            # Click-based pagination (default)
                            # Enhanced XPath and CSS selector support
                            is_xpath = self._is_xpath_selector(pagination_selector)
                            
                            if is_xpath:
                                # XPath selector - comprehensive support
                                logger.debug(f"🎯 Using XPath selector: {pagination_selector}")
                                next_button = self.driver.find_element(By.XPATH, pagination_selector)
                            else:
                                # CSS selector
                                logger.debug(f"🎯 Using CSS selector: {pagination_selector}")
                                next_button = self.driver.find_element(By.CSS_SELECTOR, pagination_selector)
                            
                            # Check if the button is enabled/clickable
                            if not next_button.is_enabled() or 'disabled' in (next_button.get_attribute('class') or ''):
                                logger.info(f"🔚 Next page button is disabled, stopping pagination")
                                break
                            
                            # Check if button text suggests it's the last page
                            button_text = next_button.text.lower() if next_button.text else ''
                            if any(word in button_text for word in ['last', 'final', 'end']):
                                logger.info(f"🔚 Reached last page based on button text: '{button_text}'")
                                break
                            
                            # Store current URL to detect if page actually changed
                            current_url = self.driver.current_url
                            
                            # Click next page button
                            logger.info(f"🔄 Navigating to page {current_page + 1}")
                            self.driver.execute_script("arguments[0].click();", next_button)
                            
                            # Wait for page to load
                            time.sleep(config.get('request_delay_seconds', 2))
                            
                            # Check if URL changed (some sites use AJAX)
                            new_url = self.driver.current_url
                            if current_url == new_url:
                                # For AJAX-based pagination, wait a bit more and check if table content changed
                                time.sleep(2)
                                try:
                                    # Wait for table to be refreshed
                                    WebDriverWait(self.driver, 5).until(
                                        EC.staleness_of(table)
                                    )
                                except:
                                    # If table doesn't become stale, it might not have updated
                                    logger.warning(f"⚠️ Page may not have changed after clicking next")
                        
                        current_page += 1
                        
                    except Exception as e:
                        logger.info(f"🔚 No more pages available or error with pagination: {str(e)}")
                        break
                
                except Exception as e:
                    logger.error(f"❌ Error processing table on page {current_page}: {str(e)}")
                    break
            
        except TimeoutException:
            logger.warning(f"⏰ Timeout waiting for table on {source_name}")
        except Exception as e:
            logger.error(f"❌ Error scraping table from {source_name}: {str(e)}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
        
        # Update last_scraped timestamp in proxy_sources table (if requested)
        if update_stats:
            try:
                success = len(proxies) > 0
                self.supabase_client.update_source_scrape_results(source_name, success, len(proxies))
            except Exception as e:
                logger.warning(f"⚠️ Failed to update source stats for {source_name}: {str(e)}")
        
        return proxies

    def scrape_table_based_site(self, url: str, table_selector: str, source_name: str) -> List[Dict]:
        """
        Scrape proxy data from table-based websites.
        
        Args:
            url (str): URL to scrape
            table_selector (str): CSS selector for the proxy table
            source_name (str): Name of the source
            
        Returns:
            List[Dict]: List of proxy dictionaries
        """
        proxies = []
        
        try:
            print(f"🔍 Scraping {source_name} from {url}")
            
            if not self.driver:
                self.driver = self.setup_driver()
            
            self.driver.get(url)
            
            # Wait for table to load
            wait = WebDriverWait(self.driver, 10)
            table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, table_selector)))
            
            # Get table HTML and parse with BeautifulSoup
            table_html = table.get_attribute('outerHTML')
            soup = BeautifulSoup(table_html, 'html.parser')
            
            # Find all table rows (skip header)
            rows = soup.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:  # Need at least IP and Port
                    try:
                        ip = cells[0].get_text(strip=True)
                        port = int(cells[1].get_text(strip=True))
                        
                        # Determine proxy type based on source
                        proxy_type = 'http'
                        if 'ssl' in source_name.lower():
                            proxy_type = 'https'
                        elif 'socks' in source_name.lower():
                            proxy_type = 'socks5'
                        
                        # Extract additional info if available
                        country = cells[2].get_text(strip=True) if len(cells) > 2 else None
                        anonymity = cells[4].get_text(strip=True) if len(cells) > 4 else None
                        
                        # Validate IP format
                        if self.is_valid_ip(ip) and 1 <= port <= 65535:
                            proxy_data = {
                                'ip': ip,
                                'port': port,
                                'type': proxy_type,
                                'country': country[:3] if country else None,
                                'country_name': country if country else None,
                                'anonymity_level': self.normalize_anonymity_level(anonymity),
                                'source_url': url,
                                'source_name': source_name,
                                'status': 'untested'
                            }
                            proxies.append(proxy_data)
                            
                    except (ValueError, IndexError) as e:
                        continue  # Skip invalid rows
            
            print(f"✅ Found {len(proxies)} proxies from {source_name}")
            
        except TimeoutException:
            print(f"⏰ Timeout while loading {url}")
        except Exception as e:
            print(f"❌ Error scraping {source_name}: {str(e)}")
        
        return proxies
    
    def debug_table_scraping(self, url: str, table_selector: str, source_name: str, 
                           pause_after_load: bool = False, take_screenshot: bool = False) -> List[Dict]:
        """
        Debug version of table scraping with enhanced visibility and control.
        
        Args:
            url (str): URL to scrape
            table_selector (str): CSS selector for the proxy table
            source_name (str): Name of the source
            pause_after_load (bool): Pause after page load for manual inspection
            take_screenshot (bool): Take screenshot of the page
            
        Returns:
            List[Dict]: List of proxy dictionaries
        """
        proxies = []
        
        try:
            print(f"🔍 Debug scraping {source_name} from {url}")
            
            if not self.driver:
                self.driver = self.setup_driver()
            
            print("📡 Loading page...")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            print(f"📄 Page title: {self.driver.title}")
            print(f"🌐 Current URL: {self.driver.current_url}")
            
            # Take screenshot if requested
            if take_screenshot:
                screenshot_path = f"/tmp/debug_screenshot_{source_name}_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                print(f"📸 Screenshot saved: {screenshot_path}")
            
            # Check if table exists
            try:
                wait = WebDriverWait(self.driver, 10)
                table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, table_selector)))
                print(f"✅ Table found with selector: {table_selector}")
                
                # Get table info
                rows = table.find_elements(By.TAG_NAME, "tr")
                print(f"📊 Table has {len(rows)} rows")
                
                if len(rows) > 0:
                    header_row = rows[0]
                    headers = [th.text.strip() for th in header_row.find_elements(By.TAG_NAME, "th")]
                    if headers:
                        print(f"📋 Headers: {headers}")
                    else:
                        # Try td elements for header
                        headers = [td.text.strip() for td in header_row.find_elements(By.TAG_NAME, "td")]
                        print(f"📋 Headers (from td): {headers}")
                
            except TimeoutException:
                print(f"❌ Table not found with selector: {table_selector}")
                # Try to find any tables
                tables = self.driver.find_elements(By.TAG_NAME, "table")
                print(f"🔍 Found {len(tables)} table(s) on page")
                for i, table in enumerate(tables):
                    table_id = table.get_attribute('id')
                    table_class = table.get_attribute('class')
                    print(f"   Table {i+1}: id='{table_id}', class='{table_class}'")
                
                if pause_after_load:
                    input("\n⏸️  Page loaded. Inspect the page manually, then press Enter to continue...")
                
                return proxies
            
            # Pause for manual inspection if requested
            if pause_after_load:
                input("\n⏸️  Table found. Inspect the page manually, then press Enter to continue...")
            
            # Get table HTML and parse with BeautifulSoup
            table_html = table.get_attribute('outerHTML')
            soup = BeautifulSoup(table_html, 'html.parser')
            
            # Find all table rows (skip header)
            rows = soup.find_all('tr')[1:]  # Skip header row
            print(f"🔄 Processing {len(rows)} data rows...")
            
            for i, row in enumerate(rows):
                cells = row.find_all('td')
                if len(cells) >= 2:  # Need at least IP and Port
                    try:
                        ip = cells[0].get_text(strip=True)
                        port_text = cells[1].get_text(strip=True)
                        
                        # Debug output for first few rows
                        if i < 5:
                            print(f"   Row {i+1}: IP={ip}, Port={port_text}, Cells={len(cells)}")
                            if len(cells) > 2:
                                print(f"           Other: {[cell.get_text(strip=True) for cell in cells[2:6]]}")
                        
                        port = int(port_text)
                        
                        # Determine proxy type based on source
                        proxy_type = 'http'
                        if 'ssl' in source_name.lower():
                            proxy_type = 'https'
                        elif 'socks' in source_name.lower():
                            proxy_type = 'socks5'
                        
                        # Extract additional info if available
                        country = cells[2].get_text(strip=True) if len(cells) > 2 else None
                        anonymity = cells[4].get_text(strip=True) if len(cells) > 4 else None
                        
                        # Validate IP format
                        if self.is_valid_ip(ip) and 1 <= port <= 65535:
                            proxy_data = {
                                'ip': ip,
                                'port': port,
                                'type': proxy_type,
                                'country': country[:3] if country else None,
                                'country_name': country if country else None,
                                'anonymity_level': self.normalize_anonymity_level(anonymity),
                                'source_url': url,
                                'source_name': source_name,
                                'status': 'untested'
                            }
                            proxies.append(proxy_data)
                        else:
                            if i < 5:  # Debug invalid entries for first few rows
                                print(f"   ❌ Invalid: IP={ip}, Port={port_text}")
                            
                    except (ValueError, IndexError) as e:
                        if i < 5:  # Debug errors for first few rows
                            print(f"   ⚠️ Parse error row {i+1}: {str(e)}")
                        continue  # Skip invalid rows
            
            print(f"✅ Successfully parsed {len(proxies)} valid proxies from {source_name}")
            
        except Exception as e:
            print(f"❌ Error in debug scraping {source_name}: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return proxies
    
    def scrape_api_source(self, source_name: str, config: Dict, update_stats: bool = True) -> List[Dict]:
        """
        Scrape proxy data from API endpoints with configurable JSON field mapping.
        
        Args:
            source_name (str): Name of the source
            config (Dict): Source configuration including API settings
            
        Returns:
            List[Dict]: List of proxy dictionaries
        """
        proxies = []
        
        try:
            url = config.get('url')
            if not url:
                logger.error(f"❌ No URL provided for API source {source_name}")
                return []
            
            logger.info(f"🔍 Fetching from API: {source_name}")
            logger.info(f"🌐 URL: {url}")
            
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'application/json, text/plain, */*'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            api_format = config.get('api_format', 'text')
            
            if api_format == 'json':
                # Handle JSON API responses
                try:
                    data = response.json()
                    
                    # Extract proxy array from response
                    api_response_path = config.get('api_response_path', 'data')
                    if api_response_path and api_response_path in data:
                        proxy_list = data[api_response_path]
                    elif isinstance(data, list):
                        proxy_list = data
                    else:
                        # Try to find array in top-level keys
                        proxy_list = None
                        for key, value in data.items():
                            if isinstance(value, list) and len(value) > 0:
                                proxy_list = value
                                break
                        
                        if proxy_list is None:
                            logger.warning(f"⚠️ Could not find proxy array in JSON response for {source_name}")
                            return []
                    
                    # Configure JSON field mappings
                    ip_field = config.get('json_ip_field', 'ip')
                    port_field = config.get('json_port_field', 'port') 
                    country_field = config.get('json_country_field', 'country')
                    anonymity_field = config.get('json_anonymity_field', 'anonymityLevel')
                    
                    # Process each proxy in the list
                    for item in proxy_list:
                        try:
                            if not isinstance(item, dict):
                                continue
                                
                            ip = item.get(ip_field)
                            port = item.get(port_field)
                            
                            if not ip or not port:
                                continue
                                
                            # Convert port to integer
                            try:
                                port = int(port)
                            except (ValueError, TypeError):
                                continue
                            
                            # Validate IP and port
                            if not self.is_valid_ip(str(ip)) or not (1 <= port <= 65535):
                                continue
                            
                            # Extract additional fields
                            country = item.get(country_field, '')
                            anonymity = item.get(anonymity_field, '')
                            
                            # Determine proxy type from protocols if available
                            proxy_type = 'http'  # Default
                            if 'protocols' in item and isinstance(item['protocols'], list):
                                protocols = item['protocols']
                                if 'socks5' in protocols:
                                    proxy_type = 'socks5'
                                elif 'socks4' in protocols:
                                    proxy_type = 'socks4'
                                elif 'https' in protocols:
                                    proxy_type = 'https'
                            
                            proxy_data = {
                                'ip': str(ip),
                                'port': port,
                                'type': proxy_type,
                                'country': country[:3] if country else None,  # Country code limit
                                'anonymity_level': self.normalize_anonymity_level(anonymity),
                                'source_url': config['url'],
                                'source_name': source_name,
                                'status': 'untested'
                            }
                            
                            proxies.append(proxy_data)
                            
                        except Exception as e:
                            logger.debug(f"Skipping invalid proxy item: {str(e)}")
                            continue
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse JSON response from {source_name}: {str(e)}")
                    return []
            
            else:
                # Handle text-based API responses (IP:PORT format)
                proxy_lines = response.text.strip().split('\n')
                
                for line in proxy_lines:
                    line = line.strip()
                    if ':' in line:
                        try:
                            ip, port = line.split(':', 1)
                            port = int(port)
                            
                            if self.is_valid_ip(ip) and 1 <= port <= 65535:
                                proxy_data = {
                                    'ip': ip,
                                    'port': port,
                                    'type': 'http',  # Default for text APIs
                                    'source_url': config['url'],
                                    'source_name': source_name,
                                    'status': 'untested'
                                }
                                proxies.append(proxy_data)
                                
                        except ValueError:
                            continue
            
            logger.info(f"✅ Found {len(proxies)} proxies from {source_name}")
            
        except Exception as e:
            logger.error(f"❌ Error fetching from API {source_name}: {str(e)}")
        
        # Update last_scraped timestamp in proxy_sources table (if requested)
        if update_stats:
            try:
                success = len(proxies) > 0
                self.supabase_client.update_source_scrape_results(source_name, success, len(proxies))
            except Exception as e:
                logger.warning(f"⚠️ Failed to update source stats for {source_name}: {str(e)}")
        
        return proxies
    
    def normalize_anonymity_level(self, anonymity: str) -> str:
        """
        Normalize anonymity level to match database constraints.
        
        Args:
            anonymity (str): Raw anonymity string from website
            
        Returns:
            str: Normalized anonymity level or None
        """
        if not anonymity:
            return None
            
        anonymity_lower = anonymity.lower()
        if 'elite' in anonymity_lower:
            return 'elite'
        elif 'anonymous' in anonymity_lower:
            return 'anonymous'
        elif 'transparent' in anonymity_lower:
            return 'transparent'
        
        return None
    
    def is_valid_ip(self, ip: str) -> bool:
        """
        Validate IP address format.
        
        Args:
            ip (str): IP address to validate
            
        Returns:
            bool: True if valid IP format
        """
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(pattern, ip):
            octets = ip.split('.')
            return all(0 <= int(octet) <= 255 for octet in octets)
        return False
    
    def remove_duplicates(self, proxies: List[Dict]) -> List[Dict]:
        """
        Remove duplicate proxies based on IP:Port combination.
        
        Args:
            proxies (List[Dict]): List of proxy dictionaries
            
        Returns:
            List[Dict]: List with duplicates removed
        """
        unique_proxies = []
        seen = set()
        
        for proxy in proxies:
            key = f"{proxy['ip']}:{proxy['port']}"
            if key not in seen:
                seen.add(key)
                unique_proxies.append(proxy)
        
        return unique_proxies
    
    def scrape_all_sources(self) -> Dict[str, List[Dict]]:
        """
        Scrape all configured proxy sources.
        
        Returns:
            Dict[str, List[Dict]]: Dictionary mapping source names to proxy lists
        """
        all_proxies = {}
        
        try:
            for source_name, config in self.proxy_sources.items():
                print(f"\n🚀 Starting to scrape {source_name}")
                
                if config['method'] == 'selenium':
                    proxies = self.scrape_table_source(source_name, config)
                elif config['method'] == 'api':
                    proxies = self.scrape_api_source(source_name, config)
                else:
                    proxies = []
                
                all_proxies[source_name] = proxies
                
                # Add delay between sources
                if self.delay > 0:
                    print(f"⏳ Waiting {self.delay} seconds before next source...")
                    time.sleep(self.delay)
        
        finally:
            if self.driver:
                self.driver.quit()
                print("🔒 WebDriver closed")
        
        return all_proxies
    
    def save_proxies_to_database(self, proxies: List[Dict], silent: bool = True) -> int:
        """
        Save scraped proxies to Supabase database.
        
        Args:
            proxies (List[Dict]): List of proxy dictionaries
            silent (bool): If True, suppress per-proxy logs
            
        Returns:
            int: Number of proxies successfully saved
        """
        saved_count = 0
        duplicate_count = 0
        error_count = 0
        
        for proxy in proxies:
            try:
                result = self.supabase_client.insert_proxy(proxy, silent=True)
                if result is not None:
                    saved_count += 1
                else:
                    duplicate_count += 1
            except Exception as e:
                error_count += 1
                if not silent:
                    print(f"⚠️ Failed to save proxy {proxy.get('ip')}:{proxy.get('port')}: {str(e)}")
                continue
        
        # Print summary instead of per-proxy logs
        if not silent:
            print(f"💾 Database save summary:")
            print(f"   • New proxies saved: {saved_count}")
            if duplicate_count > 0:
                print(f"   • Duplicates skipped: {duplicate_count}")
            if error_count > 0:
                print(f"   • Errors: {error_count}")
        
        return saved_count
    
    def run_scraping_job(self) -> Dict[str, int]:
        """
        Run a complete scraping job across all sources.
        
        Returns:
            Dict[str, int]: Statistics about the scraping job
        """
        print("🚀 Starting proxy scraping job...")
        start_time = datetime.now()
        
        # Scrape all sources
        all_scraped_proxies = self.scrape_all_sources()
        
        # Combine all proxies
        all_proxies = []
        for source_name, proxies in all_scraped_proxies.items():
            all_proxies.extend(proxies)
        
        # Remove duplicates based on IP:Port combination
        unique_proxies = []
        seen = set()
        for proxy in all_proxies:
            key = f"{proxy['ip']}:{proxy['port']}"
            if key not in seen:
                seen.add(key)
                unique_proxies.append(proxy)

        print("Saving to database...")
        
        # Save to database
        saved_count = self.save_proxies_to_database(unique_proxies, silent=False)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        stats = {
            'total_scraped': len(all_proxies),
            'unique_proxies': len(unique_proxies),
            'saved_to_db': saved_count,
            'duration_seconds': duration,
            'sources_scraped': len(all_scraped_proxies)
        }
        
        print(f"\n📊 Scraping Job Complete!")
        print(f"   • Total scraped: {stats['total_scraped']}")
        print(f"   • Unique proxies: {stats['unique_proxies']}")
        print(f"   • Saved to DB: {stats['saved_to_db']}")
        print(f"   • Duration: {stats['duration_seconds']:.1f} seconds")
        print(f"   • Sources: {stats['sources_scraped']}")
        
        return stats


# Example usage
if __name__ == "__main__":
    scraper = ProxyScraper(headless=True, delay=2)
    stats = scraper.run_scraping_job() 