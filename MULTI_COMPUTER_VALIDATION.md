# Multi-Computer Distributed Proxy Validation

This guide explains how to set up proxy validation across multiple computers for maximum performance and scalability.

## 🏗️ Architecture Overview

```
Master Computer (Server)          Worker Computer 1           Worker Computer 2           Worker Computer N
┌─────────────────────┐           ┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│ ValidationServer    │◄──────────┤ RemoteValidation    │     │ RemoteValidation    │ ... │ RemoteValidation    │
│ - Job Management    │           │ Worker              │     │ Worker              │     │ Worker              │
│ - Worker Coordination│           │ - Proxy Validation  │     │ - Proxy Validation  │     │ - Proxy Validation  │
│ - Results Collection│           │ - HTTP/SOCKS Testing│     │ - HTTP/SOCKS Testing│     │ - HTTP/SOCKS Testing│
│ - Database Updates  │           └─────────────────────┘     └─────────────────────┘     └─────────────────────┘
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Supabase Database   │
│ - Proxy Storage     │
│ - Validation Results│
│ - Job History       │
└─────────────────────┘
```

## 📋 Requirements

### Master Computer

- Python 3.10+
- Network access to all worker computers
- Supabase database access
- Sufficient bandwidth for coordination

### Worker Computers

- Python 3.10+
- Network access to master computer
- Internet access for proxy testing
- No database access required

## 🚀 Quick Start

### 1. Install Dependencies

On all computers (master and workers):

```bash
# Clone the repository
git clone <repository-url>
cd proxy-scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

On the master computer, create `.env` file:

```bash
cp env.template .env
# Edit .env with your Supabase credentials
```

### 3. Start the Server (Master Computer)

```bash
# Start the validation server
python -m Worker.network_distributed_validator server --host 0.0.0.0 --port 8000

# Output:
# 🚀 Starting ValidationServer on 0.0.0.0:8000
# 📊 Server will be available at http://0.0.0.0:8000
# 📈 Stats endpoint: http://0.0.0.0:8000/stats
```

### 4. Start Workers (Each Worker Computer)

Replace `MASTER_IP` with the actual IP address of your master computer:

```bash
# Start a worker
python -m Worker.network_distributed_validator worker MASTER_IP --port 8000 --concurrent 30

# Output:
# 🚀 Starting RemoteValidationWorker: worker-hostname-12345678
# 🔗 Connecting to server: http://MASTER_IP:8000
# ✅ Worker worker-hostname-12345678 registered with server
```

### 5. Submit Validation Jobs

From any computer with network access to the master:

```bash
# Validate all untested proxies
python -m Worker.network_distributed_validator validate MASTER_IP --status untested

# Validate specific proxy types
python -m Worker.network_distributed_validator validate MASTER_IP --type http --limit 1000

# Validate by country
python -m Worker.network_distributed_validator validate MASTER_IP --country US --limit 500
```

## 🔧 Advanced Configuration

### Server Configuration

```bash
# Custom host and port
python -m Worker.network_distributed_validator server --host 192.168.1.100 --port 9000 --batch-size 100

# Parameters:
# --host: Server IP address (default: 0.0.0.0)
# --port: Server port (default: 8000)
# --batch-size: Proxies per job batch (default: 50)
```

### Worker Configuration

```bash
# Custom worker with specific settings
python -m Worker.network_distributed_validator worker 192.168.1.100 \
    --port 9000 \
    --worker-id "office-computer-1" \
    --timeout 15 \
    --concurrent 50

# Parameters:
# --port: Server port (default: 8000)
# --worker-id: Custom worker identifier
# --timeout: Proxy timeout in seconds (default: 10)
# --concurrent: Max concurrent validations (default: 20)
```

### Client Configuration

```bash
# Submit job with filters
python -m Worker.network_distributed_validator validate 192.168.1.100 \
    --port 9000 \
    --status active \
    --type socks5 \
    --country "United States" \
    --limit 2000
```

## 📊 Monitoring and Management

### Real-time Statistics

Visit `http://MASTER_IP:8000/stats` in your browser to see:

```json
{
  "server_stats": {
    "total_jobs_created": 150,
    "total_jobs_completed": 140,
    "total_proxies_validated": 7000,
    "total_working_proxies": 2100,
    "server_start_time": "2024-01-15T10:30:00"
  },
  "worker_count": 5,
  "queue_size": 8,
  "active_jobs": 2,
  "workers": {
    "worker-laptop-1": {
      "last_seen": "2024-01-15T11:45:30",
      "jobs_completed": 25,
      "hostname": "laptop-1"
    },
    "worker-desktop-2": {
      "last_seen": "2024-01-15T11:45:28",
      "jobs_completed": 32,
      "hostname": "desktop-2"
    }
  }
}
```

### Health Check

Check server health:

```bash
curl http://MASTER_IP:8000/health
```

### Progress Monitoring

The client automatically monitors progress and shows real-time updates:

```
📊 Progress: 15 jobs completed, 3 queued, 2 active, 5 workers, 45.2s elapsed
📊 Progress: 18 jobs completed, 1 queued, 1 active, 5 workers, 50.1s elapsed
✅ All validation jobs completed!
```

## 🔗 Network Setup

### Firewall Configuration

Ensure the master computer allows incoming connections on the server port:

**Linux/macOS:**

```bash
# Allow incoming connections on port 8000
sudo ufw allow 8000/tcp
```

**Windows:**

```cmd
# Add firewall rule for port 8000
netsh advfirewall firewall add rule name="Proxy Validator" dir=in action=allow protocol=TCP localport=8000
```

### Finding IP Address

**Linux/macOS:**

```bash
# Get IP address
ip addr show | grep inet
# or
ifconfig | grep inet
```

**Windows:**

```cmd
ipconfig | findstr IPv4
```

## ⚡ Performance Optimization

### Scaling Guidelines

| Proxy Count | Recommended Setup                    | Expected Time |
| ----------- | ------------------------------------ | ------------- |
| 1,000       | 2-3 workers, 20-30 concurrent each   | 2-5 minutes   |
| 10,000      | 4-6 workers, 30-50 concurrent each   | 10-20 minutes |
| 50,000      | 8-12 workers, 50-100 concurrent each | 30-60 minutes |
| 100,000+    | 15+ workers, 100+ concurrent each    | 1-2 hours     |

### Performance Tuning

1. **Batch Size**: Larger batches (50-100) reduce overhead but increase memory usage
2. **Concurrent Validations**: More concurrent validations = faster processing but higher resource usage
3. **Worker Distribution**: Spread workers across different networks for better IP diversity
4. **Network Location**: Workers closer to target proxy regions may perform better

### Resource Requirements

**Per Worker Computer:**

- **CPU**: 2+ cores recommended
- **RAM**: 2GB+ available
- **Network**: Stable internet connection
- **Bandwidth**: ~1Mbps per 50 concurrent validations

## 🚨 Troubleshooting

### Common Issues

**1. Worker Can't Connect to Server**

```bash
# Check if server is running
curl http://MASTER_IP:8000/health

# Check firewall settings
telnet MASTER_IP 8000
```

**2. High Memory Usage**

```bash
# Reduce concurrent validations per worker
python -m Worker.network_distributed_validator worker MASTER_IP --concurrent 10

# Reduce batch size on server
python -m Worker.network_distributed_validator server --batch-size 25
```

**3. Workers Disappearing**

- Workers are removed after 5 minutes without heartbeat
- Check network stability and server connectivity
- Restart workers if needed

**4. Slow Validation**

```bash
# Increase concurrent validations
python -m Worker.network_distributed_validator worker MASTER_IP --concurrent 50

# Reduce timeout for faster rejection of bad proxies
python -m Worker.network_distributed_validator worker MASTER_IP --timeout 5
```

### Debug Mode

Enable verbose logging by modifying the worker:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🔒 Security Considerations

1. **Network Security**: Use VPN or private networks when possible
2. **Access Control**: Restrict server access to trusted IP ranges
3. **Resource Limits**: Monitor resource usage to prevent abuse
4. **Data Protection**: Ensure Supabase credentials are secure

## 📈 Scaling Beyond Multiple Computers

For enterprise-scale validation:

1. **Cloud Deployment**: Deploy on AWS, GCP, or Azure for automatic scaling
2. **Container Orchestration**: Use Docker + Kubernetes for container management
3. **Load Balancing**: Use multiple server instances with load balancer
4. **Database Optimization**: Consider database connection pooling and read replicas

## 🎯 Use Cases

### Home Lab Setup

- Master: Main desktop/server
- Workers: Laptops, spare computers, Raspberry Pis

### Office Environment

- Master: Dedicated server
- Workers: Developer workstations during off-hours

### Cloud Deployment

- Master: Cloud server (AWS EC2, etc.)
- Workers: Multiple cloud instances in different regions

### Hybrid Setup

- Master: On-premises server
- Workers: Mix of local and cloud instances

## 📝 Example Deployment Script

Create `deploy_workers.sh` for easy worker deployment:

```bash
#!/bin/bash

MASTER_IP="192.168.1.100"
MASTER_PORT="8000"
CONCURRENT="30"

echo "Starting proxy validation worker..."
echo "Master server: $MASTER_IP:$MASTER_PORT"
echo "Concurrent validations: $CONCURRENT"

# Activate virtual environment
source venv/bin/activate

# Start worker with auto-restart
while true; do
    echo "$(date): Starting worker..."
    python -m Worker.network_distributed_validator worker $MASTER_IP \
        --port $MASTER_PORT \
        --concurrent $CONCURRENT \
        --timeout 10

    echo "$(date): Worker stopped. Restarting in 10 seconds..."
    sleep 10
done
```

Run on each worker computer:

```bash
chmod +x deploy_workers.sh
./deploy_workers.sh
```

This setup allows you to easily scale proxy validation across multiple computers, dramatically improving performance and reducing validation time!
