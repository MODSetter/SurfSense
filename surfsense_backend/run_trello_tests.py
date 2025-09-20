#!/usr/bin/env python3
"""
Test runner script for Trello connector tests.
Runs all Trello-related tests with proper configuration.
"""

import sys
import subprocess
import os
from pathlib import Path

def run_tests():
    """Run all Trello connector tests."""
    # Get the project root directory
    project_root = Path(__file__).parent
    
    # Test files to run
    test_files = [
        "tests/connectors/test_trello_connector.py",
        "tests/connectors/test_trello_connector_comprehensive.py",
        "tests/integration/test_trello_integration.py",
    ]
    
    # Check if test files exist
    missing_files = []
    for test_file in test_files:
        if not (project_root / test_file).exists():
            missing_files.append(test_file)
    
    if missing_files:
        print(f"Warning: The following test files are missing: {missing_files}")
        print("Running available tests...")
        test_files = [f for f in test_files if f not in missing_files]
    
    if not test_files:
        print("No test files found!")
        return 1
    
    # Run pytest with verbose output
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--color=yes",  # Colored output
        "--durations=10",  # Show 10 slowest tests
    ] + test_files
    
    print(f"Running command: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, cwd=project_root, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

def run_specific_test(test_name):
    """Run a specific test by name."""
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",
        "--tb=short",
        "--color=yes",
        "-k", test_name,
        "tests/"
    ]
    
    project_root = Path(__file__).parent
    print(f"Running specific test: {test_name}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, cwd=project_root, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error running test: {e}")
        return 1

def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("Usage:")
            print("  python run_trello_tests.py                    # Run all Trello tests")
            print("  python run_trello_tests.py <test_name>        # Run specific test")
            print("  python run_trello_tests.py --help             # Show this help")
            return 0
        else:
            # Run specific test
            test_name = sys.argv[1]
            return run_specific_test(test_name)
    else:
        # Run all tests
        return run_tests()

if __name__ == "__main__":
    sys.exit(main())
