#!/usr/bin/env python3
"""
Test runner for YouTube Analysis Crew.
"""

import unittest
import sys
import os
import argparse

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.youtube_analysis.utils.logging import setup_logger

# Set up logger
logger = setup_logger("test_runner", log_level="INFO")

def run_all_tests():
    """Run all tests in the project."""
    logger.info("Running all tests...")
    
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(
        start_dir=os.path.dirname(__file__),
        pattern='test_*.py'
    )
    
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    return result.wasSuccessful()

def run_specific_test(test_module):
    """Run a specific test module."""
    logger.info(f"Running test module: {test_module}")
    
    try:
        # Import the test module
        __import__(test_module)
        module = sys.modules[test_module]
        
        # Run the tests in the module
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromModule(module)
        
        test_runner = unittest.TextTestRunner(verbosity=2)
        result = test_runner.run(test_suite)
        
        return result.wasSuccessful()
    except ImportError:
        logger.error(f"Could not import test module: {test_module}")
        return False

def main():
    """Main function to run the tests."""
    parser = argparse.ArgumentParser(description="Run tests for YouTube Analysis Crew")
    parser.add_argument("--module", type=str, help="Specific test module to run (e.g., src.youtube_analysis.tests.tools.test_youtube_tools_unittest)")
    args = parser.parse_args()
    
    if args.module:
        success = run_specific_test(args.module)
    else:
        success = run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 