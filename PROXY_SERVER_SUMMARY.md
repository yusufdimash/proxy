# Rotating HTTP Proxy Server - Implementation Summary

This document provides a complete overview of the **actual HTTP proxy server** implementation for your proxy scraper project.

## 🎯 What This Actually Does

This is **NOT a REST API** that returns proxy info in JSON. This is an **actual HTTP proxy server** that you configure in your browser or curl. When you use it as a proxy, it routes your traffic through the proxies in your database.

## ✅ Exactly What You Requested

### **Directory Structure** (As Requested)

```
proxy-scraper/
├── Api/                      # All API related files
│   ├── __init__.py
│   ├── proxy_manager.py      # Core proxy rotation logic
│   ├── proxy_server.py       # HTTP Proxy Server (MAIN FILE)
│   ├── start_proxy_server.py # Easy startup script
│   ├── test_proxy_server.py  # Testing script
│   └── README.md             # Comprehensive documentation
├── Tools/                    # Tools (already existed)
│   ├── supabase_client.py    # Database connection
│   └── gemini_client.py      # AI tools
└── Worker/                   # Scraping & validation (already existed)
    ├── main.py               # Worker orchestration
    ├── proxy_scraper.py      # Proxy collection
    └── proxy_validator.py    # Proxy validation
```

### **Three Main Modes** (Exactly As Requested)

#### 1. **Always Rotating Mode** - `--mode rotating`

- ✅ **Changes proxy for every request** automatically
- ✅ Each HTTP/HTTPS request uses a different proxy
- ✅ Automatic failover if proxy fails

#### 2. **Manual Refresh Mode** - `--mode manual`

- ✅ **Uses same proxy** until refresh is triggered
- ✅ Consistent proxy for multiple requests
- ✅ Only changes when refresh endpoint is hit

#### 3. **Refresh Trigger** - `http://localhost:3333/refresh`

- ✅ **Triggers update** for manual refresh mode
- ✅ Forces proxy list refresh from database
- ✅ Only works in manual mode

## 🚀 Quick Start Guide

### 1. Setup Environment

```bash
# Make sure your .env has Supabase credentials
cp env.template .env
# Edit .env with your credentials
```

### 2. Start the Proxy Server

```bash
# Start rotating mode (proxy changes each request)
python Api/start_proxy_server.py --mode rotating --port 3333

# Start manual mode (proxy stays same until refresh)
python Api/start_proxy_server.py --mode manual --port 3333
```

### 3. Configure Your Browser/Application

**Set your HTTP and HTTPS proxy to:**

- **Host:** `localhost`
- **Port:** `3333`

### 4. Test the Proxy

```bash
# Test with curl
curl --proxy localhost:3333 http://httpbin.org/ip
curl --proxy localhost:3333 https://httpbin.org/ip

# Test the proxy functionality
python Api/test_proxy_server.py
```

## 🌐 How to Use

### **Browser Configuration**

1. Open your browser proxy settings
2. Set HTTP Proxy: `localhost:3333`
3. Set HTTPS Proxy: `localhost:3333`
4. Now all your browser traffic goes through the proxy server

### **Curl Usage**

```bash
# HTTP requests
curl --proxy localhost:3333 http://httpbin.org/ip
curl --proxy localhost:3333 http://ipinfo.io/json

# HTTPS requests
curl --proxy localhost:3333 https://httpbin.org/ip
curl --proxy localhost:3333 https://google.com
```

### **Programming Usage**

```python
import requests

# Configure requests to use the proxy
proxies = {
    'http': 'http://localhost:3333',
    'https': 'http://localhost:3333'
}

# All requests now go through your proxy server
response = requests.get('http://httpbin.org/ip', proxies=proxies)
print(response.json())  # Shows the IP of the proxy from your database
```

## 🔄 The Three Modes Explained

### Mode 1: Rotating (`--mode rotating`)

```bash
python Api/start_proxy_server.py --mode rotating

# Each request automatically uses a different proxy:
curl --proxy localhost:3333 http://httpbin.org/ip  # Uses proxy A
curl --proxy localhost:3333 http://httpbin.org/ip  # Uses proxy B
curl --proxy localhost:3333 http://httpbin.org/ip  # Uses proxy C
```

### Mode 2: Manual (`--mode manual`)

```bash
python Api/start_proxy_server.py --mode manual

# Same proxy until you trigger refresh:
curl --proxy localhost:3333 http://httpbin.org/ip  # Uses proxy A
curl --proxy localhost:3333 http://httpbin.org/ip  # Uses proxy A (same)
curl --proxy localhost:3333 http://httpbin.org/ip  # Uses proxy A (same)
```

### Mode 3: Manual Refresh

```bash
# Trigger refresh (only works in manual mode)
curl --proxy localhost:3333 http://localhost:3333/refresh

# Now the proxy changes:
curl --proxy localhost:3333 http://httpbin.org/ip  # Uses proxy B (new!)
curl --proxy localhost:3333 http://httpbin.org/ip  # Uses proxy B (same)
```

## 🔧 Technical Implementation

### **HTTP Proxy Server** (`Api/proxy_server.py`)

- ✅ **Real HTTP proxy** that handles CONNECT requests (HTTPS)
- ✅ **Thread-safe proxy rotation**
- ✅ **Automatic proxy failover**
- ✅ **HTTPS tunneling support**
- ✅ **Manual refresh endpoint**

### **ProxyManager** (`Api/proxy_manager.py`)

- ✅ **Database integration** with existing Supabase
- ✅ **Thread-safe operations**
- ✅ **Failed proxy handling**
- ✅ **HTTPS proxy prioritization**

### **Key Features**

- ✅ **Actual HTTP Proxy**: Not an API, but a real proxy server
- ✅ **Browser Compatible**: Works with any browser/application
- ✅ **HTTPS Support**: Full HTTPS tunneling via CONNECT
- ✅ **Database Integration**: Uses your existing proxy database
- ✅ **Worker Integration**: Leverages existing scrapers/validators

## 💡 Real-World Usage Examples

### **Web Scraping with Rotating Proxies**

```python
import requests

# Set up proxy configuration
proxies = {
    'http': 'http://localhost:3333',
    'https': 'http://localhost:3333'
}

# Each request automatically uses a different proxy (rotating mode)
for i in range(10):
    response = requests.get('http://httpbin.org/ip', proxies=proxies)
    ip = response.json()['origin']
    print(f"Request {i+1}: {ip}")  # Different IP each time!
```

### **Browser Automation with Selenium**

```python
from selenium import webdriver
from selenium.webdriver.common.proxy import Proxy, ProxyType

# Configure Selenium to use your proxy server
proxy = Proxy()
proxy.proxy_type = ProxyType.MANUAL
proxy.http_proxy = "localhost:3333"
proxy.ssl_proxy = "localhost:3333"

capabilities = webdriver.DesiredCapabilities.CHROME
proxy.add_to_capabilities(capabilities)

driver = webdriver.Chrome(desired_capabilities=capabilities)
driver.get("http://httpbin.org/ip")  # Uses proxy from your database
```

### **Consistent Sessions (Manual Mode)**

```python
import requests

# Start server in manual mode
# python Api/start_proxy_server.py --mode manual

proxies = {'http': 'http://localhost:3333', 'https': 'http://localhost:3333'}

# All requests use the same proxy until refresh
session = requests.Session()
session.proxies = proxies

# Same proxy for all these requests
response1 = session.get('http://httpbin.org/ip')
response2 = session.get('http://ipinfo.io/json')
response3 = session.get('http://httpbin.org/user-agent')

# Trigger refresh
session.get('http://localhost:3333/refresh')

# Now uses a new proxy
response4 = session.get('http://httpbin.org/ip')  # New IP!
```

## 📊 Server Modes Comparison

| Feature                 | Rotating Mode           | Manual Mode          |
| ----------------------- | ----------------------- | -------------------- |
| **Proxy Changes**       | Every request           | Only on refresh      |
| **Use Case**            | Web scraping, anonymity | Consistent sessions  |
| **Refresh Trigger**     | Automatic               | Manual endpoint      |
| **Session Consistency** | No                      | Yes (until refresh)  |
| **Best For**            | High volume scraping    | Login sessions, APIs |

## 🚀 Integration with Your Existing System

### **Seamless Database Integration**

- ✅ Uses your existing Supabase database
- ✅ Reads from the same `proxies` table
- ✅ Respects `is_working` and `supports_https` flags
- ✅ Updates proxy status when failed

### **Worker Integration**

- ✅ Automatically uses newly scraped proxies
- ✅ Works with existing validation system
- ✅ Integrates with health monitoring

### **Zero Configuration Required**

- ✅ Uses existing `Tools/supabase_client.py`
- ✅ Leverages existing database schema
- ✅ No changes needed to workers or tools

## ⚙️ Configuration Options

### **Environment Variables**

```env
# Required (same as your existing setup)
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key

# Optional proxy server settings
PROXY_HOST=localhost
PROXY_PORT=3333
PROXY_MODE=rotating
```

### **Command Line Options**

```bash
python Api/start_proxy_server.py --help

Options:
  --host HOST     Host to bind to (default: localhost)
  --port PORT     Port to bind to (default: 3333)
  --mode MODE     rotating or manual (default: rotating)
  --check-env     Check environment variables
```

## 🎯 Perfect Match for Your Requirements

✅ **Directory Structure**: Exactly as requested - Api/, Tools/, Worker/  
✅ **Three Modes**: Exactly as specified - rotating, manual, refresh  
✅ **Rotating Behavior**: Changes proxy every request automatically  
✅ **Manual Control**: Only changes when refresh endpoint is hit  
✅ **Real Proxy Server**: Actually acts as HTTP/HTTPS proxy  
✅ **Browser Compatible**: Works with any application  
✅ **Database Integration**: Uses your existing system

## 🚀 Next Steps

1. **Start the proxy server**: `python Api/start_proxy_server.py --mode rotating`
2. **Configure your browser**: HTTP/HTTPS Proxy = `localhost:3333`
3. **Test it**: `curl --proxy localhost:3333 http://httpbin.org/ip`
4. **Run tests**: `python Api/test_proxy_server.py`

Now you have a **real HTTP proxy server** that routes traffic through your database proxies! 🎉

## 💡 Key Difference

**Before**: API that returns proxy info → You handle proxy configuration  
**Now**: Actual proxy server → You just set `localhost:3333` as your proxy

This is much simpler and exactly what you wanted! 🚀
