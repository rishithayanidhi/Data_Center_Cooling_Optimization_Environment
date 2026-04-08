---
title: Data Center Cooling Optimization
emoji: 🌡️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: false
---

# Data Center Cooling Optimization Environment

Autonomous AI environment for optimizing data center cooling using reinforcement learning.

## Features

- 🌡️ Multi-zone temperature management
- ⚡ Energy efficiency optimization
- 🤖 RL-based autonomous control
- 📊 Real-time metrics and monitoring

## API Endpoints

- `POST /reset` - Reset environment
- `POST /step` - Execute action
- `GET /state` - Get current state
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation

## Environment Variables

- `API_BASE_URL`: API endpoint (default: http://localhost:8000)
- `TASK_TYPE`: Task difficulty - easy/medium/hard (default: easy)
- `MODEL_NAME`: Model identifier (default: gpt-4-turbo)
- `HF_TOKEN`: Hugging Face API token
- `OPENAI_API_KEY`: OpenAI API key

## Quick Start

The environment is deployed on Hugging Face Spaces and exposes a FastAPI server on port 8000.
