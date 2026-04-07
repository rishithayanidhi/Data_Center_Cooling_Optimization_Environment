# Multi-stage build for OpenEnv Data Center Cooling Environment
# This Dockerfile is designed to run from the repo root
# Build: docker build -t datacenter-cooling:latest .

ARG BASE_IMAGE=ghcr.io/meta-pytorch/openenv-base:latest
FROM ${BASE_IMAGE} AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy entire project
COPY . /app

# Ensure uv is available
RUN if ! command -v uv >/dev/null 2>&1; then \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    mv /root/.local/bin/uvx /usr/local/bin/uvx; \
    fi

# Install dependencies from my_env
WORKDIR /app/my_env

# Create and use virtual environment
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Install requirements
RUN pip install -r /app/requirements-docker.txt

# Final runtime stage
FROM ${BASE_IMAGE}

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/venv /app/venv

# Copy project code
COPY --from=builder /app /app

# Set PATH to use virtual environment
ENV PATH="/app/venv/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"

# Environment configuration
ENV TASK_TYPE=easy
ENV WORKERS=4
ENV PORT=8000
ENV HOST=0.0.0.0

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run FastAPI server
CMD ["sh", "-c", "uvicorn my_env.server.app:app --host ${HOST} --port ${PORT} --workers ${WORKERS}"]
