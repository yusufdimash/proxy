# Rotating Proxy API Server

A Flask-based API server that provides rotating proxy functionality with three main endpoints for different use cases.

## Features

- **Automatic Proxy Rotation**: Always get a different proxy on each request
- **Manual Refresh Control**: Get a consistent proxy until manually refreshed
- **Health Monitoring**: Automatic proxy health checking and failover
- **Database Integration**: Uses Supabase for proxy storage and management
- **Thread-Safe Operations**: Concurrent request handling
- **Comprehensive Statistics**: Detailed proxy pool information

## Endpoints

### Core Proxy Endpoints

#### 1. GET `/api/proxy/rotate`

**Always Rotating Proxy** - Returns a different proxy on every request.

```bash
curl http://localhost:5000/api/proxy/rotate
```

**Response:**

```json
{
  "status": "success",
  "proxy": {
    "id": "uuid-here",
    "ip": "192.168.1.1",
    "port": 8080,
    "type": "http",
    "country": "US",
    "anonymity_level": "elite",
    "response_time_ms": 150,
    "supports_https": true,
    "proxy_url": "http://192.168.1.1:8080"
  },
  "endpoint_type": "rotating",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "message": "Proxy rotates on every request"
}
```

#### 2. GET `/api/proxy/manual`

**Manual Refresh Proxy** - Returns the same proxy until manually refreshed.

```bash
curl http://localhost:5000/api/proxy/manual
```

**Response:**

```json
{
  "status": "success",
  "proxy": {
    "id": "uuid-here",
    "ip": "192.168.1.2",
    "port": 3128,
    "type": "https",
    "country": "UK",
    "anonymity_level": "anonymous",
    "response_time_ms": 200,
    "supports_https": true,
    "proxy_url": "http://192.168.1.2:3128"
  },
  "endpoint_type": "manual_refresh",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "message": "Proxy changes only when refresh endpoint is hit"
}
```

#### 3. POST `/api/proxy/refresh`

**Trigger Manual Refresh** - Updates the proxy for the manual endpoint.

```bash
curl -X POST http://localhost:5000/api/proxy/refresh
```

**Response:**

```json
{
  "status": "success",
  "message": "Proxy list refreshed successfully",
  "new_proxy": {
    "id": "new-uuid-here",
    "ip": "192.168.1.3",
    "port": 8888,
    "type": "http",
    "proxy_url": "http://192.168.1.3:8888"
  },
  "timestamp": "2024-01-15T10:30:00.000Z",
  "action": "manual_refresh_triggered"
}
```

### Utility Endpoints

#### GET `/api/health`

Health check for the API server.

```bash
curl http://localhost:5000/api/health
```

#### GET `/api/stats`

Get proxy pool statistics.

```bash
curl http://localhost:5000/api/stats
```

#### POST `/api/proxy/report-failed`

Report a proxy as failed.

```bash
curl -X POST http://localhost:5000/api/proxy/report-failed \
  -H "Content-Type: application/json" \
  -d '{"proxy_id": "uuid-of-failed-proxy"}'
```

#### GET `/api/endpoints`

List all available endpoints.

```bash
curl http://localhost:5000/api/endpoints
```

## Installation & Setup

### 1. Environment Setup

Create a `.env` file from the template:

```bash
cp env.template .env
```

Edit `.env` and set your Supabase credentials:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# Optional API server configuration
API_HOST=0.0.0.0
API_PORT=5000
API_DEBUG=false
```

### 2. Install Dependencies

```bash
pip install flask flask-cors python-dotenv
```

### 3. Start the Server

#### Using the startup script (recommended):

```bash
python Api/start_server.py
```

#### Direct execution:

```bash
python Api/server.py
```

#### With custom configuration:

```bash
python Api/start_server.py --host localhost --port 8080 --debug
```

### 4. Check Environment

```bash
python Api/start_server.py --check-env
```

## Usage Examples

### Basic Proxy Rotation

```python
import requests

# Get a rotating proxy (different each time)
response = requests.get('http://localhost:5000/api/proxy/rotate')
proxy_data = response.json()

if proxy_data['status'] == 'success':
    proxy_url = proxy_data['proxy']['proxy_url']

    # Use the proxy for your requests
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }

    result = requests.get('http://httpbin.org/ip', proxies=proxies)
    print(result.json())
```

### Manual Refresh Pattern

```python
import requests

# Get a consistent proxy
response = requests.get('http://localhost:5000/api/proxy/manual')
proxy_data = response.json()

# Use this proxy for multiple requests...
proxy_url = proxy_data['proxy']['proxy_url']

# When you want a new proxy, trigger refresh
requests.post('http://localhost:5000/api/proxy/refresh')

# Now get the new proxy
response = requests.get('http://localhost:5000/api/proxy/manual')
new_proxy_data = response.json()
```

### Error Handling

```python
import requests

def get_working_proxy():
    try:
        response = requests.get('http://localhost:5000/api/proxy/rotate')
        data = response.json()

        if response.status_code == 200 and data['status'] == 'success':
            return data['proxy']
        else:
            print(f"Error: {data.get('error', 'Unknown error')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return None

def report_failed_proxy(proxy_id):
    try:
        response = requests.post(
            'http://localhost:5000/api/proxy/report-failed',
            json={'proxy_id': proxy_id}
        )
        return response.status_code == 200
    except:
        return False
```

## Server Configuration

### Command Line Options

```bash
python Api/start_server.py --help
```

Options:

- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 5000)
- `--debug`: Enable debug mode
- `--check-env`: Check environment variables

### Environment Variables

- `SUPABASE_URL`: Your Supabase project URL (required)
- `SUPABASE_ANON_KEY`: Your Supabase anon key (required)
- `API_HOST`: Server host (optional, default: 0.0.0.0)
- `API_PORT`: Server port (optional, default: 5000)
- `API_DEBUG`: Debug mode (optional, default: false)

## Integration with Existing System

The API server integrates with your existing proxy scraper system:

- **Database**: Uses the same Supabase database as your scrapers
- **Proxy Pool**: Automatically loads working proxies from the database
- **Health Monitoring**: Integrates with the proxy validation system
- **Tools**: Uses the existing `Tools/supabase_client.py` for database operations

## Performance Notes

- The server is multi-threaded and can handle concurrent requests
- Proxy list is cached in memory and refreshed periodically
- Failed proxies are automatically removed from rotation
- HTTPS-capable proxies are prioritized when available

## Monitoring

Check server health:

```bash
curl http://localhost:5000/api/health
```

Get detailed statistics:

```bash
curl http://localhost:5000/api/stats
```

## Troubleshooting

### Common Issues

1. **No proxies available**: Run the proxy scraper to populate the database
2. **Connection errors**: Check your Supabase credentials in `.env`
3. **Permission errors**: Ensure the server has read access to the database

### Debug Mode

Start with debug mode for detailed logging:

```bash
python Api/start_server.py --debug
```

### Logs

The server outputs detailed logs including:

- Proxy refresh operations
- Failed proxy removals
- Health check results
- Error messages with timestamps
