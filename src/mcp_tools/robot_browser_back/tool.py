#!/usr/bin/env python
"""
MCP Tool: Robot Browser Back
Provides browser back navigation functionality for Robot Framework through MCP.
"""

import os
import logging
import time
import json
from typing import Dict, Any, Optional
from pathlib import Path

# Import local modules instead of direct mcp import
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    # Define a stub class for type hinting
    class FastMCP:
        def tool(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_back')

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def initialize_webdriver() -> Optional[webdriver.Chrome]:
    """
    Initialize the Chrome WebDriver with multiple fallback methods.
    
    Returns:
        WebDriver object if successful, None otherwise
    """
    # Set up Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")  # Set a large window size
    
    # Try different approaches to initialize the WebDriver
    driver = None
    last_error = None
    
    try:
        if WEBDRIVER_MANAGER_AVAILABLE:
            # Try with webdriver-manager if available
            logger.info("Trying WebDriver Manager initialization")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
        else:
            # Direct WebDriver initialization
            logger.info("Trying direct WebDriver initialization")
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
    except Exception as e:
        last_error = str(e)
        logger.warning(f"WebDriver initialization failed: {e}")
            
    if driver is None:
        logger.error(f"All WebDriver initialization methods failed. Last error: {last_error}")
        
    return driver

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def browser_go_back(starting_url: str, wait_time: int = 5) -> Dict[str, Any]:
    """
    Navigate back in browser history.
    
    Args:
        starting_url: URL to start from before going back
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with navigation status and page metadata
    """
    result = {
        "starting_url": starting_url,
        "previous_url": None,
        "status": "success",
        "robot_command": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["status"] = "error"
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Navigate to the starting URL
        logger.info(f"Navigating to starting URL: {starting_url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(starting_url)
        
        # Check if there's a history to go back to
        history_length = driver.execute_script("return window.history.length")
        if history_length <= 1:
            result["status"] = "warning"
            result["error"] = "No browser history available to go back"
            return result
        
        # Store the current URL before navigating back
        current_url = driver.current_url
        
        # Go back
        logger.info(f"Navigating back from: {current_url}")
        driver.back()
        
        # Wait for page to load
        time.sleep(wait_time)
        
        # Get the previous URL
        previous_url = driver.current_url
        result["previous_url"] = previous_url
        
        # Generate Robot Framework command for back navigation
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Navigate Back
    Go Back
    Wait Until Page Contains Element    tag:body    timeout={wait_time}s
"""
        result["robot_command"] = robot_command
        
        return result
    except TimeoutException:
        logger.error(f"Timeout while navigating back from URL: {starting_url}")
        result["status"] = "error"
        result["error"] = f"Timeout after {wait_time*2} seconds"
        return result
    except Exception as e:
        logger.error(f"Error navigating back: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_back_script(
    starting_url: str, 
    output_file: str,
    browser: str = "Chrome",
    wait_time: int = 5
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for navigating back in browser history.
    
    Args:
        starting_url: URL to start from before going back
        output_file: File to save the generated script
        browser: Browser to use (default is Chrome)
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for navigating back in browser history
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{STARTING_URL}}  {starting_url}
${{BROWSER}}       {browser}
${{WAIT_TIME}}     {wait_time}

*** Test Cases ***
Navigate Back In History
    [Documentation]    Navigate to a URL and then go back in browser history
    Open Browser    ${{STARTING_URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    
    # Make a navigation to create history (could be replaced with a real navigation)
    Click Link    xpath=(//a)[1]    # Click first link on page
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    
    # Go back in history
    Go Back
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    
    # Verify navigation was successful
    Location Should Not Be    about:blank
"""
        
        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Write the script to the output file
        with open(output_file, 'w') as f:
            f.write(script_content)
            
        return result
    except Exception as e:
        logger.error(f"Error generating back navigation script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser back navigation tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_navigate_back(
        starting_url: str,
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Navigate back in browser history.
        
        Args:
            starting_url: URL to start from before going back
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with navigation status and page metadata
        """
        logger.info(f"Received request to navigate back from URL: {starting_url}")
        result = browser_go_back(starting_url, wait_time)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_back_script(
        starting_url: str,
        output_file: str,
        browser: str = "Chrome",
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for navigating back in browser history.
        
        Args:
            starting_url: URL to start from before going back
            output_file: File to save the generated script
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate back navigation script from URL: {starting_url}")
        result = generate_back_script(starting_url, output_file, browser, wait_time)
        return result 