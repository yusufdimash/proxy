import os
import json
import time
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import google.generativeai as genai
from dataclasses import dataclass
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

@dataclass
class ProxySourceConfig:
    """Data class for proxy source configuration"""
    name: str
    url: str
    method: str
    table_selector: Optional[str] = None
    ip_column: Optional[int] = None
    port_column: Optional[int] = None
    country_column: Optional[int] = None
    anonymity_column: Optional[int] = None
    api_format: Optional[str] = None
    api_response_path: Optional[str] = None
    has_pagination: bool = False
    pagination_selector: Optional[str] = None
    pagination_type: str = 'click'
    max_pages: int = 10
    request_delay_seconds: int = 2
    expected_min_proxies: int = 10
    confidence_score: float = 0.0

class GeminiConfigGenerator:
    """
    Google Gemini AI client for generating proxy scraper configurations.
    Analyzes websites and generates scraping configurations automatically.
    """
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment variables")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        print("✅ Gemini AI client initialized successfully")
    
    def setup_driver(self) -> webdriver.Chrome:
        """
        Set up Chrome WebDriver for analysis.
        
        Returns:
            webdriver.Chrome: Configured Chrome driver
        """
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            # Try to use system ChromeDriver first
            driver = webdriver.Chrome(options=options)
            print("✅ Using system ChromeDriver")
            return driver
        except Exception:
            try:
                # Fallback to WebDriverManager
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                print("✅ Using WebDriverManager ChromeDriver")
                return driver
            except Exception as e:
                raise Exception(f"Failed to setup ChromeDriver: {str(e)}")

    def analyze_website_structure_with_driver(self, url: str, driver: webdriver.Chrome) -> str:
        """
        Analyze website structure using an existing Selenium driver.
        
        Args:
            url (str): URL to analyze
            driver (webdriver.Chrome): Existing Chrome driver
            
        Returns:
            str: HTML structure analysis
        """
        try:
            print(f"🔍 Loading page: {url}")
            driver.get(url)
            
            # Wait for page to fully load
            time.sleep(3)
            
            # Wait for any tables to be present
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
            except TimeoutException:
                print("⚠️ No tables found on page")
            
            # Get the full page HTML after JavaScript execution
            page_html = driver.page_source
            soup = BeautifulSoup(page_html, 'html.parser')
            
            # Extract relevant structural information
            analysis = {
                'title': soup.title.string if soup.title else 'No title',
                'url': driver.current_url,
                'tables': [],
                'forms': [],
                'pagination_elements': [],
                'page_stats': {
                    'total_elements': len(soup.find_all()),
                    'scripts': len(soup.find_all('script')),
                    'total_tables': len(soup.find_all('table'))
                }
            }
            
            # Check for API endpoint indicators
            analysis['likely_api'] = False
            analysis['api_indicators'] = []
            
            # Check URL for API patterns
            if any(keyword in url.lower() for keyword in ['/api/', '/rest/', '.json', '/v1/', '/v2/', '/proxy-list']):
                analysis['likely_api'] = True
                analysis['api_indicators'].append('URL contains API patterns')
            
            # Check page content for JSON response
            page_text = soup.get_text().strip()
            if page_text.startswith('{') and page_text.endswith('}'):
                analysis['likely_api'] = True
                analysis['api_indicators'].append('Page returns raw JSON')
                # Try to parse the JSON to understand structure
                try:
                    json_data = json.loads(page_text)
                    analysis['json_structure'] = {
                        'is_array': isinstance(json_data, list),
                        'is_object': isinstance(json_data, dict),
                        'top_level_keys': list(json_data.keys()) if isinstance(json_data, dict) else [],
                        'sample_item': None
                    }
                    
                    # If it's an object with an array, find the proxy data
                    if isinstance(json_data, dict):
                        for key, value in json_data.items():
                            if isinstance(value, list) and len(value) > 0:
                                analysis['json_structure']['sample_item'] = value[0] if value else None
                                analysis['json_structure']['array_key'] = key
                                break
                    elif isinstance(json_data, list) and len(json_data) > 0:
                        analysis['json_structure']['sample_item'] = json_data[0]
                        
                except json.JSONDecodeError:
                    analysis['api_indicators'].append('Contains JSON-like content but invalid')
            
            # Check title for API indicators
            if soup.title and soup.title.string:
                title_lower = soup.title.string.lower()
                if any(keyword in title_lower for keyword in ['api', 'json', 'xml', 'rest']):
                    analysis['likely_api'] = True
                    analysis['api_indicators'].append('Title suggests API endpoint')
            
            # Analyze tables with more detail
            tables = soup.find_all('table')
            for i, table in enumerate(tables[:5]):  # Limit to first 5 tables
                if not table:
                    continue
                    
                table_info = {
                    'index': i,
                    'id': table.get('id', '') if table else '',
                    'class': ' '.join(table.get('class', [])) if table.get('class') else '',
                    'rows': len(table.find_all('tr')) if table else 0,
                    'headers': [],
                    'sample_data': []
                }
                
                # Get header information
                rows = table.find_all('tr') if table else []
                if rows:
                    # Check first row for headers
                    header_row = rows[0]
                    if header_row:
                        headers = header_row.find_all(['th', 'td'])
                        table_info['headers'] = [h.get_text(strip=True) for h in headers[:10] if h]
                    
                    # Get sample data from first few rows
                    for row_idx, row in enumerate(rows[1:4]):  # Skip header, get next 3 rows
                        if row:
                            cells = row.find_all('td')
                            if cells:
                                row_data = [cell.get_text(strip=True) for cell in cells[:10] if cell]
                                if row_data:  # Only add if we have data
                                    table_info['sample_data'].append({
                                        'row': row_idx + 1,
                                        'data': row_data
                                    })
                
                analysis['tables'].append(table_info)
            
            # Look for pagination elements with more comprehensive selectors
            pagination_selectors = [
                'a[href*="page"]', '.pagination a', '.next', '.page-next', '.pager a',
                'button[onclick*="page"]', 'a[onclick*="page"]', '[class*="next"]',
                '[class*="pagination"]', '[id*="pagination"]', 'nav a'
            ]
            
            for selector in pagination_selectors:
                elements = soup.select(selector) if soup else []
                if elements:
                    text_samples = []
                    for elem in elements[:3]:
                        if elem:
                            text = elem.get_text(strip=True)
                            if text:
                                text_samples.append(text[:50])
                    
                    analysis['pagination_elements'].append({
                        'selector': selector, 
                        'count': len(elements),
                        'text_samples': text_samples
                    })
            
            # Look for forms that might be relevant
            forms = soup.find_all('form')
            for i, form in enumerate(forms[:3]):
                if form:
                    form_info = {
                        'index': i,
                        'action': form.get('action', '') if form else '',
                        'method': form.get('method', 'GET') if form else 'GET',
                        'inputs': len(form.find_all('input')) if form else 0
                    }
                    analysis['forms'].append(form_info)
            
            print(f"✅ Analysis complete: {len(tables)} tables, {len(forms)} forms found")
            return json.dumps(analysis, indent=2)
            
        except Exception as e:
            error_msg = f"Error analyzing website: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return json.dumps({'error': error_msg, 'traceback': traceback.format_exc()}, indent=2)

    def analyze_website_structure(self, url: str) -> str:
        """
        Fetch and analyze website structure for proxy table identification using Selenium.
        
        Args:
            url (str): URL to analyze
            
        Returns:
            str: HTML structure analysis
        """
        driver = None
        try:
            driver = self.setup_driver()
            return self.analyze_website_structure_with_driver(url, driver)
        finally:
            if driver:
                driver.quit()
    
    def generate_config_prompt(self, url: str, website_analysis: str, source_name: str) -> str:
        """
        Generate the AI prompt for configuration generation.
        
        Args:
            url (str): Target URL
            website_analysis (str): Website structure analysis
            source_name (str): Name of the proxy source
            
        Returns:
            str: Generated prompt for Gemini
        """
        return f"""
You are an expert web scraping configuration generator. Analyze the provided website structure and generate a precise configuration for scraping proxy data.

**Target Website:** {url}
**Source Name:** {source_name}

**Website Analysis:**
{website_analysis}

**Task:** Generate a JSON configuration for scraping proxy data from this website.

**Requirements:**
1. **METHOD SELECTION**:
   - If analysis shows "likely_api": true with JSON structure, use method="api"
   - If analysis shows HTML tables with proxy data, use method="selenium" 
   - If URL contains /api/ or returns raw JSON, prefer method="api"

2. **For API endpoints** (when likely_api=true):
   - Set method="api"
   - Set api_format="json" (most common)
   - Identify the JSON path to proxy data array (look for "data", "proxies", "results" keys)
   - Map JSON fields: ip, port, country, anonymity_level fields in the JSON objects
   - Set api_response_path to the path to access proxy array (e.g., "data" or "results")

3. **For table-based sites**:
   - Set method="selenium"
   - Best CSS selector for the proxy table (look for table with IP addresses)
   - Column indices for IP address (usually 0), port (usually 1), country, anonymity level
   - Detect pagination presence and type:
     * Look for "Next", ">" buttons, page numbers, or pagination controls
     * For click-based pagination: provide selector for next button
       - **PREFER XPath for maximum reliability and flexibility**
       - XPath Examples (use comprehensive patterns):
         * "//a[contains(text(), 'Next')]" - Text contains "Next"
         * "//button[text()='Next']" - Exact text match
         * "//a[@aria-label='Next page']" - Aria label
         * "//button[contains(@class, 'next')]" - Class contains "next"
         * "//a[contains(@class, 'pagination-next')]" - Pagination next class
         * "(//a[contains(@class, 'page-link')])[last()]" - Last pagination link
         * "//button[@data-action='next']" - Data attribute
         * "//a[contains(@href, 'page=') and position()=last()]" - URL-based last link
         * "//div[@class='pagination']//a[text()='>']" - Greater than symbol
         * "//nav//button[contains(normalize-space(text()), 'Next')]" - Normalized text
         * "//a[@rel='next']" - Rel attribute
         * "//button[@type='button' and contains(text(), 'Next')]" - Button with text
         * "//span[text()='Next']/parent::a" - Parent element selection
         * "//li[contains(@class, 'next')]/a" - List item with next class
         * "//div[contains(@class, 'pager')]//a[last()]" - Last link in pager
       - CSS selectors are also supported but XPath is preferred:
         * ".next", ".pagination a:last-child", "button.page-next"
     * For URL-based pagination: check if URL contains page parameters (e.g., "page=1", "p=1")
     * Set pagination_type to "click" for button-based, "url" for parameter-based
     * Set max_pages to reasonable limit (5-15 depending on site size)

4. **XPath Best Practices**:
   - Use contains() function for partial text matches
   - Use normalize-space() for text with extra whitespace
   - Use position() and last() functions for element positioning
   - Combine multiple conditions with "and" operator
   - Use parent:: and following-sibling:: axes when needed
   - Prefer specific attributes like @aria-label, @data-action, @rel over generic @class
   - Use text() function for exact text matching
   - Consider case-insensitive matching with translate() function if needed

5. Estimate confidence score (0.0-1.0) based on analysis clarity
6. Estimate minimum expected proxies per scrape (typically 50-500 for proxy APIs, 50-300 for tables)
7. Recommended request delay to avoid rate limiting (usually 2-5 seconds)

**Expected Output Format (JSON):**
{{
    "method": "selenium|api",
    "table_selector": "CSS selector for proxy table (if selenium method)",
    "ip_column": 0,
    "port_column": 1,
    "country_column": 2,
    "anonymity_column": 4,
    "api_format": "json|text|csv|xml (if API method)",
    "api_response_path": "Key to access proxy array in JSON response (if API method)",
    "json_ip_field": "JSON field name for IP address (if API method)",
    "json_port_field": "JSON field name for port (if API method)", 
    "json_country_field": "JSON field name for country (if API method)",
    "json_anonymity_field": "JSON field name for anonymity level (if API method)",
    "has_pagination": false,
    "pagination_selector": "Comprehensive XPath or CSS selector for next page button (PREFER XPath with full patterns)",
    "pagination_type": "click|url",
    "max_pages": 10,
    "request_delay_seconds": 2,
    "expected_min_proxies": 50,
    "confidence_score": 0.85,
    "reasoning": "Explanation of choices made, especially pagination selector rationale"
}}

**Important Notes:**
- For table-based sites, look for tables containing IP addresses and ports
- Column indices are 0-based (first column = 0)
- Common proxy table headers: IP, Port, Country, Anonymity, Protocol, etc.
- Be conservative with confidence scores - only use >0.8 if very certain
- Consider anti-bot measures when setting request delays
- When choosing pagination selectors, prioritize reliability over brevity
- Test XPath expressions mentally for robustness across different page states

Generate the configuration now:
"""

    def generate_configuration(self, url: str, source_name: str, 
                             trigger_reason: str = "manual_request") -> Tuple[ProxySourceConfig, str, float]:
        """
        Generate a complete proxy source configuration using AI analysis.
        
        Args:
            url (str): Target URL to analyze
            source_name (str): Name for the proxy source
            trigger_reason (str): Reason for generation (for logging)
            
        Returns:
            Tuple[ProxySourceConfig, str, float]: Generated config, analysis, confidence
        """
        print(f"🤖 Generating AI configuration for {source_name}")
        print(f"📊 Trigger reason: {trigger_reason}")
        
        try:
            # Step 1: Analyze website structure
            print("🔍 Analyzing website structure...")
            website_analysis = self.analyze_website_structure(url)
            
            # Step 2: Generate AI prompt
            prompt = self.generate_config_prompt(url, website_analysis, source_name)
            
            # Step 3: Get AI response
            print("🧠 Generating configuration with Gemini AI...")
            response = self.model.generate_content(prompt)
            
            if not response.text:
                raise Exception("Empty response from Gemini API")
            
            # Step 4: Parse JSON response
            try:
                # Extract JSON from response (handle potential markdown formatting)
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
                
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parsing error: {e}")
                print(f"Response: {response.text}")
                raise Exception(f"Failed to parse AI response as JSON: {e}")
            
            # Step 5: Create ProxySourceConfig object
            config = ProxySourceConfig(
                name=source_name,
                url=url,
                method=config_data.get('method', 'selenium'),
                table_selector=config_data.get('table_selector'),
                ip_column=config_data.get('ip_column'),
                port_column=config_data.get('port_column'),
                country_column=config_data.get('country_column'),
                anonymity_column=config_data.get('anonymity_column'),
                api_format=config_data.get('api_format'),
                api_response_path=config_data.get('api_response_path'),
                has_pagination=config_data.get('has_pagination', False),
                pagination_selector=config_data.get('pagination_selector'),
                pagination_type=config_data.get('pagination_type', 'click'),
                max_pages=config_data.get('max_pages', 10),
                request_delay_seconds=config_data.get('request_delay_seconds', 2),
                expected_min_proxies=config_data.get('expected_min_proxies', 10),
                confidence_score=config_data.get('confidence_score', 0.5)
            )
            
            print(f"✅ Configuration generated successfully!")
            print(f"📊 Method: {config.method}")
            print(f"🎯 Confidence: {config.confidence_score:.2f}")
            print(f"📈 Expected proxies: {config.expected_min_proxies}")
            
            return config, website_analysis, config.confidence_score
            
        except Exception as e:
            print(f"❌ Error generating configuration: {str(e)}")
            # Return a basic fallback configuration
            fallback_config = ProxySourceConfig(
                name=source_name,
                url=url,
                method='selenium',
                table_selector='table',  # Generic fallback
                ip_column=0,
                port_column=1,
                confidence_score=0.1  # Very low confidence
            )
            return fallback_config, f"Error: {str(e)}", 0.1
    
    def validate_configuration(self, config: ProxySourceConfig) -> Dict[str, any]:
        """
        Validate a generated configuration by testing it.
        
        Args:
            config (ProxySourceConfig): Configuration to validate
            
        Returns:
            Dict[str, any]: Validation results
        """
        validation_results = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'test_results': {}
        }
        
        try:
            # Basic validation checks
            if not config.url:
                validation_results['errors'].append("URL is required")
            
            if config.method == 'selenium' and not config.table_selector:
                validation_results['errors'].append("Table selector required for selenium method")
            
            if config.method == 'api' and not config.api_format:
                validation_results['warnings'].append("API format not specified")
            
            if config.confidence_score < 0.3:
                validation_results['warnings'].append("Low confidence score - manual review recommended")
            
            # Mark as valid if no critical errors
            validation_results['valid'] = len(validation_results['errors']) == 0
            
        except Exception as e:
            validation_results['errors'].append(f"Validation error: {str(e)}")
        
        return validation_results

# Example usage and testing
if __name__ == "__main__":
    try:
        generator = GeminiConfigGenerator()
        
        # Test with a known proxy site
        test_url = "https://free-proxy-list.net/"
        config, analysis, confidence = generator.generate_configuration(
            test_url, "test-free-proxy-list"
        )
        
        print(f"\n🎯 Generated Configuration:")
        print(f"Method: {config.method}")
        print(f"Table Selector: {config.table_selector}")
        print(f"Columns: IP={config.ip_column}, Port={config.port_column}")
        print(f"Confidence: {config.confidence_score}")
        
        # Validate the configuration
        validation = generator.validate_configuration(config)
        print(f"\n✅ Validation Results:")
        print(f"Valid: {validation['valid']}")
        print(f"Errors: {validation['errors']}")
        print(f"Warnings: {validation['warnings']}")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}") 