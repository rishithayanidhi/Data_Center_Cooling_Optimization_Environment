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
import sys
import argparse
from typing import Optional

# Import environment and models
from my_env import DataCenterCoolingEnv, CoolingAction, CoolingObservation


async def test_baseline_agents(
    base_url: str = "http://localhost:8000",
    num_episodes: int = 5,
) -> None:
    """Test baseline agents against the running server."""
    print("\n" + "="*80)
    print("🤖 BASELINE AGENT EVALUATION")
    print("="*80 + "\n")
    
    # Import baseline agent after showing header to avoid early failures
    from my_env.server.baseline_agent import SmartBaselineAgent, BaselineAgent
    
    async with DataCenterCoolingEnv(base_url=base_url) as env:
        # Test both agent types
        agents = [
            SmartBaselineAgent(zone_count=4),
            BaselineAgent(zone_count=4, strategy="reactive"),
            BaselineAgent(zone_count=4, strategy="conservative"),
            BaselineAgent(zone_count=4, strategy="aggressive"),
        ]
        
        all_results = []
        
        for agent in agents:
            print(f"\n📊 Testing: {agent.get_name()}")
            print("-" * 80)
            
            total_reward = 0.0
            total_violations = 0
            total_energy = 0.0
            episode_results = []
            
            for episode in range(num_episodes):
                obs_result = await env.reset()
                observation = obs_result.observation
                
                episode_reward = 0.0
                episode_violations = 0
                episode_energy = 0.0
                steps = 0
                
                while True:
                    # Agent decides action
                    action = agent.select_action(observation)
                    
                    # Execute in environment
                    result = await env.step(action)
                    observation = result.observation
                    
                    # Track metrics
                    episode_reward += result.reward or 0.0
                    episode_violations += 1 if max(observation.zone_temperatures) > 50.0 else 0
                    episode_energy += observation.total_energy_consumption
                    steps += 1
                    
                    if result.done or steps >= 500:
                        break
                
                total_reward += episode_reward
                total_violations += episode_violations
                total_energy += episode_energy
                
                episode_results.append({
                    "episode": episode,
                    "reward": episode_reward,
                    "violations": episode_violations,
                    "energy": episode_energy,
                    "steps": steps,
                })
                
                print(f"  Episode {episode + 1}: Reward={episode_reward:.2f} | "
                      f"Violations={episode_violations} | Energy={episode_energy:.1f} | Steps={steps}")
            
            # Calculate and display averages
            avg_reward = total_reward / num_episodes
            avg_violations = total_violations / num_episodes
            avg_energy = total_energy / num_episodes
            
            print(f"\n  ✅ Results for {agent.get_name()}:")
            print(f"     • Average Reward: {avg_reward:.2f}")
            print(f"     • Average Violations: {avg_violations:.2f}")
            print(f"     • Average Energy: {avg_energy:.1f} units")
            
            all_results.append({
                "agent": agent.get_name(),
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
        
        # Find best agent
        best = max(all_results, key=lambda x: x['avg_reward'])
        print(f"\n🏆 Best Agent: {best['agent']} (Reward: {best['avg_reward']:.2f})")


def setup_training_template() -> None:
    """Create a template for training with TRL/GRPO."""
    print("\n" + "="*80)
    print("TRAINING SETUP GUIDE")
    print("="*80 + "\n")
    
    training_template = '''"""
Training script for Data Center Cooling Environment with TRL and GRPO.

This template shows how to train agents using the OpenEnv environment.

Installation:
    uv pip install trl transformers torch
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOTrainer, GRPOConfig
from my_env import DataCenterCoolingEnv, CoolingAction

def create_training_config():
    """Create training configuration."""
    return GRPOConfig(
        output_dir="./outputs/cooling_grpo",
        learning_rate=1e-5,
        per_device_train_batch_size=4,
        num_train_epochs=3,
        log_level="info",
    )

def prepare_environment():
    """Prepare environment for training."""
    return DataCenterCoolingEnv(base_url="http://localhost:8000")

async def train_agent():
    """Main training loop."""
    config = create_training_config()
    env = prepare_environment()
    
    print("Starting GRPO Training...")
    print(f"   Environment: Data Center Cooling")
    print(f"   Task: easy | medium | hard")
    
    # Example training loop
    for epoch in range(3):
        print(f"\\nEpoch {epoch + 1}")
        
        # Reset environment
        obs_result = await env.reset()
        
        # Training steps...
        # This is a template - implement full training loop as needed
        
        print(f"   Training in progress...")
    
    await env.aclose()
    print("\\nTraining complete!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(train_agent())
'''
    
    # Write training template with UTF-8 encoding
    print("Creating training template file: train_agent.py")
    with open("train_agent.py", "w", encoding="utf-8") as f:
        f.write(training_template)
    
    print("\nTemplate created at: train_agent.py")
    print("\nNext steps to train:")
    print("  1. Install TRL: uv pip install trl transformers torch")
    print("  2. Customize train_agent.py with your training logic")
    print("  3. Run: uv run python train_agent.py")
    
    print("\nTraining Resources:")
    print("  - TRL Docs: https://huggingface.co/docs/trl")
    print("  - GRPO Paper: https://arxiv.org/abs/2305.08957")
    print("  - OpenEnv Module 4: GRPO training patterns")
    
    print("\nKey Integration Points:")
    print("  - Use DataCenterCoolingEnv client for HTTP communication")
    print("  - CoolingAction for policy output")
    print("  - CoolingObservation for state input")
    print("  - Reward signal for training (already multi-signal)")


def main():
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
        default=5,
        help="Number of episodes for baseline test",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="Base URL for environment server",
    )
    
    args = parser.parse_args()
    
    # Default: run both if no args specified
    if not args.test_baseline and not args.setup_training:
        args.test_baseline = True
        args.setup_training = True
    
    try:
        if args.test_baseline:
            asyncio.run(test_baseline_agents(
                base_url=args.url,
                num_episodes=args.episodes,
            ))
        
        if args.setup_training:
            setup_training_template()
    
    except ConnectionError:
        print("\n❌ Error: Cannot connect to environment server")
        print(f"   URL: {args.url}")
        print("\n   Make sure server is running:")
        print("   uv run uvicorn server.app:app --reload --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()