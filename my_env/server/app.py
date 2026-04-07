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
from fastapi.responses import HTMLResponse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with 'uv sync'"
    ) from e

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


def environment_factory() -> DataCenterCoolingEnvironment:
    """Factory function to create new environment instances."""
    return DataCenterCoolingEnvironment(task_type=TASK_TYPE)


# Create the app with web interface and README integration
app = create_app(
    environment_factory,
    CoolingAction,
    CoolingObservation,
    env_name="datacenter_cooling",
    max_concurrent_envs=100,
)


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
        "num_zones": 4,
        "actions": {
            "zone_id": "0-3 (which zone to adjust)",
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
                    </ul>
                </div>
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
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--task", type=str, default="easy", choices=["easy", "medium", "hard"])
    args = parser.parse_args()
    
    # Override TASK_TYPE from command line if provided
    if args.task:
        os.environ["TASK_TYPE"] = args.task
    
    main(port=args.port)
