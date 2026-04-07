---
title: Autonomous Data Center Cooling Optimization
emoji: ❄️
colorFrom: blue
colorTo: cyan
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - reinforcement-learning
  - cooling-optimization
---

# 🧊 Data Center Cooling Optimization Environment

An OpenEnv-compliant environment that simulates autonomous cooling management for modern data centers. This environment models a realistic operational task where an AI agent learns to balance thermal stability and energy efficiency under dynamic workload conditions.

## 📋 Overview

**Objective:** Maintain safe operating temperatures in a data center while minimizing energy consumption.

**Realism:** This environment simulates the exact job responsibilities of a **Data Center Infrastructure Operator / Site Reliability Engineer**, including:

- Real-time monitoring of servers and cooling systems
- Responding to thermal alerts and anomalies
- Optimizing cooling distribution for efficiency
- Preventing hardware failures due to overheating

## 🎮 Quick Start

### Local Development with Uvicorn

```bash
# Install dependencies
uv sync

# Start the server (dev mode with auto-reload)
uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Or run specific task
TASK_TYPE=hard uvicorn server.app:app --reload --port 8000
```

### In Python

```python
from my_env import DataCenterCoolingEnv, CoolingAction

# Connect to running server
with DataCenterCoolingEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
    print(f"Initial temperatures: {result.observation.zone_temperatures}")

    # Increase cooling in zone 0
    action = CoolingAction(zone_id=0, cooling_adjustment=0.5)
    result = env.step(action)

    print(f"New temperatures: {result.observation.zone_temperatures}")
    print(f"Energy consumption: {result.observation.total_energy_consumption} kW")
    print(f"Reward: {result.reward}")
```

### Docker Deployment

```bash
# Build Docker image
docker build -t datacenter-cooling:latest -f server/Dockerfile .

# Run container (easy task)
docker run -d -p 8000:8000 \
    -e TASK_TYPE=easy \
    -e WORKERS=4 \
    --name cooling-env \
    datacenter-cooling:latest

# Connect from Python
from my_env import DataCenterCoolingEnv
with DataCenterCoolingEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
```

## 🏗️ Environment Structure

```
my_env/
├── models.py                 # Type-safe contracts (Action, Observation, State)
├── client.py                 # HTTPEnvClient implementation
├── server/
│   ├── app.py               # FastAPI server with WebSocket
│   ├── environment.py       # Cooling physics simulation
│   ├── baseline_agent.py    # Rule-based baseline agent
│   └── Dockerfile           # Container definitions
├── openenv.yaml             # Environment manifest
└── pyproject.toml           # Dependencies
```

## 📊 State Space

### Observation (CoolingObservation)

| Field                      | Type        | Range                | Description               |
| -------------------------- | ----------- | -------------------- | ------------------------- |
| `zone_temperatures`        | List[float] | 10-70°C              | Current temp in each zone |
| `zone_workload_intensity`  | List[float] | [0.0, 1.0]           | CPU load per zone         |
| `zone_cooling_levels`      | List[float] | [0.0, 1.0]           | Current cooling per zone  |
| `total_energy_consumption` | float       | 0-500 kW             | Total power usage         |
| `ambient_temperature`      | float       | 20°C                 | External ambient temp     |
| `timestamp`                | int         | 0-500                | Simulation step count     |
| `task_name`                | str         | {easy, medium, hard} | Current task type         |
| `max_temperature`          | float       | 10-70°C              | Hottest zone              |
| `min_temperature`          | float       | 10-70°C              | Coolest zone              |
| `temperature_variance`     | float       | 0-100                | Zone temperature variance |

**Safe Temperature Range:** 18°C - 42°C  
**Critical Temperature:** > 50°C (causes penalties)

### Action (CoolingAction)

| Field                | Type  | Range       | Description                          |
| -------------------- | ----- | ----------- | ------------------------------------ |
| `zone_id`            | int   | 0-3         | Which zone to adjust                 |
| `cooling_adjustment` | float | [-1.0, 1.0] | -1=decrease, 0=maintain, +1=increase |
| `duration`           | int   | 1+          | Steps to apply (default: 1)          |

## 🎯 Task Difficulty Levels

### Easy Task: Constant Workload

- **Workload Pattern:** Constant 0.5 intensity across all zones
- **Objective:** Maintain temperature stability
- **Difficulty:** Learn basic feedback loop
- **Success Criteria:** Temperature stays in [18°C, 42°C]

```python
env = DataCenterCoolingEnv(base_url="http://localhost:8000?task=easy")
```

### Medium Task: Fluctuating Workload

- **Workload Pattern:** Sinusoidal oscillation (0.4-0.8 intensity)
- **Objective:** Handle dynamic load while minimizing energy
- **Difficulty:** Predict and respond to changes
- **Success Criteria:** Stability + efficiency score

```python
env = DataCenterCoolingEnv(base_url="http://localhost:8000?task=medium")
```

### Hard Task: Sudden Spikes

- **Workload Pattern:** Baseline (0.4) + sudden 0.5 spikes every 100 steps
- **Objective:** Prevent overheating under extreme conditions
- **Difficulty:** Fast response to emergencies
- **Success Criteria:** Recovery speed + prevent critical temps

```python
env = DataCenterCoolingEnv(base_url="http://localhost:8000?task=hard")
```

## 🏆 Reward Function

The environment provides continuous, multi-signal rewards:

### Positive Rewards

- **Thermal Stability:** +0.5 when mean temp in safe range
- **Variance Bonus:** +0.1 when temperature variance < 5°C
- **Energy Efficiency:** -penalty only (negative if overcooling)

### Negative Rewards

- **Overheating Penalty:** -1.0 to -2.0 based on severity
- **Excessive Cooling:** -0.1 per unit of unnecessary cooling
- **Critical Temperature:** -1.0 when temp > 50°C

### Reward Breakdown Example

```python
result = env.step(action)
print(f"Total Reward: {result.reward}")
# Breaks down into:
# - Thermal Stability: +0.5
# - Energy Efficiency: -0.08
# - Stability Bonus: +0.1
# = Total: +0.52
```

## 🤖 Baseline Agent

A simple rule-based agent for benchmarking and testing:

```python
from my_env.server.baseline_agent import SmartBaselineAgent, run_baseline_evaluation
from my_env import DataCenterCoolingEnv

# Create environment
env = DataCenterCoolingEnv(base_url="http://localhost:8000")

# Evaluate baseline
results = run_baseline_evaluation(env, num_episodes=10, agent_type="smart")

print(f"Baseline Performance:")
print(f"  Avg Reward: {results['avg_reward']:.2f}")
print(f"  Avg Thermal Violations: {results['avg_violations']}")
print(f"  Avg Energy (kWh): {results['avg_energy']:.2f}")
```

### Baseline Strategies

| Strategy       | Behavior               | Best For               |
| -------------- | ---------------------- | ---------------------- |
| `reactive`     | Simple threshold-based | Understanding task     |
| `conservative` | Preemptive cooling     | Preventing overheating |
| `smart`        | Zone-aware balancing   | General-purpose        |

## 📈 Physics Simulation

The environment models realistic thermal dynamics:

### Heat Generation

```
Heat = Workload_Intensity × 20°C
```

### Cooling Effect

```
Cooling_Effect = Cooling_Level × 5°C
```

### Temperature Dynamics

```
dT/dt = (Heat_Generated - Cooling_Effect) / 10 + Ambient_Dissipation
```

### Energy Consumption

```
Power = 50 kW (base) + Cooling_Level × 8 kW (per zone)
```

## 🚀 Deployment Options

### Local Uvicorn (Development)

```bash
uvicorn server.app:app --reload --port 8000 --workers 4
```

### Docker (Production)

```bash
docker build -t datacenter-cooling:latest -f server/Dockerfile .
docker run -d -p 8000:8000 \
    -e WORKERS=8 \
    -e MAX_CONCURRENT_ENVS=100 \
    datacenter-cooling:latest
```

### Hugging Face Spaces

```bash
# Requires HF CLI setup
openenv push --repo-id username/datacenter-cooling

# Then access at:
# https://huggingface.co/spaces/username/datacenter-cooling
```

### Load-Balanced (Multi-Container)

```bash
# With Envoy load balancer for 4+ containers
docker run -d -p 8001:8000 datacenter-cooling:latest
docker run -d -p 8002:8000 datacenter-cooling:latest
docker run -d -p 8003:8000 datacenter-cooling:latest

# Envoy load balancer distributes traffic
# Client connects to port 8080 (load balancer)
```

## 📊 API Endpoints

### Health & Info

- `GET /health` - Service health status
- `GET /info` - Environment information
- `GET /docs` - OpenAPI documentation (Swagger UI)
- `GET /web` - Interactive web interface

### Environment Control

- `POST /reset` - Start new episode
- `POST /step` - Execute action
- `GET /state` - Get episode state
- `WS /ws` - WebSocket for persistent sessions

## 🔧 Configuration

### Environment Variables

```bash
# Task selection
TASK_TYPE=easy|medium|hard  (default: easy)

# Server configuration
HOST=0.0.0.0                 (default: 0.0.0.0)
PORT=8000                    (default: 8000)
WORKERS=4                    (default: 4)

# Performance tuning
MAX_CONCURRENT_ENVS=100      (default: 100, max WebSocket sessions)
```

### Command Line

```bash
# Start with specific task
python server/app.py --task hard --port 8001

# Via Uvicorn
TASK_TYPE=medium uvicorn server.app:app --reload
```

## 📚 Training with TRL

This environment integrates with Hugging Face TRL for GRPO training:

```python
# See openenv-course Module 4 for full training example
from trl import GRPOTrainer

# Load client
from my_env import DataCenterCoolingEnv
env = DataCenterCoolingEnv(base_url="http://localhost:8000")

# Define reward function
def cooling_reward(completions, **kwargs):
    return kwargs.get("reward", [0.0] * len(completions))

# Create trainer with environment rollout
trainer = GRPOTrainer(
    model="Qwen/Qwen3-1.7B",
    reward_funcs=[cooling_reward],
    rollout_func=lambda prompts, trainer: rollout_cooling(env, trainer, prompts),
    args=grpo_config,
)

trainer.train()
```

## 🧪 Testing

```bash
# Run health check
curl http://localhost:8000/health

# Get environment info
curl http://localhost:8000/info

# Test reset
curl -X POST http://localhost:8000/reset \
    -H "Content-Type: application/json"

# Test step
curl -X POST http://localhost:8000/step \
    -H "Content-Type: application/json" \
    -d '{"zone_id": 0, "cooling_adjustment": 0.5}'
```

## 📖 Documentation

- Full OpenEnv tutorial: [GitHub](https://github.com/meta-pytorch/OpenEnv)
- Training guide: [TRL Documentation](https://huggingface.co/docs/trl)
- Scaling post: [OpenEnv Scaling](https://github.com/burtenshaw/openenv-scaling)

## 🤝 Contributing

Improvements welcome! Consider:

- More sophisticated physics models
- GPU thermal monitoring integration
- Multi-tier cooling hierarchies
- Cost-aware rewards ($/kWh)

## 📄 License

BSD 3-Clause License - See LICENSE file

# Push with a custom base image

openenv push --base-image ghcr.io/meta-pytorch/openenv-base:latest

# Push as a private space

openenv push --private

# Combine options

openenv push --repo-id my-org/my-env --base-image custom-base:latest --private

````

After deployment, your space will be available at:
`https://huggingface.co/spaces/<repo-id>`

The deployed space includes:

- **Web Interface** at `/web` - Interactive UI for exploring the environment
- **API Documentation** at `/docs` - Full OpenAPI/Swagger interface
- **Health Check** at `/health` - Container health monitoring
- **WebSocket** at `/ws` - Persistent session endpoint for low-latency interactions

## Environment Details

### Action

**MyAction**: Contains a single field

- `message` (str) - The message to echo back

### Observation

**MyObservation**: Contains the echo response and metadata

- `echoed_message` (str) - The message echoed back
- `message_length` (int) - Length of the message
- `reward` (float) - Reward based on message length (length × 0.1)
- `done` (bool) - Always False for echo environment
- `metadata` (dict) - Additional info like step count

### Reward

The reward is calculated as: `message_length × 0.1`

- "Hi" → reward: 0.2
- "Hello, World!" → reward: 1.3
- Empty message → reward: 0.0

## Advanced Usage

### Connecting to an Existing Server

If you already have a My Env environment server running, you can connect directly:

```python
from my_env import MyEnv

# Connect to existing server
my_envenv = MyEnv(base_url="<ENV_HTTP_URL_HERE>")

# Use as normal
result = my_envenv.reset()
result = my_envenv.step(MyAction(message="Hello!"))
````

Note: When connecting to an existing server, `my_envenv.close()` will NOT stop the server.

### Using the Context Manager

The client supports context manager usage for automatic connection management:

```python
from my_env import MyAction, MyEnv

# Connect with context manager (auto-connects and closes)
with MyEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
    print(f"Reset: {result.observation.echoed_message}")
    # Multiple steps with low latency
    for msg in ["Hello", "World", "!"]:
        result = env.step(MyAction(message=msg))
        print(f"Echoed: {result.observation.echoed_message}")
```

The client uses WebSocket connections for:

- **Lower latency**: No HTTP connection overhead per request
- **Persistent session**: Server maintains your environment state
- **Efficient for episodes**: Better for many sequential steps

### Concurrent WebSocket Sessions

The server supports multiple concurrent WebSocket connections. To enable this,
modify `server/app.py` to use factory mode:

```python
# In server/app.py - use factory mode for concurrent sessions
app = create_app(
    MyEnvironment,  # Pass class, not instance
    MyAction,
    MyObservation,
    max_concurrent_envs=4,  # Allow 4 concurrent sessions
)
```

Then multiple clients can connect simultaneously:

```python
from my_env import MyAction, MyEnv
from concurrent.futures import ThreadPoolExecutor

def run_episode(client_id: int):
    with MyEnv(base_url="http://localhost:8000") as env:
        result = env.reset()
        for i in range(10):
            result = env.step(MyAction(message=f"Client {client_id}, step {i}"))
        return client_id, result.observation.message_length

# Run 4 episodes concurrently
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(run_episode, range(4)))
```

## Development & Testing

### Direct Environment Testing

Test the environment logic directly without starting the HTTP server:

```bash
# From the server directory
python3 server/my_env_environment.py
```

This verifies that:

- Environment resets correctly
- Step executes actions properly
- State tracking works
- Rewards are calculated correctly

### Running Locally

Run the server locally for development:

```bash
uvicorn server.app:app --reload
```

## Project Structure

```
my_env/
├── .dockerignore         # Docker build exclusions
├── __init__.py            # Module exports
├── README.md              # This file
├── openenv.yaml           # OpenEnv manifest
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock                # Locked dependencies (generated)
├── client.py              # MyEnv client
├── models.py              # Action and Observation models
└── server/
    ├── __init__.py        # Server module exports
    ├── my_env_environment.py  # Core environment logic
    ├── app.py             # FastAPI application (HTTP + WebSocket endpoints)
    └── Dockerfile         # Container image definition
```
