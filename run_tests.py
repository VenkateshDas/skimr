#!/usr/bin/env python
"""
Test runner script for the YouTube Analysis API TDD suite.

Usage:
    python run_tests.py [options]

Options:
    --unit           Run only unit tests
    --integration    Run only integration tests
    --all            Run all tests (default)
    --coverage       Generate coverage report
    --verbose        Verbose output
    --quiet          Minimal output
    --xvs            Generate JUnit XML report
    --markers        List available markers
    --help           Show this help message
"""

import sys
import os
import subprocess
import argparse


# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run YouTube Analysis API tests")
    
    # Test selection options
    test_group = parser.add_argument_group("Test Selection")
    test_group.add_argument("--unit", action="store_true", help="Run only unit tests")
    test_group.add_argument("--integration", action="store_true", help="Run only integration tests")
    test_group.add_argument("--all", action="store_true", help="Run all tests (default)")
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument("--coverage", action="store_true", help="Generate coverage report")
    output_group.add_argument("--verbose", action="store_true", help="Verbose output")
    output_group.add_argument("--quiet", action="store_true", help="Minimal output")
    output_group.add_argument("--xvs", action="store_true", help="Generate JUnit XML report")
    
    # Misc options
    misc_group = parser.add_argument_group("Miscellaneous")
    misc_group.add_argument("--markers", action="store_true", help="List available markers")
    
    return parser.parse_args()


def run_tests(args):
    """Run tests with the specified options."""
    # Set PYTHONPATH for the subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.dirname(__file__))
    
    cmd = ["pytest"]
    
    # Test selection
    if args.unit:
        cmd.append("-m unit")
    elif args.integration:
        cmd.append("-m integration")
    
    # Output options
    if args.verbose:
        cmd.append("-v")
    if args.quiet:
        cmd.append("-q")
    if args.coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing"])
    if args.xvs:
        cmd.append("--junitxml=test-results.xml")
    
    # Miscellaneous options
    if args.markers:
        cmd = ["pytest", "--markers"]
    
    # Run the command
    command = " ".join(cmd)
    print(f"Running: {command}")
    print(f"PYTHONPATH={env['PYTHONPATH']}")
    subprocess.run(command, shell=True, env=env)


def main():
    """Main entry point."""
    args = parse_args()
    
    # If no options provided, run all tests
    if not any([args.unit, args.integration, args.markers]):
        args.all = True
    
    run_tests(args)


if __name__ == "__main__":
    main() 