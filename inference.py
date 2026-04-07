#!/usr/bin/env python3
"""
Inference script for Data Center Cooling Optimization Environment.

EXACT OUTPUT FORMAT REQUIRED BY JUDGES (Organizer Spec):
- [START] task=<task_name> env=<benchmark> model=<model_name>
- [STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
- [END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

Score: Normalized to [0, 1] based on total reward achieved.
"""

import asyncio
import os
import sys
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Required: OpenAI Client
try:
    from openai import OpenAI, AzureOpenAI
except ImportError:
    print("ERROR: OpenAI client not installed. Run: pip install openai", file=sys.stderr)
    sys.exit(1)

# Environment imports
try:
    from my_env import DataCenterCoolingEnv, CoolingAction, CoolingObservation
except ImportError:
    print("ERROR: my_env not installed. Run: pip install -e my_env", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Configuration
# ============================================================================

# Required environment variables
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4-turbo")
HF_TOKEN = os.getenv("HF_TOKEN", "")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME", "")

# Defaults
BENCHMARK = "datacenter-cooling"
MAX_STEPS = 50
TEMPERATURE = 0.7
MAX_TOKENS = 200


# ============================================================================
# LLM Client
# ============================================================================

def get_llm_client() -> OpenAI:
    """Initialize OpenAI client with proper configuration."""
    if os.getenv("AZURE_API_KEY"):
        return AzureOpenAI(
            api_key=os.getenv("AZURE_API_KEY"),
            api_version="2024-02-15-preview",
            azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        )
    else:
        return OpenAI(
            api_key=HF_TOKEN or os.getenv("OPENAI_API_KEY", "sk-mock"),
            base_url=API_BASE_URL if "http" in API_BASE_URL else None,
        )


def get_action_from_llm(client: OpenAI, obs: Dict[str, Any], step: int) -> str:
    """Use LLM to generate next action."""
    try:
        prompt = f"""You control a data center cooling system.
Current state (step {step}):
- Zone temps: {obs.get('zone_temperatures', [])}
- Cooling: {obs.get('zone_cooling_levels', [])}
- Energy: {obs.get('total_energy_consumption', 0):.1f}

Output action: COOL zone_id=<0-3> adjustment=<0.0-1.0>"""
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        return response.choices[0].message.content.strip().split('\n')[0]
    except Exception as e:
        # Fallback: greedy zone selection
        temps = obs.get('zone_temperatures', [0]*4)
        hottest_zone = temps.index(max(temps))
        return f"COOL zone_id={hottest_zone} adjustment=0.5"


def parse_action(action_str: str) -> CoolingAction:
    """Parse LLM action to CoolingAction."""
    try:
        # Format: COOL zone_id=X adjustment=Y
        parts = action_str.split()
        zone_id, adjustment = 0, 0.1
        
        for part in parts:
            if part.startswith("zone_id="):
                zone_id = int(part.split("=")[1])
            elif part.startswith("adjustment="):
                adjustment = float(part.split("=")[1])
        
        return CoolingAction(zone_id=zone_id, cooling_adjustment=adjustment)
    except:
        return CoolingAction(zone_id=0, cooling_adjustment=0.1)


# ============================================================================
# Episode Runner
# ============================================================================

async def run_episode(task: str, difficulty: str) -> Dict[str, Any]:
    """Run single episode with exact output format."""
    client = get_llm_client()
    
    # [START] line
    print(f"[START] task={task} env={BENCHMARK} model={MODEL_NAME}", flush=True)
    
    rewards = []
    steps_taken = 0
    success = False
    final_error = None
    
    try:
        async with DataCenterCoolingEnv(base_url=API_BASE_URL) as env:
            # Reset
            result = await env.reset()
            obs = result.observation
            
            # Episode loop
            for step in range(1, MAX_STEPS + 1):
                try:
                    # Format observation dict
                    obs_dict = {
                        'zone_temperatures': obs.zone_temperatures if hasattr(obs, 'zone_temperatures') else [],
                        'zone_cooling_levels': obs.zone_cooling_levels if hasattr(obs, 'zone_cooling_levels') else [],
                        'zone_workload_intensity': obs.zone_workload_intensity if hasattr(obs, 'zone_workload_intensity') else [],
                        'total_energy_consumption': obs.total_energy_consumption if hasattr(obs, 'total_energy_consumption') else 0.0,
                    }
                    
                    # Get LLM action
                    action_str = get_action_from_llm(client, obs_dict, step)
                    action = parse_action(action_str)
                    
                    # Step environment
                    step_result = await env.step(action)
                    reward = float(step_result.reward) if step_result.reward is not None else 0.0
                    done = bool(step_result.done) if step_result.done else False
                    
                    rewards.append(reward)
                    steps_taken = step
                    
                    # [STEP] line - EXACT FORMAT
                    done_str = "true" if done else "false"
                    error_str = "null"
                    print(f"[STEP] step={step} action={action_str} reward={reward:.2f} done={done_str} error={error_str}", flush=True)
                    
                    if done:
                        success = True
                        break
                    
                    obs = step_result.observation
                    
                except Exception as e:
                    final_error = str(e)
                    done_str = "true"
                    error_str = f'"{str(e)}"'
                    print(f"[STEP] step={step} action=ERROR reward=0.00 done={done_str} error={error_str}", flush=True)
                    steps_taken = step
                    break
            
            await env.close()
    
    except Exception as e:
        final_error = str(e)
        success = False
    
    # [END] line - EXACT FORMAT (with score)
    # Calculate normalized score: sum(rewards) / max_possible_reward
    # Rewards are in [0.0, 1.0], max per step is 1.0, so max total is MAX_STEPS * 1.0
    max_possible_reward = MAX_STEPS * 1.0
    total_reward = sum(rewards)
    score = total_reward / max_possible_reward if max_possible_reward > 0 else 0.0
    score = min(max(score, 0.0), 1.0)  # Clamp to [0, 1]
    
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    success_str = "true" if success else "false"
    print(f"[END] success={success_str} steps={steps_taken} score={score:.2f} rewards={rewards_str}", flush=True)
    
    return {
        "task": task,
        "difficulty": difficulty,
        "success": success,
        "steps": steps_taken,
        "total_reward": total_reward,
        "avg_reward": sum(rewards) / len(rewards) if rewards else 0.0,
        "score": score,
        "rewards": rewards,
    }


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run evaluation on 3+ tasks."""
    
    tasks = [
        ("task_easy", "easy"),
        ("task_medium", "medium"),
        ("task_hard", "hard"),
    ]
    
    results = []
    
    for task_name, difficulty in tasks:
        try:
            result = await run_episode(task_name, difficulty)
            results.append(result)
        except Exception as e:
            # Always emit [START] and [END] even on error
            print(f"[START] task={task_name} env={BENCHMARK} model={MODEL_NAME}", flush=True)
            print(f"[END] success=false steps=0 score=0.00 rewards=", flush=True)
            print(f"ERROR: Task {task_name} failed: {e}", file=sys.stderr)
    
    return results


if __name__ == "__main__":
    exit_code = 0
    try:
        results = asyncio.run(main())
        
        # Summary (to stderr, doesn't affect stdout format)
        total_success = sum(1 for r in results if r.get("success"))
        print(f"\n--- Summary ---", file=sys.stderr)
        print(f"Tasks run: {len(results)}", file=sys.stderr)
        print(f"Success: {total_success}/{len(results)}", file=sys.stderr)
        
        # Exit 0 on successful completion
        # Judges evaluate stdout format, not exit code
        exit_code = 0
        
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        exit_code = 1
    
    finally:
        # Ensure clean exit without lingering processes
        sys.exit(exit_code)
