"""
Training script for Data Center Cooling Environment with TRL and GRPO.

This template shows how to train agents using the OpenEnv environment.

Installation:
    uv pip install trl transformers torch
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOTrainer, GRPOConfig
from my_env import DataCenterCoolingEnv, CoolingAction


# ============================================================================
# Configuration — all values driven by environment variables
# ============================================================================

TRAINING_OUTPUT_DIR = os.getenv("TRAINING_OUTPUT_DIR", "./outputs/cooling_grpo")
SERVER_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_LEARNING_RATE = float(os.getenv("LEARNING_RATE", "1e-5"))
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "4"))
DEFAULT_NUM_WORKERS = int(os.getenv("NUM_WORKERS", "4"))
DEFAULT_EPOCHS = int(os.getenv("TRAIN_EPOCHS", "3"))
LOG_FILE = os.getenv("TRAIN_LOG_FILE", "train_agent.log")


# ============================================================================
# Logging setup — file + console
# ============================================================================

def _setup_logger() -> logging.Logger:
    """Configure a logger that writes to both stdout and a log file."""
    log_dir = Path(LOG_FILE).parent
    if str(log_dir) != ".":
        log_dir.mkdir(parents=True, exist_ok=True)

    _logger = logging.getLogger("train_agent")
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


# ============================================================================
# Training helpers
# ============================================================================

def create_training_config(
    learning_rate: float = DEFAULT_LEARNING_RATE,
    batch_size: int = DEFAULT_BATCH_SIZE,
    num_workers: int = DEFAULT_NUM_WORKERS,
    epochs: int = DEFAULT_EPOCHS,
) -> GRPOConfig:
    """Create training configuration from arguments or env vars."""
    log.info(
        "Creating GRPOConfig — output_dir=%s lr=%s batch=%d workers=%d epochs=%d",
        TRAINING_OUTPUT_DIR, learning_rate, batch_size, num_workers, epochs,
    )
    try:
        config = GRPOConfig(
            output_dir=TRAINING_OUTPUT_DIR,
            learning_rate=learning_rate,
            per_device_train_batch_size=batch_size,
            num_train_epochs=epochs,
            log_level="info",
            use_cpu=not torch.cuda.is_available(),
        )
        log.info("GRPOConfig created OK")
        return config
    except Exception as exc:
        log.error("Failed to create GRPOConfig: %s", exc)
        raise


def prepare_environment() -> DataCenterCoolingEnv:
    """Prepare environment client for training."""
    log.info("Connecting to environment server at %s", SERVER_URL)
    try:
        env = DataCenterCoolingEnv(base_url=SERVER_URL)
        log.info("Environment client created OK")
        return env
    except Exception as exc:
        log.error("Failed to create environment client: %s", exc)
        raise


async def train_agent(
    learning_rate: float = DEFAULT_LEARNING_RATE,
    batch_size: int = DEFAULT_BATCH_SIZE,
    num_workers: int = DEFAULT_NUM_WORKERS,
    epochs: int = DEFAULT_EPOCHS,
) -> None:
    """Main training loop."""
    log.info("=== Training START ===")

    try:
        config = create_training_config(learning_rate, batch_size, num_workers, epochs)
    except Exception:
        log.critical("Cannot create training config — aborting")
        return

    try:
        env = prepare_environment()
    except Exception:
        log.critical("Cannot prepare environment — aborting")
        return

    print("Starting GRPO Training...")
    print(f"   Environment: Data Center Cooling  (server={SERVER_URL})")
    print(f"   Output dir:  {TRAINING_OUTPUT_DIR}")
    print(f"   LR={learning_rate}  batch={batch_size}  workers={num_workers}  epochs={epochs}")

    try:
        for epoch in range(epochs):
            log.info("--- Epoch %d/%d ---", epoch + 1, epochs)
            print(f"\nEpoch {epoch + 1}/{epochs}")

            try:
                obs_result = await env.reset()
                log.info(
                    "Epoch %d reset OK — initial temps: %s",
                    epoch + 1,
                    getattr(obs_result.observation, "zone_temperatures", []),
                )
            except Exception as exc:
                log.error("Environment reset failed at epoch %d: %s", epoch + 1, exc)
                raise

            # Training steps — implement full loop as needed
            log.info("Epoch %d training in progress...", epoch + 1)
            print(f"   Training in progress...")

        log.info("All epochs complete")
    except Exception as exc:
        log.error("Training loop error: %s", exc, exc_info=True)
        raise
    finally:
        try:
            await env.close()
            log.info("Environment connection closed")
        except Exception as close_exc:
            log.warning("Error closing environment: %s", close_exc)

    print("\nTraining complete!")
    log.info("=== Training END ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train GRPO agent for cooling optimization")
    parser.add_argument("--learning_rate", type=float, default=DEFAULT_LEARNING_RATE,
                        help="Learning rate for training")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="Batch size for training")
    parser.add_argument("--num_workers", type=int, default=DEFAULT_NUM_WORKERS,
                        help="Number of worker processes")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS,
                        help="Number of training epochs")

    args = parser.parse_args()
    log.info(
        "train_agent.py invoked — lr=%s batch=%d workers=%d epochs=%d",
        args.learning_rate, args.batch_size, args.num_workers, args.epochs,
    )

    try:
        asyncio.run(train_agent(
            learning_rate=args.learning_rate,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            epochs=args.epochs,
        ))
    except KeyboardInterrupt:
        log.warning("Training interrupted by user")
        sys.exit(130)
    except Exception as exc:
        log.critical("Unhandled training error: %s", exc, exc_info=True)
        sys.exit(1)
