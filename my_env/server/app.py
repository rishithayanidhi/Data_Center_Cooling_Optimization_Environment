# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Data Center Cooling Optimization Environment.

This module creates an HTTP server that exposes the DataCenterCoolingEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions
    - GET /health: Health check
    - GET /docs: Interactive API documentation
    - GET /web: Web interface

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # With task selection:
    TASK_TYPE=hard uvicorn server.app:app --port 8000
"""

import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi import Request, Query
from starlette.types import ASGIApp, Receive, Scope, Send
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with 'uv sync'"
    ) from e

# Import logging service
try:
    from server.logging_service import get_container_logger, log_request
except ImportError:
    try:
        from .logging_service import get_container_logger, log_request
    except ImportError:
        from logging_service import get_container_logger, log_request

# Try different import styles for flexibility
try:
    from models import CoolingAction, CoolingObservation, CoolingState
    from server.environment import DataCenterCoolingEnvironment
except ImportError:
    try:
        from ..models import CoolingAction, CoolingObservation, CoolingState
        from .environment import DataCenterCoolingEnvironment
    except ImportError:
        from models import CoolingAction, CoolingObservation, CoolingState
        from environment import DataCenterCoolingEnvironment


# Get task type from environment variable
TASK_TYPE = os.getenv("TASK_TYPE", "easy").lower()
if TASK_TYPE not in ["easy", "medium", "hard"]:
    TASK_TYPE = "easy"

# Operational configuration from environment variables
MAX_CONCURRENT_ENVS = int(os.getenv("MAX_CONCURRENT_ENVS", "100"))
NUM_ZONES = int(os.getenv("NUM_ZONES", "4"))


class LoggingMiddleware:
    """ASGI middleware to log HTTP requests (skips WebSocket scopes)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            # Wrap send to capture the status code
            status_code = 200
            original_send = send

            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message.get("status", 200)
                await original_send(message)

            await self.app(scope, receive, send_wrapper)

            try:
                client = scope.get("client")
                client_ip = client[0] if client else "unknown"
                method = scope.get("method", "GET")
                path = scope.get("path", "/")
                log_request(method=method, path=path, status_code=status_code, client_ip=client_ip)
            except Exception:
                pass
        else:
            # Pass WebSocket and lifespan scopes through unchanged
            await self.app(scope, receive, send)


def environment_factory() -> DataCenterCoolingEnvironment:
    """Factory function to create new environment instances."""
    return DataCenterCoolingEnvironment(task_type=TASK_TYPE)


# Create the app with web interface and README integration
app = create_app(
    environment_factory,
    CoolingAction,
    CoolingObservation,
    env_name="datacenter_cooling",
    max_concurrent_envs=MAX_CONCURRENT_ENVS,
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Initialize logger
logger = get_container_logger()
logger.info("🚀 Data Center Cooling Environment Server initialized")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": "DataCenterCoolingEnvironment",
        "task_type": TASK_TYPE,
    }


@app.get("/info")
def environment_info():
    """Get environment information."""
    return {
        "name": "Data Center Cooling Optimization",
        "description": "Autonomous cooling management for data centers",
        "task_types": ["easy", "medium", "hard"],
        "current_task": TASK_TYPE,
        "num_zones": NUM_ZONES,
        "actions": {
            "zone_id": f"0-{NUM_ZONES - 1} (which zone to adjust)",
            "cooling_adjustment": "-1.0 to +1.0 (decrease/maintain/increase)",
        },
        "observations": [
            "zone_temperatures",
            "zone_workload_intensity", 
            "zone_cooling_levels",
            "total_energy_consumption",
            "ambient_temperature",
        ],
    }


@app.get("/logs")
def get_logs(limit: int = 100, level: Optional[str] = None, format: str = "json"):
    """
    Get container logs.
    
    Query Parameters:
    - limit: Maximum number of log entries to return (default: 100)
    - level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - format: Response format (json or text)
    
    Returns:
        Logs in JSON or plain text format
    """
    try:
        container_logger = get_container_logger()
        logs_data = container_logger.get_logs(limit=limit, level=level)
        
        if format == "text":
            # Convert to plain text format
            lines = []
            for log in logs_data["logs"]:
                timestamp = log.get("timestamp", "")
                log_level = log.get("level", "")
                message = log.get("message", "")
                lines.append(f"{timestamp} [{log_level}] {message}")
            
            return JSONResponse(
                content={
                    "format": "text",
                    "logs": "\n".join(lines),
                    "count": logs_data["count"],
                    "stats": logs_data["stats"]
                }
            )
        else:
            # Default JSON format
            return logs_data
    
    except Exception as e:
        logger = get_container_logger()
        logger.error(f"Error retrieving logs: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve logs: {str(e)}"}
        )


@app.get("/logs/stats")
def get_logs_stats():
    """
    Get container logging statistics.
    
    Returns:
        Statistics about logged entries and container health
    """
    try:
        container_logger = get_container_logger()
        return {
            "container_info": container_logger.get_container_info(),
            "health": container_logger.get_health_status(),
            "stats": container_logger.buffer.get_stats()
        }
    except Exception as e:
        logger = get_container_logger()
        logger.error(f"Error retrieving stats: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve stats: {str(e)}"}
        )


@app.get("/logs/clear")
def clear_logs():
    """
    Clear all stored logs (requires admin access).
    
    Note: This is for development only. In production, logs should be
    managed through a logging infrastructure.
    
    Returns:
        Confirmation message
    """
    try:
        # In production, you might want to add authentication here
        container_logger = get_container_logger()
        container_logger.buffer.clear()
        logger.info("Logs cleared via /logs/clear endpoint")
        return {
            "status": "success",
            "message": "All logs have been cleared",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger = get_container_logger()
        logger.error(f"Error clearing logs: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to clear logs: {str(e)}"}
        )


@app.get("/logs/container")
def get_container_logs():
    """
    Get container-specific logs with more details.
    
    This is the endpoint that external monitoring services may call.
    
    Returns:
        Container logs and metadata
    """
    try:
        container_logger = get_container_logger()
        logs_data = container_logger.get_logs(limit=200)
        
        return {
            "type": "container",
            "logs": logs_data["logs"],
            "summary": {
                "total": logs_data["count"],
                "container_info": container_logger.get_container_info(),
                "health": container_logger.get_health_status()
            }
        }
    except Exception as e:
        logger = get_container_logger()
        logger.error(f"Error retrieving container logs: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve container logs: {str(e)}"}
        )


@app.get("/")
def root(logs: Optional[str] = Query(default=None)):
    """
    Root endpoint. If ?logs=container is provided (e.g. by Hugging Face Spaces
    monitoring), returns container logs. Otherwise redirects to the web UI.
    """
    if logs == "container":
        try:
            container_logger = get_container_logger()
            logs_data = container_logger.get_logs(limit=200)
            return {
                "type": "container",
                "logs": logs_data["logs"],
                "summary": {
                    "total": logs_data["count"],
                    "container_info": container_logger.get_container_info(),
                    "health": container_logger.get_health_status(),
                },
            }
        except Exception as e:
            logger.error(f"Error retrieving container logs at root: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to retrieve container logs: {str(e)}"},
            )
    return RedirectResponse(url="/web")


@app.get("/web", response_class=HTMLResponse)
def web_interface():
    """Web interface for the Data Center Cooling Environment."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Data Center Cooling Environment</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px 20px;
                border-radius: 8px;
                margin-bottom: 30px;
            }
            .header h1 { margin: 0; font-size: 2.5em; }
            .header p { margin: 10px 0 0 0; opacity: 0.9; }
            
            .container {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .card h2 {
                margin-top: 0;
                color: #333;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }
            
            .info-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }
            
            .info-item {
                background: #f9f9f9;
                padding: 12px;
                border-radius: 4px;
                border-left: 4px solid #667eea;
            }
            
            .info-label {
                font-size: 0.85em;
                color: #666;
                text-transform: uppercase;
                font-weight: 600;
            }
            
            .info-value {
                font-size: 1.5em;
                color: #333;
                margin-top: 5px;
                font-weight: bold;
            }
            
            .status-healthy {
                color: #22c55e;
                font-weight: bold;
            }
            
            .task-badge {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.9em;
                margin-top: 10px;
            }
            
            .endpoints {
                background: #f0f4ff;
                padding: 15px;
                border-radius: 4px;
                margin-top: 15px;
            }
            
            .endpoints h3 {
                margin-top: 0;
                color: #667eea;
            }
            
            .endpoint-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            
            .endpoint-list li {
                padding: 8px 0;
                border-bottom: 1px solid #e0e0e0;
            }
            
            .endpoint-list li:last-child {
                border-bottom: none;
            }
            
            .endpoint-method {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 0.8em;
                font-weight: bold;
                min-width: 40px;
                text-align: center;
            }
            
            .endpoint-path {
                font-family: monospace;
                margin-left: 10px;
                color: #333;
            }
            
            .full-width {
                grid-column: 1 / -1;
            }
            
            .footer {
                text-align: center;
                color: #666;
                padding-top: 20px;
                border-top: 1px solid #e0e0e0;
            }
            
            .link {
                color: #667eea;
                text-decoration: none;
                font-weight: 500;
            }
            
            .link:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌡️ Data Center Cooling Environment</h1>
            <p>Autonomous cooling management for data centers</p>
        </div>
        
        <div class="container">
            <div class="card">
                <h2>Server Status</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Status</div>
                        <div class="info-value status-healthy">✓ Healthy</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Task Type</div>
                        <div class="info-value">""" + TASK_TYPE.upper() + """</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Zones</div>
                        <div class="info-value">4</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">API Version</div>
                        <div class="info-value">1.0</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>Quick Links</h2>
                <ul style="list-style: none; padding: 0; margin: 0;">
                    <li style="margin: 10px 0;">
                        <a href="/docs" class="link">📖 API Documentation (Swagger UI)</a>
                    </li>
                    <li style="margin: 10px 0;">
                        <a href="/redoc" class="link">📕 API Reference (ReDoc)</a>
                    </li>
                    <li style="margin: 10px 0;">
                        <a href="/health" class="link">💚 Health Check Endpoint</a>
                    </li>
                    <li style="margin: 10px 0;">
                        <a href="/info" class="link">ℹ️ Environment Info</a>
                    </li>
                    <li style="margin: 10px 0;">
                        <a href="/logs?limit=50" class="link">📋 Container Logs</a>
                    </li>
                    <li style="margin: 10px 0;">
                        <a href="/logs/stats" class="link">📊 Logging Stats</a>
                    </li>
                </ul>
            </div>
            
            <div class="card full-width">
                <h2>API Endpoints</h2>
                <div class="endpoints">
                    <h3>WebSocket</h3>
                    <ul class="endpoint-list">
                        <li>
                            <span class="endpoint-method">WS</span>
                            <span class="endpoint-path">/ws</span>
                            <span style="color: #666;"> — Persistent WebSocket connection for streaming interactions</span>
                        </li>
                    </ul>
                </div>
                <div class="endpoints">
                    <h3>HTTP (REST)</h3>
                    <ul class="endpoint-list">
                        <li>
                            <span class="endpoint-method">POST</span>
                            <span class="endpoint-path">/reset</span>
                            <span style="color: #666;"> — Reset environment to initial state</span>
                        </li>
                        <li>
                            <span class="endpoint-method">POST</span>
                            <span class="endpoint-path">/step</span>
                            <span style="color: #666;"> — Execute action and get observation</span>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/state</span>
                            <span style="color: #666;"> — Get current environment state</span>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/schema</span>
                            <span style="color: #666;"> — Get action/observation schemas</span>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/health</span>
                            <span style="color: #666;"> — Health check</span>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/info</span>
                            <span style="color: #666;"> — Environment information</span>
                        </li>
                    </ul>
                </div>
                <div class="endpoints">
                    <h3>Logging & Monitoring</h3>
                    <ul class="endpoint-list">
                        <li>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/logs</span>
                            <span style="color: #666;"> — Get container logs (supports ?limit=, ?level=)</span>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/logs/container</span>
                            <span style="color: #666;"> — Get container-specific logs and metadata</span>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/logs/stats</span>
                            <span style="color: #666;"> — Get logging statistics and health status</span>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/logs/clear</span>
                            <span style="color: #666;"> — Clear all stored logs (dev only)</span>
                        </li>
                    </ul>
                </div>
        </div>
        
        <div class="footer">
            <p>📚 Documentation: Check <a href="README.md" class="link">README.md</a> for training guides and examples.</p>
            <p>Built with <strong>OpenEnv</strong> • <strong>FastAPI</strong> • <strong>Python</strong></p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


def main(host: str = "0.0.0.0", port: int = 8000):
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        uv run --project . server --port 8001
        python -m my_env.server.app

    Args:
        host: Host address to bind to (default: "0.0.0.0")
        port: Port number to listen on (default: 8000)

    For production deployments, consider using uvicorn directly with
    multiple workers:
        uvicorn my_env.server.app:app --workers 4
    """
    import uvicorn

    print(f"\n🚀 Starting Data Center Cooling Environment Server")
    print(f"   Task Type: {TASK_TYPE}")
    print(f"   Host: {host}:{port}\n")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
