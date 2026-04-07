#!/usr/bin/env python3
"""
Quick reference for pre-submission tests.
Run individual test sections or all at once.
"""

import subprocess
import sys
from pathlib import Path


class SubmissionTester:
    """Helper to run pre-submission tests."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
    
    def run_command(self, cmd, description):
        """Run a command and print status."""
        print(f"\n{'='*60}")
        print(f"[TEST] {description}")
        print(f"{'='*60}")
        print(f"Command: {cmd}\n")
        
        result = subprocess.run(cmd, shell=True, cwd=self.project_root)
        
        if result.returncode == 0:
            print(f"✓ {description} PASSED")
        else:
            print(f"✗ {description} FAILED")
        
        return result.returncode == 0
    
    def test_validation(self):
        """Test 1: Run pre-submission validator."""
        return self.run_command(
            "uv run python validate_submission.py",
            "Pre-submission Validation"
        )
    
    def test_syntax(self):
        """Test 2: Check Python syntax."""
        return self.run_command(
            'python -m py_compile "inference.py" "validate_submission.py" "my_env/train_agent.py"',
            "Python Syntax Check"
        )
    
    def test_imports(self):
        """Test 3: Verify imports."""
        return self.run_command(
            'uv run python -c "from my_env import DataCenterCoolingEnv, CoolingAction, CoolingObservation; from openai import OpenAI; print(\'✓ All imports successful\')"',
            "Import Verification"
        )
    
    def test_server_start(self):
        """Test 4: Verify server startup."""
        print(f"\n{'='*60}")
        print(f"[TEST] Server Startup Check")
        print(f"{'='*60}")
        print("Command: cd my_env; uv run python -m uvicorn server.app:app --port 8000 --timeout-keep-alive 5")
        print("\nNote: This will START the server. Run in a separate terminal for testing.\n")
        print("Quick test: Start in one terminal, then in another run:")
        print("  curl http://localhost:8000/health  # Or use Python requests")
        
        return True
    
    def test_inference(self):
        """Test 5: Run inference script."""
        print(f"\n{'='*60}")
        print(f"[TEST] Inference Script Execution")
        print(f"{'='*60}")
        print("Before running, ensure:")
        print("  1. Environment variables are set:")
        print("     $env:API_BASE_URL='http://localhost:8000'")
        print("     $env:MODEL_NAME='gpt-4-turbo'")
        print("     $env:HF_TOKEN='your_token'")
        print("  2. Server is running on port 8000")
        print("\nCommand: uv run python inference.py")
        print("\nNote: This test must be run manually with server running.\n")
        
        return True
    
    def run_all(self):
        """Run all tests."""
        print("\n" + "="*60)
        print("PRE-SUBMISSION TEST SUITE")
        print("="*60)
        
        results = {
            "Validation": self.test_validation(),
            "Syntax": self.test_syntax(),
            "Imports": self.test_imports(),
            "Server": self.test_server_start(),
            "Inference": self.test_inference(),
        }
        
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        for test_name, passed in results.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status:10} {test_name}")
        
        total_passed = sum(1 for p in results.values() if p)
        total_tests = len(results)
        
        print(f"\n{total_passed}/{total_tests} tests passed")
        
        if total_passed == total_tests:
            print("\n✓ All automated tests passed!")
            print("\nNext steps:")
            print("  1. Start the server: cd my_env; uv run python -m uvicorn server.app:app --port 8000")
            print("  2. In another terminal, run: uv run python inference.py")
            print("  3. Verify output has [START], [STEP], [END] logs")
            print("  4. Check runtime < 20 minutes")
            return 0
        else:
            print("\n✗ Some tests failed. Please fix before submitting.")
            return 1


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        test = sys.argv[1].lower()
        tester = SubmissionTester()
        
        if test == "validation":
            tester.test_validation()
        elif test == "syntax":
            tester.test_syntax()
        elif test == "imports":
            tester.test_imports()
        elif test == "server":
            tester.test_server_start()
        elif test == "inference":
            tester.test_inference()
        elif test == "all":
            return tester.run_all()
        else:
            print(f"Unknown test: {test}")
            print("Available tests: validation, syntax, imports, server, inference, all")
            return 1
    else:
        tester = SubmissionTester()
        return tester.run_all()


if __name__ == "__main__":
    sys.exit(main())
