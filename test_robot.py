#!/usr/bin/env python

import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('robot_test')

# Import helper functions
from src.utils.helpers import get_available_robot_libraries
from src.mcp_tools.robot_library_explorer.tool import explore_libraries
from src.mcp_tools.robot_test_linter.tool import lint_robot_files
from src.mcp_tools.robot_runner.tool import run_robot_tests

def main():
    # Test 1: Verify library explorer works
    logger.info("Testing robot_library_explorer...")
    libraries = get_available_robot_libraries()
    logger.info(f"Found {len(libraries)} libraries")
    
    # Test 2: Explore libraries
    result = explore_libraries(
        library_name=None,
        include_standard_libraries=True,
        include_installed_libraries=True
    )
    logger.info(f"Explored libraries: {len(result['libraries'])}")
    if result["error"]:
        logger.error(f"Error in explore_libraries: {result['error']}")
    
    # Create a simple robot test file for testing
    test_file_path = Path("simple_test.robot")
    with open(test_file_path, "w") as f:
        f.write("""*** Settings ***
Documentation     A simple test file
Library           BuiltIn

*** Variables ***
${MESSAGE}        Hello, Robot Framework!

*** Test Cases ***
Simple Test
    Log    ${MESSAGE}
    Should Be Equal    ${MESSAGE}    Hello, Robot Framework!
""")
    
    # Test 3: Lint the test file
    logger.info("Testing robot_test_linter...")
    lint_result = lint_robot_files(
        file_path=str(test_file_path),
        recursive=False
    )
    logger.info(f"Lint results: {lint_result['summary']}")
    if lint_result["error"]:
        logger.error(f"Error in lint_robot_files: {lint_result['error']}")
    
    # Test 4: Run the test
    logger.info("Testing robot_runner...")
    run_result = run_robot_tests(
        file_path=str(test_file_path),
        timeout=30
    )
    logger.info(f"Run result: {run_result['success']}")
    if run_result["error"]:
        logger.error(f"Error in run_robot_tests: {run_result['error']}")
    
    # Clean up
    if test_file_path.exists():
        test_file_path.unlink()
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    main() 