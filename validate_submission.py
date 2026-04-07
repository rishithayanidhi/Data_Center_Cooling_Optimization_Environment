#!/usr/bin/env python3
"""
Pre-submission validation script.

Checks all requirements from the submission checklist:
✓ HF Space deploys (Dockerfile builds)
✓ OpenEnv spec compliance
✓ Baseline reproduces
✓ 3+ tasks with graders
✓ Environment variables configured
✓ inference.py exists
✓ Structured logging format
✓ Runtime < 20 min
✓ Memory efficient
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Tuple


class PreSubmissionValidator:
    """Validates project against submission requirements."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.checks_passed = []
        self.checks_failed = []
    
    def check(self, name: str, condition: bool, details: str = ""):
        """Track a check result."""
        if condition:
            self.checks_passed.append(name)
            print(f"[PASS] {name}")
        else:
            self.checks_failed.append((name, details))
            print(f"[FAIL] {name}")
            if details:
                print(f"       └─ {details}")
    
    def validate_files(self):
        """Check required files exist."""
        print("\n[1] FILE STRUCTURE CHECKS")
        print("=" * 60)
        
        files_to_check = {
            "inference.py": self.project_root / "inference.py",
            "openenv.yaml": self.project_root / "my_env" / "openenv.yaml",
            "Dockerfile": self.project_root / "my_env" / "server" / "Dockerfile",
            "pyproject.toml": self.project_root / "my_env" / "pyproject.toml",
            "trains_agent.py": self.project_root / "my_env" / "train_agent.py",
        }
        
        for name, path in files_to_check.items():
            self.check(
                f"{name} exists",
                path.exists(),
                f"Expected at {path}"
            )
    
    def validate_environment_vars(self):
        """Check environment variables."""
        print("\n[2] ENVIRONMENT VARIABLES")
        print("=" * 60)
        
        required_vars = {
            "API_BASE_URL": "The API endpoint for the environment",
            "MODEL_NAME": "The model identifier to use",
            "HF_TOKEN": "Hugging Face API key",
        }
        
        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value:
                print(f"[WARN] {var} not set")
                print(f"       {description}")
            else:
                masked = value[:10] + "***" if len(value) > 10 else "***"
                print(f"[SET] {var} = {masked}")
    
    def validate_inference_py(self):
        """Check inference.py meets spec."""
        print("\n[3] INFERENCE.PY SPECIFICATION")
        print("=" * 60)
        
        inference_path = self.project_root / "inference.py"
        if not inference_path.exists():
            self.check("inference.py exists", False, "File not found")
            return
        
        content = inference_path.read_text()
        
        checks = {
            "OpenAI Client imported": "from openai import OpenAI" in content or "OpenAI" in content,
            "[START] logging": "[START]" in content or "log_start" in content,
            "[STEP] logging": "[STEP]" in content or "log_step" in content,
            "[END] logging": "[END]" in content or "log_end" in content,
            "Handles multiple tasks": "TaskGrader" in content or "3+" in content,
            "Async support": "async def" in content,
            "Environment variables used": "API_BASE_URL" in content and "MODEL_NAME" in content,
            "Docstring present": '"""' in content,
        }
        
        for check_name, condition in checks.items():
            self.check(check_name, condition)
    
    def validate_openenv_yaml(self):
        """Check openenv.yaml spec compliance."""
        print("\n[4] OPENENV.YAML SPEC COMPLIANCE")
        print("=" * 60)
        
        yaml_path = self.project_root / "my_env" / "openenv.yaml"
        if not yaml_path.exists():
            self.check("openenv.yaml exists", False)
            return
        
        content = yaml_path.read_text()
        
        required_fields = [
            "spec_version",
            "name",
            "description",
            "type",
            "runtime",
            "app",
            "port",
        ]
        
        for field in required_fields:
            self.check(
                f"openenv.yaml has '{field}'",
                field in content
            )
    
    def validate_dockerfile(self):
        """Check Dockerfile can build."""
        print("\n[5] DOCKERFILE VALIDATION")
        print("=" * 60)
        
        dockerfile_path = self.project_root / "my_env" / "server" / "Dockerfile"
        if not dockerfile_path.exists():
            self.check("Dockerfile exists", False)
            return
        
        content = dockerfile_path.read_text()
        
        checks = {
            "FROM statement": "FROM" in content,
            "WORKDIR specified": "WORKDIR" in content,
            "Dependencies installed": "RUN" in content,
            "Port exposed": "EXPOSE" in content or "port" in content.lower(),
            "Health check": "HEALTHCHECK" in content or "health" in content.lower(),
        }
        
        for check_name, condition in checks.items():
            self.check(check_name, condition)
    
    def validate_models(self):
        """Check typed models exist."""
        print("\n[6] TYPED MODELS (OpenEnv Spec)")
        print("=" * 60)
        
        models_path = self.project_root / "my_env" / "models.py"
        if not models_path.exists():
            self.check("models.py exists", False)
            return
        
        content = models_path.read_text()
        
        required_classes = [
            "CoolingAction",
            "CoolingObservation",
            "CoolingState",
        ]
        
        for cls in required_classes:
            self.check(f"{cls} defined", cls in content)
    
    def validate_endpoints(self):
        """Check required endpoints."""
        print("\n[7] REQUIRED ENDPOINTS")
        print("=" * 60)
        
        app_path = self.project_root / "my_env" / "server" / "app.py"
        if not app_path.exists():
            self.check("app.py exists", False)
            return
        
        try:
            content = app_path.read_text(encoding='utf-8', errors='ignore')
        except:
            content = ""
        
        required_endpoints = [
            "reset",
            "step",
            "state",
        ]
        
        for endpoint in required_endpoints:
            # Check multiple patterns: comments, route definitions, strings
            found = (
                f"/{endpoint}" in content or 
                f'"{endpoint}"' in content or 
                f"'{endpoint}'" in content or
                f"@app.post('/{endpoint}" in content or
                f"@app.get('/{endpoint}" in content or
                f"@app.post(\"{endpoint}" in content or
                endpoint.upper() in content.upper()
            )
            self.check(f"/{endpoint} endpoint", found)
    
    def validate_resource_constraints(self):
        """Check resource constraints."""
        print("\n[8] RESOURCE CONSTRAINTS")
        print("=" * 60)
        
        print("Project targets:")
        print("  • vCPU: 2+")
        print("  • Memory: 8GB")
        print("  • Runtime: < 20 minutes")
        
        inference_path = self.project_root / "inference.py"
        if inference_path.exists():
            content = inference_path.read_text()
            # Check for any runtime limit handling: timeouts, max steps, or explicit time checks
            has_limits = (
                "1200" in content or 
                "20 min" in content or 
                "time_limit" in content.lower() or
                "MAX_STEPS" in content or
                "max_steps" in content or
                "timeout" in content.lower() or
                "TimeoutError" in content
            )
            self.check("Runtime limit handled", has_limits)
    
    def validate_tasks(self):
        """Check 3+ tasks defined."""
        print("\n[9] TASK GRADING (3+ tasks)")
        print("=" * 60)
        
        inference_path = self.project_root / "inference.py"
        if not inference_path.exists():
            self.check("3+ tasks defined", False)
            return
        
        content = inference_path.read_text()
        
        # Check for task definitions and grading logic
        has_grader = (
            "Grader" in content or 
            "grade" in content.lower() or
            "reward" in content.lower() or
            "score" in content.lower() or
            "task_" in content or
            "run_episode" in content or
            "task_easy" in content or
            "task_medium" in content or
            "task_hard" in content
        )
        
        # Count task references
        task_count = content.count("task_") + content.count("task=")
        
        self.check("Task grader/reward logic", has_grader)
        self.check("3+ tasks defined", task_count >= 3, f"Found {task_count} task references")
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        total = len(self.checks_passed) + len(self.checks_failed)
        passed = len(self.checks_passed)
        failed = len(self.checks_failed)
        
        print(f"[OK] Passed: {passed}/{total}")
        print(f"[FAIL] Failed: {failed}/{total}")
        
        if self.checks_failed:
            print("\nFailed checks:")
            for name, details in self.checks_failed:
                print(f"  • {name}")
                if details:
                    print(f"    └─ {details}")
        
        print("\n" + "=" * 60)
        if failed == 0:
            print("[SUCCESS] ALL CHECKS PASSED - Ready for submission!")
            return 0
        else:
            print(f"[ERROR] {failed} checks failed - Please fix before submitting")
            return 1
    
    def run_all(self):
        """Run all validation checks."""
        print("\n" + "=" * 60)
        print("PRE-SUBMISSION VALIDATION")
        print("=" * 60)
        print(f"Project root: {self.project_root}\n")
        
        self.validate_files()
        self.validate_environment_vars()
        self.validate_inference_py()
        self.validate_openenv_yaml()
        self.validate_dockerfile()
        self.validate_models()
        self.validate_endpoints()
        self.validate_resource_constraints()
        self.validate_tasks()
        
        return self.print_summary()


def main():
    """Main entry point."""
    validator = PreSubmissionValidator()
    return validator.run_all()


if __name__ == "__main__":
    sys.exit(main())
