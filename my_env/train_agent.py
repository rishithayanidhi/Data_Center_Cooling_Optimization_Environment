"""
Training script for Data Center Cooling Environment with TRL and GRPO.

This template shows how to train agents using the OpenEnv environment.

Installation:
    uv pip install trl transformers torch
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOTrainer, GRPOConfig
from my_env import DataCenterCoolingEnv, CoolingAction

def create_training_config(learning_rate=1e-5, batch_size=4, num_workers=4):
    """Create training configuration."""
    return GRPOConfig(
        output_dir="./outputs/cooling_grpo",
        learning_rate=learning_rate,
        per_device_train_batch_size=batch_size,
        num_train_epochs=3,
        log_level="info",
        use_cpu=True,  # Use CPU to avoid bf16/GPU issues
    )

def prepare_environment():
    """Prepare environment for training."""
    return DataCenterCoolingEnv(base_url="http://localhost:8000")

async def train_agent(learning_rate=1e-5, batch_size=4, num_workers=4):
    """Main training loop."""
    config = create_training_config(learning_rate, batch_size, num_workers)
    env = prepare_environment()
    
    print("Starting GRPO Training...")
    print(f"   Environment: Data Center Cooling")
    print(f"   Task: easy | medium | hard")
    
    # Example training loop
    for epoch in range(3):
        print(f"\nEpoch {epoch + 1}")
        
        # Reset environment
        obs_result = await env.reset()
        
        # Training steps...
        # This is a template - implement full training loop as needed
        
        print(f"   Training in progress...")
    
    await env.close()
    print("\nTraining complete!")

if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Train GRPO agent for cooling optimization")
    parser.add_argument("--learning_rate", type=float, default=1e-5, help="Learning rate for training")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size for training")
    parser.add_argument("--num_workers", type=int, default=4, help="Number of worker processes")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    
    args = parser.parse_args()
    
    asyncio.run(train_agent(
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    ))
