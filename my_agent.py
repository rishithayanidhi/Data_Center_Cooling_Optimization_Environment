#!/usr/bin/env python3
"""
Test baseline agents and setup for training.

Usage:
    # Test baseline agents (5 episodes)
    uv run python my_agent.py --test-baseline
    
    # Test with 10 episodes
    uv run python my_agent.py --test-baseline --episodes 10
    
    # Setup training template
    uv run python my_agent.py --setup-training
    
    # Run both (default)
    uv run python my_agent.py
"""

import asyncio
import logging
import os
import sys
import argparse
from pathlib import Path
from typing import Optional

# Import environment and models
from my_env import DataCenterCoolingEnv, CoolingAction, CoolingObservation


# ============================================================================
# Configuration — all values driven by environment variables
# ============================================================================

ZONE_COUNT = int(os.getenv("ZONE_COUNT", "4"))
MAX_EPISODE_STEPS = int(os.getenv("MAX_EPISODE_STEPS", "500"))
VIOLATION_TEMP = float(os.getenv("VIOLATION_TEMP", "50.0"))
DEFAULT_SERVER_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_EPISODES = int(os.getenv("DEFAULT_EPISODES", "5"))
LOG_FILE = os.getenv("AGENT_LOG_FILE", "my_agent.log")


# ============================================================================
# Logging setup — file + console
# ============================================================================

def _setup_logger() -> logging.Logger:
    """Configure a logger that writes to both stdout and a log file."""
    log_dir = Path(LOG_FILE).parent
    if str(log_dir) != ".":
        log_dir.mkdir(parents=True, exist_ok=True)

    _logger = logging.getLogger("my_agent")
    _logger.setLevel(logging.DEBUG)

    if not _logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        _logger.addHandler(fh)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        _logger.addHandler(ch)

    return _logger


log = _setup_logger()


async def test_baseline_agents(
    base_url: str = DEFAULT_SERVER_URL,
    num_episodes: int = DEFAULT_EPISODES,
) -> None:
    """Test baseline agents against the running server."""
    log.info("=== Baseline Agent Evaluation START ===")
    log.info("server=%s  episodes=%d  zone_count=%d", base_url, num_episodes, ZONE_COUNT)

    print("\n" + "="*80)
    print("🤖 BASELINE AGENT EVALUATION")
    print("="*80 + "\n")
    
    # Import baseline agent after showing header to avoid early failures
    try:
        from my_env.server.baseline_agent import SmartBaselineAgent, BaselineAgent
    except ImportError as exc:
        log.error("Could not import baseline agents: %s", exc)
        raise
    
    try:
        async with DataCenterCoolingEnv(base_url=base_url) as env:
            agents = [
                SmartBaselineAgent(zone_count=ZONE_COUNT),
                BaselineAgent(zone_count=ZONE_COUNT, strategy="reactive"),
                BaselineAgent(zone_count=ZONE_COUNT, strategy="conservative"),
                BaselineAgent(zone_count=ZONE_COUNT, strategy="aggressive"),
            ]
            
            all_results = []
            
            for agent in agents:
                agent_name = agent.get_name()
                log.info("--- Testing agent: %s ---", agent_name)
                print(f"\n📊 Testing: {agent_name}")
                print("-" * 80)
                
                total_reward = 0.0
                total_violations = 0
                total_energy = 0.0
                episode_results = []
                
                for episode in range(num_episodes):
                    try:
                        obs_result = await env.reset()
                        observation = obs_result.observation
                        
                        episode_reward = 0.0
                        episode_violations = 0
                        episode_energy = 0.0
                        steps = 0
                        
                        log.debug("Episode %d/%d start — agent=%s", episode + 1, num_episodes, agent_name)

                        while True:
                            try:
                                action = agent.select_action(observation)
                                result = await env.step(action)
                                observation = result.observation

                                episode_reward += result.reward or 0.0
                                if max(observation.zone_temperatures) > VIOLATION_TEMP:
                                    episode_violations += 1
                                    log.warning(
                                        "Thermal violation — agent=%s episode=%d step=%d max_temp=%.1f",
                                        agent_name, episode + 1, steps + 1,
                                        max(observation.zone_temperatures),
                                    )
                                episode_energy += observation.total_energy_consumption
                                steps += 1

                                if result.done or steps >= MAX_EPISODE_STEPS:
                                    break

                            except Exception as step_exc:
                                log.error(
                                    "Step error — agent=%s episode=%d step=%d: %s",
                                    agent_name, episode + 1, steps + 1, step_exc,
                                )
                                break
                        
                        total_reward += episode_reward
                        total_violations += episode_violations
                        total_energy += episode_energy
                        
                        ep_summary = {
                            "episode": episode,
                            "reward": episode_reward,
                            "violations": episode_violations,
                            "energy": episode_energy,
                            "steps": steps,
                        }
                        episode_results.append(ep_summary)
                        log.info(
                            "Episode %d/%d done — reward=%.2f violations=%d energy=%.1f steps=%d",
                            episode + 1, num_episodes,
                            episode_reward, episode_violations, episode_energy, steps,
                        )
                        
                        print(f"  Episode {episode + 1}: Reward={episode_reward:.2f} | "
                              f"Violations={episode_violations} | Energy={episode_energy:.1f} | Steps={steps}")

                    except Exception as ep_exc:
                        log.error("Episode %d failed — agent=%s: %s", episode + 1, agent_name, ep_exc, exc_info=True)
                        print(f"  Episode {episode + 1}: ERROR — {ep_exc}")


            avg_reward = total_reward / num_episodes if num_episodes > 0 else 0.0
            avg_violations = total_violations / num_episodes if num_episodes > 0 else 0.0
            avg_energy = total_energy / num_episodes if num_episodes > 0 else 0.0
            
            log.info(
                "Agent %s final: avg_reward=%.2f avg_violations=%.2f avg_energy=%.1f",
                agent_name, avg_reward, avg_violations, avg_energy,
            )
            print(f"\n  ✅ Results for {agent_name}:")
            print(f"     • Average Reward: {avg_reward:.2f}")
            print(f"     • Average Violations: {avg_violations:.2f}")
            print(f"     • Average Energy: {avg_energy:.1f} units")
            
            all_results.append({
                "agent": agent_name,
                "avg_reward": avg_reward,
                "avg_violations": avg_violations,
                "avg_energy": avg_energy,
                "episodes": episode_results,
            })
        
        # Summary comparison
        print("\n" + "="*80)
        print("📈 COMPARISON SUMMARY")
        print("="*80)
        print(f"{'Agent':<30} {'Reward':<15} {'Violations':<15} {'Energy':<15}")
        print("-" * 75)
        for result in all_results:
            print(f"{result['agent']:<30} {result['avg_reward']:<15.2f} "
                  f"{result['avg_violations']:<15.2f} {result['avg_energy']:<15.1f}")
        
        if all_results:
            best = max(all_results, key=lambda x: x['avg_reward'])
            log.info("Best agent: %s (avg_reward=%.2f)", best['agent'], best['avg_reward'])
            print(f"\n🏆 Best Agent: {best['agent']} (Reward: {best['avg_reward']:.2f})")

    except Exception as exc:
        log.error("test_baseline_agents failed: %s", exc, exc_info=True)
        raise

    log.info("=== Baseline Agent Evaluation END ===")


def setup_training_template() -> None:
    """Write a training template to train_agent.py (does not overwrite my_env/train_agent.py)."""
    log.info("Setting up training template")
    print("\n" + "="*80)
    print("TRAINING SETUP GUIDE")
    print("="*80 + "\n")

    output_path = os.getenv("TRAINING_TEMPLATE_PATH", "train_agent.py")

    training_template = '''\
"""
Training script for Data Center Cooling Environment with TRL and GRPO.

This template shows how to train agents using the OpenEnv environment.

Installation:
    uv pip install trl transformers torch
"""

import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOTrainer, GRPOConfig
from my_env import DataCenterCoolingEnv, CoolingAction

def create_training_config(learning_rate=1e-5, batch_size=4, epochs=3):
    """Create training configuration."""
    return GRPOConfig(
        output_dir=os.getenv("TRAINING_OUTPUT_DIR", "./outputs/cooling_grpo"),
        learning_rate=learning_rate,
        per_device_train_batch_size=batch_size,
        num_train_epochs=epochs,
        log_level="info",
    )

def prepare_environment():
    """Prepare environment for training."""
    return DataCenterCoolingEnv(base_url=os.getenv("API_BASE_URL", "http://localhost:8000"))

async def train_agent(learning_rate=1e-5, batch_size=4, epochs=3):
    """Main training loop."""
    config = create_training_config(learning_rate, batch_size, epochs)
    env = prepare_environment()

    print("Starting GRPO Training...")
    print(f"   Environment: Data Center Cooling")
    print(f"   Task: easy | medium | hard")

    for epoch in range(epochs):
        print(f"\\nEpoch {epoch + 1}/{epochs}")
        obs_result = await env.reset()
        print(f"   Training in progress...")

    await env.aclose()
    print("\\nTraining complete!")

if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(description="Train GRPO agent for cooling optimization")
    parser.add_argument("--learning_rate", type=float,
                        default=float(os.getenv("LEARNING_RATE", "1e-5")))
    parser.add_argument("--batch_size", type=int,
                        default=int(os.getenv("BATCH_SIZE", "4")))
    parser.add_argument("--epochs", type=int,
                        default=int(os.getenv("TRAIN_EPOCHS", "3")))
    args = parser.parse_args()

    asyncio.run(train_agent(
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        epochs=args.epochs,
    ))
'''

    try:
        print(f"Creating training template file: {output_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(training_template)
        log.info("Training template written to %s", output_path)
    except OSError as exc:
        log.error("Failed to write training template to %s: %s", output_path, exc)
        raise

    print(f"\nTemplate created at: {output_path}")
    print("\nNext steps to train:")
    print("  1. Install TRL: uv pip install trl transformers torch")
    print(f"  2. Customize {output_path} with your training logic")
    print(f"  3. Run: uv run python {output_path}")
    print("\nTraining Resources:")
    print("  - TRL Docs: https://huggingface.co/docs/trl")
    print("  - GRPO Paper: https://arxiv.org/abs/2305.08957")
    print("\nKey Integration Points:")
    print("  - Use DataCenterCoolingEnv client for HTTP communication")
    print("  - CoolingAction for policy output")
    print("  - CoolingObservation for state input")
    print("  - Reward signal for training (already multi-signal)")
    print("  - Set TRAINING_OUTPUT_DIR env var to change output directory")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test baseline agents and setup training"
    )
    parser.add_argument(
        "--test-baseline",
        action="store_true",
        help="Test baseline agents against running server",
    )
    parser.add_argument(
        "--setup-training",
        action="store_true",
        help="Create training template",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=DEFAULT_EPISODES,
        help="Number of episodes for baseline test",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_SERVER_URL,
        help="Base URL for environment server",
    )

    args = parser.parse_args()

    # Default: run both if no args specified
    if not args.test_baseline and not args.setup_training:
        args.test_baseline = True
        args.setup_training = True

    log.info("my_agent.py started — test_baseline=%s setup_training=%s url=%s episodes=%d",
             args.test_baseline, args.setup_training, args.url, args.episodes)

    try:
        if args.test_baseline:
            asyncio.run(test_baseline_agents(
                base_url=args.url,
                num_episodes=args.episodes,
            ))

        if args.setup_training:
            setup_training_template()

    except ConnectionError as exc:
        log.error("Cannot connect to environment server at %s: %s", args.url, exc)
        print("\n❌ Error: Cannot connect to environment server")
        print(f"   URL: {args.url}")
        print("\n   Make sure server is running:")
        print("   uv run uvicorn server.app:app --reload --port 8000")
        sys.exit(1)
    except Exception as exc:
        log.error("Unhandled error: %s", exc, exc_info=True)
        print(f"\n❌ Error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()