#!/usr/bin/env python
"""
MCP Tool: Robot Browser Forward
Provides browser forward navigation functionality for Robot Framework through MCP.
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

logger = logging.getLogger('robot_tool.browser_forward')

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

def browser_go_forward(starting_url: str, wait_time: int = 5) -> Dict[str, Any]:
    """
    Navigate forward in browser history.
    
    Args:
        starting_url: URL to start from before going forward
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with navigation status and page metadata
    """
    result = {
        "starting_url": starting_url,
        "forward_url": None,
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
        
        # Create a history by navigating to a secondary page
        # Get the first link on the page and navigate to it
        try:
            links = driver.find_elements("tag name", "a")
            if links:
                # Store the current URL
                first_url = driver.current_url
                
                # Click the first link to navigate
                links[0].click()
                time.sleep(wait_time)
                
                # Go back to create forward history
                driver.back()
                time.sleep(wait_time)
                
                # Now go forward
                logger.info(f"Navigating forward from: {driver.current_url}")
                driver.forward()
                
                # Wait for page to load
                time.sleep(wait_time)
                
                # Get the forward URL
                forward_url = driver.current_url
                result["forward_url"] = forward_url
                
                # Generate Robot Framework command for forward navigation
                robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Navigate Forward
    Go Forward
    Wait Until Page Contains Element    tag:body    timeout={wait_time}s
"""
                result["robot_command"] = robot_command
                
                return result
            else:
                result["status"] = "warning"
                result["error"] = "No links found on page to create navigation history"
                return result
        except Exception as e:
            result["status"] = "warning"
            result["error"] = f"Error creating navigation history: {str(e)}"
            return result
            
    except TimeoutException:
        logger.error(f"Timeout while navigating with URL: {starting_url}")
        result["status"] = "error"
        result["error"] = f"Timeout after {wait_time*2} seconds"
        return result
    except Exception as e:
        logger.error(f"Error navigating forward: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_forward_script(
    starting_url: str, 
    output_file: str,
    browser: str = "Chrome",
    wait_time: int = 5
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for navigating forward in browser history.
    
    Args:
        starting_url: URL to start from before going forward
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
Documentation     Robot Framework script for navigating forward in browser history
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{STARTING_URL}}  {starting_url}
${{BROWSER}}       {browser}
${{WAIT_TIME}}     {wait_time}

*** Test Cases ***
Navigate Forward In History
    [Documentation]    Navigate to a URL, click a link, go back, then go forward
    Open Browser    ${{STARTING_URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    
    # Store initial URL
    ${{\$initial_url}}    Get Location
    
    # Click first link to create history
    Click Link    xpath=(//a)[1]    # Click first link on page
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    
    # Go back to initial page
    Go Back
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    Location Should Be    ${{\$initial_url}}
    
    # Go forward in history
    Go Forward
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    
    # Verify navigation was successful
    Location Should Not Be    ${{\$initial_url}}
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
        logger.error(f"Error generating forward navigation script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser forward navigation tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_navigate_forward(
        starting_url: str,
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Navigate forward in browser history.
        
        Args:
            starting_url: URL to start from before going forward
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with navigation status and page metadata
        """
        logger.info(f"Received request to navigate forward from URL: {starting_url}")
        result = browser_go_forward(starting_url, wait_time)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_forward_script(
        starting_url: str,
        output_file: str,
        browser: str = "Chrome",
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for navigating forward in browser history.
        
        Args:
            starting_url: URL to start from before going forward
            output_file: File to save the generated script
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate forward navigation script from URL: {starting_url}")
        result = generate_forward_script(starting_url, output_file, browser, wait_time)
        return result 