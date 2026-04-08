# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Logging service for the Data Center Cooling Environment server.

Handles container logs, request/response logging, and debugging information.
Logs are written to both an in-memory buffer (for API retrieval) and a rotating
file on disk (configurable via SERVER_LOG_FILE env var).
"""

import logging
import io
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import deque
from enum import Enum
from logging.handlers import RotatingFileHandler


class LogLevel(str, Enum):
    """Log levels for filtering."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogBuffer:
    """
    In-memory circular buffer for storing logs.
    
    Keeps the most recent N log entries in memory for quick retrieval.
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize the log buffer.
        
        Args:
            max_size: Maximum number of log entries to store
        """
        self.max_size = max_size
        self.logs: deque = deque(maxlen=max_size)
        self.start_time = datetime.utcnow()
    
    def add(self, level: str, message: str, extra: Optional[Dict] = None):
        """Add a log entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "extra": extra or {}
        }
        self.logs.append(entry)
    
    def get_all(self, level: Optional[str] = None) -> List[Dict]:
        """
        Retrieve all logs, optionally filtered by level.
        
        Args:
            level: Optional log level to filter by
            
        Returns:
            List of log entries
        """
        logs = list(self.logs)
        if level:
            logs = [log for log in logs if log["level"] == level.upper()]
        return logs
    
    def get_recent(self, count: int = 100, level: Optional[str] = None) -> List[Dict]:
        """
        Get the most recent N log entries.
        
        Args:
            count: Number of recent entries to retrieve
            level: Optional log level to filter by
            
        Returns:
            List of recent log entries
        """
        all_logs = self.get_all(level)
        return all_logs[-count:] if all_logs else []
    
    def clear(self):
        """Clear all logs."""
        self.logs.clear()
    
    def get_stats(self) -> Dict:
        """Get statistics about logged entries."""
        level_counts = {}
        for log in self.logs:
            level = log["level"]
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return {
            "total_entries": len(self.logs),
            "max_size": self.max_size,
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "by_level": level_counts
        }


class ContainerLogger:
    """
    Logger for container-specific information and debugging.

    Writes to:
    - stdout (console)
    - in-memory circular buffer (for /logs API endpoint)
    - rotating log file on disk (path from SERVER_LOG_FILE env var)
    """

    def __init__(self, max_buffer_size: int = 10000):
        """Initialize container logger."""
        self.buffer = LogBuffer(max_size=max_buffer_size)
        self.logger = logging.getLogger("container")
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure Python's built-in logging with console and file handlers."""
        if self.logger.handlers:
            return  # Already configured; avoid adding duplicate handlers

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(console_handler)

        # Rotating file handler — path and size from env vars
        log_file = os.getenv("SERVER_LOG_FILE", "server.log")
        max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB default
        backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

        try:
            log_dir = Path(log_file).parent
            if str(log_dir) != ".":
                log_dir.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)
        except Exception as exc:
            # Fall back to console-only if file handler setup fails
            self.logger.warning("Could not set up file logging (%s): %s", log_file, exc)

        self.logger.setLevel(logging.DEBUG)
    
    def debug(self, message: str, extra: Optional[Dict] = None):
        """Log debug message."""
        self.logger.debug(message)
        self.buffer.add("DEBUG", message, extra)
    
    def info(self, message: str, extra: Optional[Dict] = None):
        """Log info message."""
        self.logger.info(message)
        self.buffer.add("INFO", message, extra)
    
    def warning(self, message: str, extra: Optional[Dict] = None):
        """Log warning message."""
        self.logger.warning(message)
        self.buffer.add("WARNING", message, extra)
    
    def error(self, message: str, extra: Optional[Dict] = None):
        """Log error message."""
        self.logger.error(message)
        self.buffer.add("ERROR", message, extra)
    
    def critical(self, message: str, extra: Optional[Dict] = None):
        """Log critical message."""
        self.logger.critical(message)
        self.buffer.add("CRITICAL", message, extra)
    
    def get_logs(self, 
                 limit: int = 100, 
                 level: Optional[str] = None,
                 recent_only: bool = True) -> Dict:
        """
        Get formatted container logs.
        
        Args:
            limit: Maximum number of log entries to return
            level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            recent_only: If True, get recent logs; if False, get all
            
        Returns:
            Dictionary containing logs and metadata
        """
        if recent_only:
            logs = self.buffer.get_recent(count=limit, level=level)
        else:
            all_logs = self.buffer.get_all(level=level)
            logs = all_logs[-limit:] if all_logs else []
        
        return {
            "logs": logs,
            "count": len(logs),
            "stats": self.buffer.get_stats(),
            "filter": {
                "limit": limit,
                "level": level,
                "recent_only": recent_only
            }
        }
    
    def get_container_info(self) -> Dict:
        """Get container runtime information."""
        import socket
        return {
            "hostname": os.getenv("HOSTNAME", socket.gethostname()),
            "log_file": os.getenv("SERVER_LOG_FILE", "server.log"),
            "uptime": (datetime.utcnow() - self.buffer.start_time).total_seconds(),
            "log_buffer_size": self.buffer.max_size,
            "log_entries": len(self.buffer.logs),
            "start_time": self.buffer.start_time.isoformat(),
        }
    
    def get_health_status(self) -> Dict:
        """Get health status of the logger and container."""
        stats = self.buffer.get_stats()
        error_count = stats.get("by_level", {}).get("ERROR", 0)
        critical_count = stats.get("by_level", {}).get("CRITICAL", 0)
        
        health_status = "healthy"
        if critical_count > 0:
            health_status = "critical"
        elif error_count > 10:
            health_status = "degraded"
        
        return {
            "status": health_status,
            "error_count": error_count,
            "critical_count": critical_count,
            "total_logs": stats.get("total_entries", 0),
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global logger instance
_container_logger: Optional[ContainerLogger] = None


def get_container_logger() -> ContainerLogger:
    """Get or create the global container logger instance."""
    global _container_logger
    if _container_logger is None:
        _container_logger = ContainerLogger()
    return _container_logger


def log_request(method: str, path: str, status_code: int, client_ip: str = "unknown"):
    """Log an HTTP request."""
    logger = get_container_logger()
    logger.info(
        f"HTTP {method} {path}",
        extra={
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "client_ip": client_ip,
            "type": "http_request"
        }
    )


def log_environment_event(event_type: str, details: Optional[Dict] = None):
    """Log an environment-related event."""
    logger = get_container_logger()
    message = f"Environment: {event_type}"
    logger.info(message, extra={"event_type": event_type, "details": details or {}})


def log_websocket_event(event: str, client_id: str = "unknown", details: Optional[Dict] = None):
    """Log WebSocket events."""
    logger = get_container_logger()
    message = f"WebSocket {event} ({client_id})"
    logger.info(
        message,
        extra={
            "websocket_event": event,
            "client_id": client_id,
            "details": details or {}
        }
    )
