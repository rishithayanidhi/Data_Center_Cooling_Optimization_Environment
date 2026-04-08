# Container Logging System

## Overview

The Data Center Cooling Optimization Environment now includes a comprehensive logging system to handle container logs, request tracking, and debugging information.

## New Endpoints

### 1. `GET /logs`

Retrieve container logs with optional filtering.

**Query Parameters:**

- `limit` (int, default: 100): Maximum number of log entries to return
- `level` (str, optional): Filter by log level - `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `format` (str, default: json): Response format - `json` or `text`

**Example Requests:**

```bash
# Get last 100 logs
curl http://localhost:8000/logs

# Get last 50 INFO logs
curl "http://localhost:8000/logs?limit=50&level=INFO"

# Get last 20 ERROR logs in text format
curl "http://localhost:8000/logs?limit=20&level=ERROR&format=text"
```

**Response (JSON):**

```json
{
  "logs": [
    {
      "timestamp": "2026-04-08T08:56:31.123456",
      "level": "INFO",
      "message": "HTTP GET /health",
      "extra": {
        "http_method": "GET",
        "http_path": "/health",
        "http_status": 200,
        "client_ip": "10.16.8.212",
        "type": "http_request"
      }
    }
  ],
  "count": 1,
  "stats": {
    "total_entries": 150,
    "max_size": 10000,
    "start_time": "2026-04-08T08:56:30",
    "uptime_seconds": 1.5,
    "by_level": {
      "INFO": 120,
      "DEBUG": 20,
      "WARNING": 5,
      "ERROR": 5
    }
  },
  "filter": {
    "limit": 100,
    "level": null,
    "recent_only": true
  }
}
```

---

### 2. `GET /logs/container`

Get container-specific logs with metadata and health information.

**Purpose:** This is the endpoint that external monitoring services (like Hugging Face Spaces) call to fetch container logs.

**Example Request:**

```bash
curl http://localhost:8000/logs/container
```

**Response:**

```json
{
  "type": "container",
  "logs": [...],
  "summary": {
    "total": 150,
    "container_info": {
      "hostname": "data-center-cooling-env",
      "uptime": 125.5,
      "log_buffer_size": 10000,
      "log_entries": 150,
      "start_time": "2026-04-08T08:56:30.123456"
    },
    "health": {
      "status": "healthy",
      "error_count": 2,
      "critical_count": 0,
      "total_logs": 150,
      "timestamp": "2026-04-08T08:58:15.654321"
    }
  }
}
```

---

### 3. `GET /logs/stats`

Get detailed logging statistics and container health status.

**Example Request:**

```bash
curl http://localhost:8000/logs/stats
```

**Response:**

```json
{
  "container_info": {
    "hostname": "data-center-cooling-env",
    "uptime": 125.5,
    "log_buffer_size": 10000,
    "log_entries": 150,
    "start_time": "2026-04-08T08:56:30.123456"
  },
  "health": {
    "status": "healthy",
    "error_count": 2,
    "critical_count": 0,
    "total_logs": 150,
    "timestamp": "2026-04-08T08:58:15.654321"
  },
  "stats": {
    "total_entries": 150,
    "max_size": 10000,
    "start_time": "2026-04-08T08:56:30",
    "uptime_seconds": 125.5,
    "by_level": {
      "INFO": 120,
      "DEBUG": 20,
      "WARNING": 5,
      "ERROR": 5
    }
  }
}
```

**Health Status Values:**

- `healthy`: No errors or critical issues (✓ normal operation)
- `degraded`: More than 10 errors detected (⚠ warning)
- `critical`: One or more critical errors (✗ needs attention)

---

### 4. `GET /logs/clear`

Clear all stored logs (development only).

**Example Request:**

```bash
curl http://localhost:8000/logs/clear
```

**Response:**

```json
{
  "status": "success",
  "message": "All logs have been cleared",
  "timestamp": "2026-04-08T08:58:15.654321"
}
```

---

## Logging Middleware

All HTTP requests are automatically logged by the `LoggingMiddleware`. Each request creates an entry with:

- HTTP method (GET, POST, etc.)
- Request path
- Status code (200, 404, 500, etc.)
- Client IP address
- Timestamp

### Example Log Entry:

```json
{
  "timestamp": "2026-04-08T08:56:31.123456",
  "level": "INFO",
  "message": "HTTP GET /health",
  "extra": {
    "http_method": "GET",
    "http_path": "/health",
    "http_status": 200,
    "client_ip": "10.16.8.212",
    "type": "http_request"
  }
}
```

---

## Log Buffer

The logging system maintains an in-memory circular buffer of the most recent 10,000 log entries. This provides:

1. **Fast Access:** No need to read from disk
2. **Memory Efficient:** Fixed size buffer prevents unbounded growth
3. **Recent Data:** Always keeps the most relevant recent logs
4. **Graceful Overflow:** Oldest entries are automatically discarded when buffer is full

### Configuration

To change the buffer size, modify `logging_service.py`:

```python
_container_logger = ContainerLogger(max_buffer_size=20000)  # Increase to 20k entries
```

---

## Integration with External Monitoring

Services like Hugging Face Spaces can monitor container health by calling `/logs/container` periodically. The response includes:

1. Recent logs (up to 200 entries)
2. Container metadata (uptime, hostname)
3. Health status (healthy/degraded/critical)
4. Error and critical event counts

### Example Monitoring Script:

```python
import requests
import time

def monitor_container():
    while True:
        try:
            response = requests.get("http://localhost:8000/logs/container")
            data = response.json()

            health = data["summary"]["health"]
            print(f"Container Health: {health['status']}")
            print(f"Errors: {health['error_count']}, Critical: {health['critical_count']}")

            if health["status"] == "critical":
                # Alert or take action
                print("⚠️ CRITICAL HEALTH STATUS DETECTED!")

        except Exception as e:
            print(f"Error fetching logs: {e}")

        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    monitor_container()
```

---

## Python API

### Using the Logger in Your Code

```python
from server.logging_service import (
    get_container_logger,
    log_request,
    log_environment_event,
    log_websocket_event,
)

# Get the logger instance
logger = get_container_logger()

# Log different levels
logger.debug("Debug information", extra={"key": "value"})
logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")

# Helper functions for specific event types
log_request(method="POST", path="/reset", status_code=200, client_ip="127.0.0.1")
log_environment_event("episode_completed", {"reward": 350.5, "steps": 50})
log_websocket_event("connected", client_id="client_123", details={"version": "1.0"})

# Get logs programmatically
logs = logger.get_logs(limit=50, level="ERROR")
print(f"Total errors: {logs['count']}")

# Get health status
health = logger.get_health_status()
print(f"Container status: {health['status']}")
```

---

## Environment Variables

No special environment variables are required for logging. The system works automatically. However, you can control the logger behavior through code:

```python
from server.logging_service import get_container_logger

logger = get_container_logger()

# Clear logs periodically if needed
logger.buffer.clear()

# Get statistics
stats = logger.buffer.get_stats()
print(stats)
```

---

## Production Recommendations

1. **Log Persistence:** For production, consider integrating with logging services (Sentry, CloudWatch, Datadog, etc.)
2. **Log Rotation:** Current system uses in-memory buffer; add file logging for long-term retention
3. **Security:** The `/logs/clear` endpoint should be protected with authentication in production
4. **Performance:** The logging middleware adds minimal overhead (~1-2ms per request)

### Example: Adding File Logging

```python
import logging.handlers

handler = logging.handlers.RotatingFileHandler(
    "app.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
logger.logger.addHandler(handler)
```

---

## Troubleshooting

### Issue: 404 errors on `/logs` endpoints

**Solution:** Ensure the server is running with the latest app.py that includes the logging endpoints.

### Issue: Logs endpoint returns empty

**Solution:** This is normal if no requests have been made since startup. Make a request to any endpoint (e.g., `/health`) to generate logs.

### Issue: High memory usage

**Solution:** The buffer is capped at 10,000 entries by default. If it grows too large, it automatically discards old entries. You can also call `/logs/clear` to reset it.

---

## Web Interface

The web interface at `/web` includes quick links to:

- 📋 Container Logs (`/logs?limit=50`)
- 📊 Logging Stats (`/logs/stats`)

Visit [http://localhost:8000/web](http://localhost:8000/web) to access these links.

---

## API Documentation

Full interactive API documentation available at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

The logging endpoints are documented in the `/logs` section.
