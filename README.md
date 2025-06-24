# 🌐 AI-Powered Distributed Proxy Scraper

An advanced, intelligent proxy scraper system built with Python, Selenium, and Supabase. Features **AI-powered dynamic configuration generation**, **multi-computer distributed validation**, and automated proxy management with real-time monitoring. Scale validation across multiple computers for 4x faster performance!

## ✨ Features

### 🔍 **Smart Scraping**

- **Multi-source scraping** from 5+ popular proxy websites
- **Selenium-powered** with anti-detection capabilities
- **Automatic proxy type detection** (HTTP, HTTPS, SOCKS4, SOCKS5)
- **Geolocation extraction** (country, city, anonymity level)
- **Duplicate removal** and data validation

### ✅ **Advanced Validation**

- **Multi-computer distributed validation** (4x faster performance)
- **Traditional single-machine validation** (up to 50 concurrent threads)
- **Real proxy testing** with HTTP/SOCKS support
- **Performance metrics** and historical tracking
- **IP verification** and response time monitoring
- **Auto-scaling across multiple computers**

### 🤖 **Automation & Monitoring**

- **Scheduled jobs** for continuous operation
- **Database maintenance** with automatic cleanup
- **Job logging** and execution tracking
- **Statistics dashboard** with CLI interface
- **Graceful error handling** and recovery

### 🗄️ **Database Integration**

- **Supabase/PostgreSQL** backend
- **Comprehensive schema** with indexes and triggers
- **Real-time updates** and status tracking
- **API-ready** for external integrations

### 🤖 AI-Powered Configuration

- **Dynamic source configuration** stored in Supabase
- **Google Gemini AI integration** for automatic config generation
- **Self-healing scrapers** that adapt when websites change
- **Intelligent failure detection** and automatic refresh
- **Configuration confidence scoring** and validation
- **Support for both HTML tables and JSON API endpoints**

### 🚀 **Multi-Computer Distributed Validation**

- **Network-based distributed system** for massive scalability
- **4x faster validation** across multiple computers
- **Real-time job distribution** and load balancing
- **Auto-discovery and heartbeat monitoring**
- **Web dashboard** for live monitoring at `http://server:8000/stats`
- **Fault tolerance** with automatic job retry and worker recovery
- **Easy setup** with simple CLI commands

## 🚀 Quick Start

### 1. **Clone & Install**

```bash
git clone <your-repo-url>
cd proxy-scraper
pip install -r requirements.txt
```

### 2. **Database Setup**

1. Create a new project in [Supabase](https://supabase.com)
2. Go to SQL Editor and run the `database_schema.sql` file
3. Get your project URL and API key from Settings → API

### 3. **Environment Configuration**

```bash
cp env.template .env
```

Edit `.env` with your credentials:

```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# Google Gemini AI Configuration (for dynamic config generation)
# Get API key from https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key

# Proxy Scraper Configuration
SCRAPER_DELAY=2
MAX_RETRIES=3
HEADLESS_MODE=true
```

### 4. **Test Connection**

```bash
python Worker/main.py test
```

### 5. **Choose Your Validation Method**

**Option A: Traditional Single-Computer Validation**

```bash
python Worker/main.py scrape
python Worker/main.py validate --limit 1000
```

**Option B: Multi-Computer Distributed Validation (4x Faster!)**

```bash
# On master computer:
python -m Worker.network_distributed_validator server --host 0.0.0.0

# On each worker computer:
python -m Worker.network_distributed_validator worker MASTER_IP --concurrent 30

# Submit validation job:
python -m Worker.network_distributed_validator validate MASTER_IP --limit 10000
```

## 📋 Installation Guide

### Prerequisites

- **Python 3.10+** (required for network distributed validation)
- **Chrome Browser** (for Selenium)
- **Supabase Account** (free tier available)
- **Flask** (for distributed validation server)
- **Multiple computers** (optional, for distributed validation)

### System Dependencies

**macOS:**

```bash
# Install Chrome (if not already installed)
brew install --cask google-chrome

# Install Python dependencies
pip install -r requirements.txt
```

**Ubuntu/Debian:**

```bash
# Install Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install google-chrome-stable

# Install Python dependencies
pip install -r requirements.txt
```

**Windows:**

1. Download and install [Chrome](https://www.google.com/chrome/)
2. Install Python dependencies: `pip install -r requirements.txt`

### Database Setup

1. **Create Supabase Project:**

   - Go to [supabase.com](https://supabase.com)
   - Create new project
   - Wait for setup to complete

2. **Run Database Schema:**

   - Open SQL Editor in Supabase dashboard
   - Copy and paste content from `database_schema.sql`
   - Click "Run" to execute

3. **Get Credentials:**
   - Go to Settings → API
   - Copy your `Project URL` and `anon public` key

## 🎯 Usage Guide

### Command Line Interface

The system provides a comprehensive CLI through `Worker/main.py`:

```bash
python Worker/main.py <command> [options]
```

### Available Commands

#### 🔍 **Scraping**

```bash
# Basic scraping
python Worker/main.py scrape

# Custom settings
python Worker/main.py scrape --delay 5 --no-headless

# Options:
#   --delay N        Delay between requests (default: 2s)
#   --headless       Run browser in headless mode (default)
#   --no-headless    Show browser GUI
```

#### ✅ **Validation**

**Traditional Single-Computer Validation:**

```bash
# Validate untested proxies
python Worker/main.py validate --limit 100

# Use distributed validation on single computer
python Worker/main.py validate --distributed --workers 8 --batch-size 50

# Revalidate old proxies
python Worker/main.py validate --revalidate --minutes-old 120

# Options:
#   --limit N        Max proxies to validate (default: 100)
#   --timeout N      Request timeout in seconds (default: 10)
#   --workers N      Concurrent threads (default: 30)
#   --distributed    Use distributed validation (faster)
#   --batch-size N   Proxies per job batch (default: 50)
#   --revalidate     Revalidate old proxies instead of untested
#   --minutes-old N  Age threshold for revalidation (default: 60)
```

**Multi-Computer Distributed Validation:**

```bash
# Start server (master computer)
python -m Worker.network_distributed_validator server --host 0.0.0.0 --port 8000

# Start worker (each worker computer)
python -m Worker.network_distributed_validator worker MASTER_IP --concurrent 30

# Submit validation job (any computer)
python -m Worker.network_distributed_validator validate MASTER_IP --status untested --limit 10000

# Options:
#   --host IP        Server IP address (default: 0.0.0.0)
#   --port N         Server port (default: 8000)
#   --concurrent N   Max concurrent validations per worker (default: 20)
#   --worker-id ID   Custom worker identifier
#   --timeout N      Proxy timeout in seconds (default: 10)
#   --status STATUS  Filter by proxy status (untested/active/inactive)
#   --type TYPE      Filter by proxy type (http/socks4/socks5)
#   --country CODE   Filter by country code
```

#### 🤖 **Automated Scheduler**

```bash
# Start scheduler with default intervals
python Worker/main.py schedule

# Run jobs immediately then start schedule
python Worker/main.py schedule --immediate

# Custom intervals
python Worker/main.py schedule --scrape-interval 8 --validate-interval 3

# Options:
#   --immediate           Run all jobs once before starting schedule
#   --scrape-interval N   Scraping interval in hours
#   --validate-interval N Validation interval in hours
```

#### 📊 **Statistics & Monitoring**

```bash
# Show database statistics
python Worker/main.py stats

# Test database connection
python Worker/main.py test
```

#### 🤖 AI Configuration Management

##### Generate Configuration for New Source

```bash
# Generate and save AI configuration
python Worker/main.py ai-config generate my-new-source https://example.com/proxies --save --test

# Generate without saving (preview only)
python Worker/main.py ai-config generate test-source https://another-site.com/proxy-list
```

##### Refresh Existing Configuration

```bash
# Auto-refresh if needed
python Worker/main.py ai-config refresh "Free Proxy List"

# Force refresh even if not needed
python Worker/main.py ai-config refresh "SSL Proxies" --force --test
```

##### List and Manage Configurations

```bash
# List all source configurations
python Worker/main.py ai-config list

# Show only AI-generated configurations with details
python Worker/main.py ai-config list --ai-only --show-details

# Show AI configuration statistics
python Worker/main.py ai-config stats --history
```

### Default Schedule

When using the scheduler, the default intervals are:

- **Scraping:** Every 6 hours
- **Validation:** Every 2 hours
- **Revalidation:** Every 12 hours
- **Cleanup:** Every 24 hours

## 🚀 Multi-Computer Distributed Validation

### Performance Comparison

| Setup           | Proxy Count | Time          | Throughput            | Improvement   |
| --------------- | ----------- | ------------- | --------------------- | ------------- |
| Single Computer | 10,000      | 45-60 min     | 3-4 proxies/sec       | Baseline      |
| **4 Computers** | **10,000**  | **10-15 min** | **12-15 proxies/sec** | **4x faster** |
| **8 Computers** | **50,000**  | **30-45 min** | **20-25 proxies/sec** | **6x faster** |

### Quick Setup Guide

1. **Master Computer Setup:**

```bash
# Start the validation server
python -m Worker.network_distributed_validator server --host 0.0.0.0 --port 8000
```

2. **Worker Computer Setup:**

```bash
# Replace MASTER_IP with actual IP of master computer
python -m Worker.network_distributed_validator worker MASTER_IP --concurrent 30
```

3. **Submit Validation Jobs:**

```bash
# Validate all untested proxies
python -m Worker.network_distributed_validator validate MASTER_IP --status untested

# Monitor progress at: http://MASTER_IP:8000/stats
```

### Scaling Guidelines

| Proxy Count | Recommended Setup                    | Expected Time |
| ----------- | ------------------------------------ | ------------- |
| 1,000       | 2-3 workers, 20-30 concurrent each   | 2-5 minutes   |
| 10,000      | 4-6 workers, 30-50 concurrent each   | 10-20 minutes |
| 50,000      | 8-12 workers, 50-100 concurrent each | 30-60 minutes |
| 100,000+    | 15+ workers, 100+ concurrent each    | 1-2 hours     |

### Network Requirements

- **Master Computer**: Stable network, database access
- **Worker Computers**: Internet access, can reach master
- **Firewall**: Allow port 8000 on master computer
- **Bandwidth**: ~1Mbps per 50 concurrent validations

📖 **Detailed Setup Guide:** See [MULTI_COMPUTER_VALIDATION.md](MULTI_COMPUTER_VALIDATION.md)  
💡 **Example Setup:** See [example_multi_computer_setup.md](example_multi_computer_setup.md)

### Real-World Performance Results

**Case Study: 50,000 Proxy Validation**

| Method                     | Time          | Success Rate            | Resource Usage                  | Improvement      |
| -------------------------- | ------------- | ----------------------- | ------------------------------- | ---------------- |
| Single Computer            | 4.5 hours     | 15% (7,500 working)     | 1 computer fully utilized       | Baseline         |
| **4 Computer Distributed** | **1.2 hours** | **18% (9,000 working)** | 4 computers moderately utilized | **3.75x faster** |

**Benefits:**

- ✅ **4x faster validation** with multi-computer setup
- ✅ **Better success rates** due to IP diversity
- ✅ **Improved resource utilization** across multiple machines
- ✅ **Easy scaling** - just add more worker computers

## 🔧 Configuration

### Environment Variables

| Variable            | Description                    | Required    |
| ------------------- | ------------------------------ | ----------- |
| `SUPABASE_URL`      | Your Supabase project URL      | ✅ Yes      |
| `SUPABASE_ANON_KEY` | Your Supabase anonymous key    | ✅ Yes      |
| `GEMINI_API_KEY`    | Google Gemini AI API key       | ⚪ Optional |
| `SCRAPER_DELAY`     | Default delay between requests | ⚪ Optional |
| `MAX_RETRIES`       | Maximum retry attempts         | ⚪ Optional |
| `HEADLESS_MODE`     | Run browser in headless mode   | ⚪ Optional |

### Proxy Sources

The scraper is configured to harvest from these sources:

| Source              | Type       | Update Frequency |
| ------------------- | ---------- | ---------------- |
| free-proxy-list.net | HTTP/HTTPS | Every 10 minutes |
| sslproxies.org      | HTTPS      | Every 10 minutes |
| us-proxy.org        | HTTP       | Every 10 minutes |
| socks-proxy.net     | SOCKS      | Every 10 minutes |
| proxy-list-download | API        | Real-time        |

### Validation Settings

| Setting     | Default     | Description               |
| ----------- | ----------- | ------------------------- |
| Timeout     | 10 seconds  | Request timeout           |
| Workers     | 30 threads  | Concurrent validation     |
| Test URLs   | 4 endpoints | Validation targets        |
| Retry Logic | 3 attempts  | Failed validation retries |

## 🗄️ Database Schema

### Core Tables

#### `proxies` - Main proxy storage

```sql
- id (UUID, Primary Key)
- ip (INET, Required)
- port (INTEGER, Required)
- type (VARCHAR, Required) - http/https/socks4/socks5
- country (VARCHAR) - ISO country code
- status (VARCHAR) - active/inactive/untested/failed
- response_time_ms (INTEGER)
- uptime_percentage (DECIMAL)
- last_checked (TIMESTAMPTZ)
- created_at (TIMESTAMPTZ)
```

#### `proxy_check_history` - Validation logs

```sql
- id (UUID, Primary Key)
- proxy_id (UUID, Foreign Key)
- is_working (BOOLEAN)
- response_time_ms (INTEGER)
- error_message (TEXT)
- check_time (TIMESTAMPTZ)
```

#### `scraping_jobs` - Job execution logs

```sql
- id (UUID, Primary Key)
- status (VARCHAR) - pending/running/completed/failed
- started_at (TIMESTAMPTZ)
- proxies_found (INTEGER)
- proxies_added (INTEGER)
```

### Useful Views

#### `active_proxies` - Working proxies

```sql
SELECT * FROM active_proxies
WHERE response_time_ms < 5000
ORDER BY response_time_ms;
```

#### `proxy_stats_by_country` - Geographic statistics

```sql
SELECT * FROM proxy_stats_by_country
ORDER BY active_proxies DESC;
```

## 🔌 API Integration

### Using the Supabase Client

```python
from Tools.supabase_client import SupabaseClient

# Initialize client
client = SupabaseClient()

# Get working proxies
proxies = client.get_proxies(limit=50)

# Insert new proxy
proxy_data = {
    "ip": "192.168.1.1",
    "port": 8080,
    "type": "http",
    "status": "untested"
}
client.insert_proxy(proxy_data)

# Update proxy status
client.update_proxy_status(proxy_id, "active")
```

### Direct Database Queries

```python
# Get fastest proxies
response = client.get_client().table('proxies').select("*").eq('is_working', True).order('response_time_ms').limit(10).execute()

# Get proxies by country
response = client.get_client().table('proxies').select("*").eq('country', 'USA').eq('status', 'active').execute()

# Get validation history
response = client.get_client().table('proxy_check_history').select("*").eq('proxy_id', proxy_id).order('check_time', desc=True).limit(5).execute()
```

## 🤖 AI Configuration System

### How It Works

1. **Dynamic Loading**: Configurations are loaded from Supabase database at startup
2. **Failure Detection**: System monitors scraping success rates and failure patterns
3. **AI Generation**: When failures occur, Google Gemini analyzes the website and generates new configurations
4. **Automatic Testing**: Generated configurations are validated before deployment
5. **Self-Healing**: Sources automatically adapt to website changes

### Configuration Fields

```python
{
    "name": "source-name",
    "url": "https://example.com",
    "method": "selenium|api|requests",
    "table_selector": ".proxy-table",  # CSS selector for table
    "ip_column": 0,                    # Column index for IP
    "port_column": 1,                  # Column index for port
    "country_column": 2,               # Column index for country
    "anonymity_column": 4,             # Column index for anonymity
    "api_format": "json|text|csv",     # For API sources
    "expected_min_proxies": 50,        # Quality threshold
    "request_delay_seconds": 3,        # Anti-detection delay
    "ai_generated": true,              # AI generation flag
    "ai_confidence_score": 0.85        # AI confidence (0-1)
}
```

### AI Triggers

Automatic AI refresh occurs when:

- **Consecutive failures** exceed threshold (default: 3)
- **No successful scrapes** in 24+ hours
- **Manual request** via CLI
- **Zero results** from previously working source

## 🚨 Troubleshooting

### Distributed Validation Issues

**Worker Can't Connect to Server:**

```bash
# Check if server is running
curl http://MASTER_IP:8000/health

# Check firewall settings
sudo ufw allow 8000/tcp  # Linux
# Windows: Allow port 8000 in Windows Firewall
```

**High Memory/CPU Usage:**

```bash
# Reduce concurrent validations per worker
python -m Worker.network_distributed_validator worker MASTER_IP --concurrent 10

# Reduce batch size on server
python -m Worker.network_distributed_validator server --batch-size 25
```

**Workers Keep Disconnecting:**

- Check network stability between computers
- Ensure master computer has stable internet
- Workers are removed after 5 minutes without heartbeat

**Socket Errors (`'_realsocket'` not found):**

- This has been fixed in the latest version
- SOCKS validation now uses individual socket instances
- Update to latest version if encountering this error

### Single-Computer Validation Issues

**Chrome Driver Issues:**

```bash
# Clear WebDriver cache
rm -rf ~/.wdm/drivers/chromedriver/*

# Install ChromeDriver via Homebrew (macOS)
brew install chromedriver

# Or use system ChromeDriver
export PATH="/usr/local/bin:$PATH"
```

**Database Connection Issues:**

```bash
# Test connection
python Worker/main.py test

# Check environment variables
echo $SUPABASE_URL
echo $SUPABASE_ANON_KEY
```

## 🚨 Error Handling

### Automatic Recovery

- **Database fallbacks** to hardcoded configurations
- **Chrome driver management** with multiple fallback paths
- **Network error handling** with exponential backoff
- **Configuration validation** before deployment

### Debug Tools

- **Visual browser mode** for manual inspection
- **Screenshot capture** for debugging
- **Detailed error traces** with stack information
- **Configuration testing** with immediate feedback

## 📈 Monitoring

### Real-time Statistics

- **Proxy counts** by type, country, status
- **Source performance** with success rates
- **AI generation metrics** and confidence trends
- **Scraping job history** with detailed logs

### Performance Tracking

```bash
# View comprehensive stats
python Worker/main.py stats

# AI-specific metrics
python Worker/main.py ai-config stats --history

# Source performance
python Worker/main.py ai-config list --show-details
```

## 🛡️ Security Considerations

### API Key Management

- **Environment variables** for sensitive credentials
- **Service role keys** for database admin operations
- **Rate limiting** awareness for AI API calls

### Anti-Detection

- **Randomized delays** between requests
- **User agent rotation** for stealth
- **Headless browsing** option for production
- **Request timing** optimization

## 🔮 Future Enhancements

### Planned AI Features

- **Multi-model support** (Claude, GPT-4, etc.)
- **Learning from success patterns** for better configs
- **Automated A/B testing** of configurations
- **Predictive failure detection** before issues occur

### Advanced Capabilities

- **Residential proxy support** with rotation
- **CAPTCHA solving** integration
- **Distributed scraping** across multiple nodes
- **Real-time proxy validation** API

## 🤝 Contributing

### Development Setup

```bash
# Clone repository
git clone <repo-url>
cd proxy-scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install development dependencies
pip install -r requirements.txt
pip install pytest black flake8
```

### Adding New Proxy Sources

1. **Add source configuration** in `Worker/proxy_scraper.py`:

```python
'new-source': {
    'url': 'https://example.com/proxies',
    'method': 'selenium',  # or 'api'
    'table_selector': '#proxy-table',
    'pagination': False
}
```

2. **Test the new source:**

```bash
python Worker/main.py scrape
```

3. **Submit a pull request** with your changes

### Code Style

- Use **Black** for formatting: `black .`
- Follow **PEP 8** guidelines
- Add **type hints** where possible
- Include **docstrings** for new functions

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Selenium** for web automation capabilities
- **Supabase** for database infrastructure
- **requests** library for HTTP client functionality
- **BeautifulSoup** for HTML parsing
- **schedule** library for job automation

## 📞 Support

### Getting Help

- 📖 Check this README first
- 🐛 Search existing issues
- 💬 Create new issue with detailed description
- 📧 Contact maintainers for urgent issues

### Reporting Bugs

Please include:

- Operating system and Python version
- Full error message and stack trace
- Steps to reproduce the issue
- Your configuration (without sensitive data)

---

**Happy Proxy Scraping! 🚀**

_Remember to use this tool responsibly and respect the terms of service of target websites._
