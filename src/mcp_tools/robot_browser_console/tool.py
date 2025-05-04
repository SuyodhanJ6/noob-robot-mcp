#!/usr/bin/env python
"""
MCP Tool: Robot Browser Console
Provides browser console message retrieval for Robot Framework through MCP.
"""

import os
import logging
import time
import json
from typing import Dict, Any, Optional, List
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
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import WebDriverException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_console')

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def initialize_webdriver_with_logging() -> Optional[webdriver.Chrome]:
    """
    Initialize the Chrome WebDriver with console logging enabled.
    
    Returns:
        WebDriver object if successful, None otherwise
    """
    # Enable logging capabilities
    capabilities = DesiredCapabilities.CHROME
    capabilities['goog:loggingPrefs'] = {'browser': 'ALL'}
    
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
                options=chrome_options,
                desired_capabilities=capabilities
            )
        else:
            # Direct WebDriver initialization
            logger.info("Trying direct WebDriver initialization")
            service = Service()
            driver = webdriver.Chrome(
                service=service, 
                options=chrome_options,
                desired_capabilities=capabilities
            )
            
    except Exception as e:
        last_error = str(e)
        logger.warning(f"WebDriver initialization failed: {e}")
            
    if driver is None:
        logger.error(f"All WebDriver initialization methods failed. Last error: {last_error}")
        
    return driver

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def get_console_messages(url: str, wait_time: int = 5) -> Dict[str, Any]:
    """
    Get browser console messages from a web page.
    
    Args:
        url: URL to navigate to
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with console messages
    """
    result = {
        "url": url,
        "console_messages": [],
        "status": "success",
        "robot_command": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize WebDriver with console logging
        driver = initialize_webdriver_with_logging()
        if not driver:
            result["status"] = "error"
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(url)
        
        # Wait for page to load and execute any JavaScript
        time.sleep(wait_time)
        
        # Get console logs
        console_entries = driver.get_log('browser')
        
        # Format console entries
        console_messages = []
        for entry in console_entries:
            message = {
                "level": entry.get('level', ''),
                "message": entry.get('message', ''),
                "source": entry.get('source', ''),
                "timestamp": entry.get('timestamp', '')
            }
            console_messages.append(message)
            
        result["console_messages"] = console_messages
        
        # Generate Robot Framework command for console logging
        robot_command = """*** Settings ***
Library           SeleniumLibrary
Library           Collections

*** Keywords ***
Capture Console Logs
    [Arguments]    ${url}
    # Note: This is a custom implementation as Robot Framework doesn't have direct console logging
    # This would require a custom Python library
    Open Browser    ${url}    Chrome    options=add_argument("--enable-logging");add_argument("--v=1")
    Execute Javascript    console.log('Console logging test from Robot Framework');
    # In real implementation, you would need to create a custom keyword to access logs
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error getting console messages: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_console_script(
    url: str, 
    output_file: str,
    browser: str = "Chrome",
    wait_time: int = 5,
    include_test_messages: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for capturing console messages.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        browser: Browser to use (default is Chrome)
        wait_time: Time to wait for page to load in seconds
        include_test_messages: Whether to include test messages in the console
        
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
Documentation     Robot Framework script for capturing browser console messages
Library           SeleniumLibrary
Library           Collections
Library           OperatingSystem

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
${{WAIT_TIME}}    {wait_time}

*** Test Cases ***
Capture Browser Console Messages
    [Documentation]    Navigate to a page and capture console messages
    
    # Open browser with logging enabled
    ${{\$options}}=    Create Dictionary    goog:loggingPrefs=${{dict(browser=ALL)}}
    Open Browser    ${{URL}}    ${{BROWSER}}    desired_capabilities=${{options}}
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
"""

        if include_test_messages:
            script_content += """    
    # Generate test console messages
    Execute Javascript    console.log('INFO: Test message from Robot Framework');
    Execute Javascript    console.warn('WARNING: Test warning message');
    Execute Javascript    console.error('ERROR: Test error message');
    
"""

        script_content += """    # Custom Python function to get console logs - this would need to be implemented
    # in a custom library as SeleniumLibrary doesn't provide direct access to console logs
    
    # This is a placeholder for what the implementation might look like
    # ${logs}=    Get Browser Console Logs
    # Log    ${logs}
    
    # For demonstration, we'll just create a test file with sample log output
    Create File    console_logs.txt    Sample console log output\\nThis would contain actual console logs in a real implementation
    
    Close Browser
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
        logger.error(f"Error generating console script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser console tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_get_console_messages(
        url: str,
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Get browser console messages from a web page.
        
        Args:
            url: URL to navigate to
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with console messages
        """
        logger.info(f"Received request to get console messages from URL: {url}")
        result = get_console_messages(url, wait_time)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_console_script(
        url: str,
        output_file: str,
        browser: str = "Chrome",
        wait_time: int = 5,
        include_test_messages: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for capturing console messages.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for page to load in seconds
            include_test_messages: Whether to include test messages in the console
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate console script for URL: {url}")
        result = generate_console_script(url, output_file, browser, wait_time, include_test_messages)
        return result