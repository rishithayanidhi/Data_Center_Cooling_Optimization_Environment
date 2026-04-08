#!/usr/bin/env python3
"""
Inference script for Data Center Cooling Optimization Environment.

EXACT OUTPUT FORMAT REQUIRED BY JUDGES (Organizer Spec):
- [START] task=<task_name> env=<benchmark> model=<model_name>
- [STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
- [END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Required: OpenAI Client
from openai import OpenAI

# Environment imports
try:
    from my_env import DataCenterCoolingEnv, CoolingAction, CoolingObservation
    from websockets.asyncio.client import connect as _ws_connect
except ImportError:
    print("ERROR: my_env not installed. Run: pip install -e my_env", file=sys.stderr)
    sys.exit(1)


class _AuthEnv(DataCenterCoolingEnv):
    """DataCenterCoolingEnv that injects an Authorization header into the
    WebSocket handshake, needed when connecting to a private HF Space."""

    def __init__(self, *args, hf_token: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._hf_token = hf_token

    async def connect(self):
        if self._ws is not None:
            return self
        headers = {}
        if self._hf_token:
            headers["Authorization"] = f"Bearer {self._hf_token}"
        try:
            self._ws = await _ws_connect(
                self._ws_url,
                open_timeout=self._connect_timeout,
                max_size=self._max_message_size,
                additional_headers=headers or None,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {self._ws_url}: {e}") from e
        return self


# ============================================================================
# Configuration — all values driven by environment variables
# ============================================================================

# API_BASE_URL: LLM API endpoint (per submission spec)
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
# HF_TOKEN: mandatory — used as api_key for the LLM client
HF_TOKEN = os.getenv("HF_TOKEN")
if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")
# Optional — if you use from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
# ENV_BASE_URL: URL of the deployed environment server (our HF Space)
ENV_BASE_URL = os.getenv(
    "ENV_BASE_URL",
    "https://rishithayanidhi-datacenter-cooling-optimization.hf.space",
)
BENCHMARK = os.getenv("BENCHMARK", "datacenter-cooling")
MAX_STEPS = int(os.getenv("MAX_STEPS", "50"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "200"))
LOG_FILE = os.getenv("LOG_FILE", "inference.log")
NUM_ZONES = int(os.getenv("NUM_ZONES", "4"))
FALLBACK_ADJUSTMENT = float(os.getenv("FALLBACK_ADJUSTMENT", "0.5"))
VIOLATION_TEMP_THRESHOLD = float(os.getenv("VIOLATION_TEMP_THRESHOLD", "50.0"))


# ============================================================================
# Logging setup — file + console
# ============================================================================

def _setup_logger() -> logging.Logger:
    """Configure a logger that writes to both stdout and a rotating log file."""
    log_dir = Path(LOG_FILE).parent
    if str(log_dir) != ".":
        log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("inference")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

        # File handler
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console handler (stderr so it doesn't pollute judge stdout)
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


logger = _setup_logger()


# ============================================================================
# LLM Client
# ============================================================================

def get_llm_client() -> OpenAI:
    """Initialize OpenAI client with proper configuration."""
    try:
        logger.info("Initialising OpenAI client (base_url=%s, model=%s)", API_BASE_URL, MODEL_NAME)
        return OpenAI(
            base_url=API_BASE_URL,
            api_key=HF_TOKEN,
        )
    except Exception as exc:
        logger.error("Failed to initialise LLM client: %s", exc)
        raise


def get_action_from_llm(client: OpenAI, obs: Dict[str, Any], step: int) -> str:
    """Use LLM to generate next action."""
    try:
        max_zone_id = NUM_ZONES - 1
        temps = obs.get('zone_temperatures', [])
        cooling = obs.get('zone_cooling_levels', [])
        energy = obs.get('total_energy_consumption', 0)
        prompt = (
            f"Data center cooling control. Step {step}.\n"
            f"Zone temperatures: {temps}\n"
            f"Zone cooling levels: {cooling}\n"
            f"Total energy: {energy:.1f}\n\n"
            f"Respond with EXACTLY this format and nothing else:\n"
            f"COOL zone_id=<N> adjustment=<F>\n"
            f"Where N is 0-{max_zone_id} (zone to cool) and F is 0.1-1.0 (cooling strength).\n"
            f"Example: COOL zone_id=2 adjustment=0.8\n"
            f"Your response (one line only):"
        )
        logger.debug("Requesting LLM action at step %d", step)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": (
                    "You are a data center cooling controller. "
                    f"Respond with EXACTLY one line in this format: COOL zone_id=<N> adjustment=<F> "
                    f"where N is an integer 0-{max_zone_id} and F is a float 0.1-1.0. "
                    "No explanation, no extra text, just that one line."
                )},
                {"role": "user", "content": prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        action = response.choices[0].message.content.strip().split('\n')[0]
        logger.debug("LLM action step=%d: %s", step, action)
        return action
    except Exception as exc:
        # Fallback: greedy zone selection
        logger.warning("LLM call failed at step %d (%s); using greedy fallback", step, exc)
        temps = obs.get('zone_temperatures', [0] * NUM_ZONES)
        hottest_zone = temps.index(max(temps)) if temps else 0
        return f"COOL zone_id={hottest_zone} adjustment={FALLBACK_ADJUSTMENT}"


def parse_action(action_str: str) -> CoolingAction:
    """Parse LLM action to CoolingAction."""
    try:
        # Format: COOL zone_id=X adjustment=Y
        parts = action_str.split()
        zone_id: int = 0
        adjustment: float = FALLBACK_ADJUSTMENT

        for part in parts:
            if part.startswith("zone_id="):
                raw_zone = int(part.split("=")[1])
                zone_id = max(0, min(NUM_ZONES - 1, raw_zone))
            elif part.startswith("adjustment="):
                raw_adj = float(part.split("=")[1])
                adjustment = max(-1.0, min(1.0, raw_adj))

        logger.debug("Parsed action: zone_id=%d adjustment=%.3f", zone_id, adjustment)
        return CoolingAction(zone_id=zone_id, cooling_adjustment=adjustment)
    except Exception as exc:
        logger.warning("Failed to parse action '%s': %s — using default", action_str, exc)
        return CoolingAction(zone_id=0, cooling_adjustment=FALLBACK_ADJUSTMENT)


# ============================================================================
# Episode Runner
# ============================================================================

async def run_episode(task: str, difficulty: str, client: OpenAI) -> Dict[str, Any]:
    """Run single episode with exact output format."""
    logger.info("=== Episode start: task=%s difficulty=%s model=%s ===", task, difficulty, MODEL_NAME)

    # [START] line — required by judge spec
    print(f"[START] task={task} env={BENCHMARK} model={MODEL_NAME}", flush=True)
    logger.info("[START] task=%s env=%s model=%s", task, BENCHMARK, MODEL_NAME)

    rewards: List[float] = []
    steps_taken = 0
    success = False
    final_error: Optional[str] = None
    action_str = "COOL zone_id=0 adjustment=0.0"  # safe default for error paths

    try:
        async with _AuthEnv(base_url=ENV_BASE_URL, hf_token=HF_TOKEN) as env:
            logger.info("Connected to environment at %s", ENV_BASE_URL)

            # Reset
            try:
                result = await env.reset()
                obs = result.observation
                logger.info("Environment reset OK — initial temps: %s",
                            getattr(obs, "zone_temperatures", []))
            except Exception as exc:
                logger.error("Environment reset failed: %s", exc)
                raise

            # Episode loop
            for step in range(1, MAX_STEPS + 1):
                try:
                    obs_dict: Dict[str, Any] = {
                        "zone_temperatures": getattr(obs, "zone_temperatures", []),
                        "zone_cooling_levels": getattr(obs, "zone_cooling_levels", []),
                        "zone_workload_intensity": getattr(obs, "zone_workload_intensity", []),
                        "total_energy_consumption": getattr(obs, "total_energy_consumption", 0.0),
                    }

                    action_str = get_action_from_llm(client, obs_dict, step)
                    action = parse_action(action_str)

                    step_result = await env.step(action)
                    reward = float(step_result.reward) if step_result.reward is not None else 0.0
                    done = bool(step_result.done) if step_result.done else False

                    rewards.append(reward)
                    steps_taken = step

                    done_str = "true" if done else "false"
                    safe_action = action_str.replace("\n", " ").replace("\r", " ")
                    step_line = (
                        f"[STEP] step={step} action={safe_action} "
                        f"reward={reward:.2f} done={done_str} error=null"
                    )
                    print(step_line, flush=True)
                    logger.info(step_line)

                    if done:
                        success = True
                        logger.info("Episode completed successfully at step %d", step)
                        break

                    obs = step_result.observation

                except Exception as exc:
                    final_error = str(exc)
                    logger.error("Step %d error: %s", step, exc)
                    safe_action = action_str.replace("\n", " ").replace("\r", " ")
                    error_str = f'"{final_error}"'
                    step_line = (
                        f"[STEP] step={step} action={safe_action} "
                        f"reward=0.00 done=true error={error_str}"
                    )
                    print(step_line, flush=True)
                    logger.warning(step_line)
                    steps_taken = step
                    break

            await env.close()
            logger.info("Environment connection closed")

    except Exception as exc:
        final_error = str(exc)
        success = False
        logger.error("Episode outer error: %s", exc, exc_info=True)

    # Compute normalised score
    max_possible_reward = float(MAX_STEPS)
    total_reward = sum(rewards)
    score = min(max(total_reward / max_possible_reward if max_possible_reward > 0 else 0.0, 0.0), 1.0)

    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    success_str = "true" if success else "false"
    end_line = f"[END] success={success_str} steps={steps_taken} score={score:.2f} rewards={rewards_str}"
    print(end_line, flush=True)
    logger.info(end_line)

    if final_error:
        logger.warning("Episode ended with error: %s", final_error)

    summary = {
        "task": task,
        "difficulty": difficulty,
        "success": success,
        "steps": steps_taken,
        "total_reward": total_reward,
        "avg_reward": total_reward / len(rewards) if rewards else 0.0,
        "score": score,
        "rewards": rewards,
    }
    logger.info("Episode summary: %s", summary)
    return summary


# ============================================================================
# Main
# ============================================================================

async def main() -> List[Dict[str, Any]]:
    """Run evaluation on all configured tasks."""
    # Tasks can be overridden via TASKS env var as comma-separated pairs:
    # e.g. TASKS="task_easy:easy,task_medium:medium,task_hard:hard"
    raw_tasks = os.getenv(
        "TASKS",
        "task_easy:easy,task_medium:medium,task_hard:hard",
    )

    tasks: List[tuple] = []
    try:
        for pair in raw_tasks.split(","):
            name, diff = pair.strip().split(":")
            tasks.append((name.strip(), diff.strip()))
    except ValueError as exc:
        logger.error("Invalid TASKS format '%s': %s — using defaults", raw_tasks, exc)
        tasks = [("task_easy", "easy"), ("task_medium", "medium"), ("task_hard", "hard")]

    logger.info("Starting evaluation: %d tasks, max_steps=%d, model=%s, log=%s",
                len(tasks), MAX_STEPS, MODEL_NAME, LOG_FILE)

    try:
        client = get_llm_client()
    except Exception as exc:
        logger.critical("Cannot create LLM client: %s", exc)
        for task_name, _ in tasks:
            print(f"[START] task={task_name} env={BENCHMARK} model={MODEL_NAME}", flush=True)
            print(f"[END] success=false steps=0 score=0.00 rewards=", flush=True)
        return []

    results: List[Dict[str, Any]] = []

    for task_name, difficulty in tasks:
        try:
            result = await run_episode(task_name, difficulty, client)
            results.append(result)
        except Exception as exc:
            logger.error("Task %s raised unhandled exception: %s", task_name, exc, exc_info=True)
            print(f"[START] task={task_name} env={BENCHMARK} model={MODEL_NAME}", flush=True)
            print(f"[END] success=false steps=0 score=0.00 rewards=", flush=True)
            print(f"ERROR: Task {task_name} failed: {exc}", file=sys.stderr)

    return results


if __name__ == "__main__":
    exit_code = 0
    try:
        logger.info("inference.py started — pid=%d", os.getpid())
        results = asyncio.run(main())

        total_success = sum(1 for r in results if r.get("success"))
        summary_line = f"Tasks run: {len(results)} | Success: {total_success}/{len(results)}"
        logger.info("=== %s ===", summary_line)
        print(f"\n--- Summary ---", file=sys.stderr)
        print(summary_line, file=sys.stderr)

        for r in results:
            logger.info(
                "  task=%-14s score=%.4f total_reward=%.2f steps=%d",
                r.get("task"), r.get("score", 0), r.get("total_reward", 0), r.get("steps", 0),
            )

        exit_code = 0

    except Exception as exc:
        logger.critical("FATAL: %s", exc, exc_info=True)
        print(f"FATAL: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        exit_code = 1

    finally:
        logger.info("inference.py exiting with code %d", exit_code)
        sys.exit(exit_code)
