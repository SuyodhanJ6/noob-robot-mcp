#!/usr/bin/env python
"""
MCP Tool: Robot Browser Close
Provides browser closing functionality for Robot Framework through MCP.
"""

import os
import logging
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
from selenium.common.exceptions import WebDriverException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_close')

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

def close_browser(url: Optional[str] = None) -> Dict[str, Any]:
    """
    Close the browser after optionally navigating to a URL.
    
    Args:
        url: Optional URL to navigate to before closing (to demonstrate the browser was working)
        
    Returns:
        Dictionary with close status
    """
    result = {
        "status": "success",
        "url": url,
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
            
        # Optionally navigate to a URL to demonstrate the browser is working
        if url:
            logger.info(f"Navigating to URL: {url}")
            driver.get(url)
            result["title"] = driver.title
            
        # Close the browser
        logger.info("Closing browser")
        driver.quit()
        driver = None
        
        # Generate Robot Framework command for closing
        robot_command = """*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Close Browser Window
    Close Browser
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error closing browser: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_close_script(
    output_file: str,
    url: Optional[str] = None,
    browser: str = "Chrome"
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for closing a browser.
    
    Args:
        output_file: File to save the generated script
        url: Optional URL to navigate to before closing
        browser: Browser to use (default is Chrome)
        
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
Documentation     Robot Framework script for closing a browser
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{BROWSER}}      {browser}
"""

        if url:
            script_content += f"${{URL}}          {url}\n"

        script_content += """
*** Test Cases ***
Close Browser Test
    [Documentation]    Open and close a browser
"""
        
        if url:
            script_content += f"""    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=10s
    
"""
        else:
            script_content += f"""    Open Browser    about:blank    ${{BROWSER}}
    
"""
            
        script_content += """    # Close the browser
    Close Browser
    
    # Verify browser is closed (this will pass as long as no browser is open)
    ${browser_count}=    Get Number Of Browsers
    Should Be Equal As Numbers    ${browser_count}    0
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
        logger.error(f"Error generating browser close script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser close tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_close(
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Close the browser after optionally navigating to a URL.
        
        Args:
            url: Optional URL to navigate to before closing
            
        Returns:
            Dictionary with close status
        """
        logger.info(f"Received request to close browser")
        result = close_browser(url)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_close_script(
        output_file: str,
        url: Optional[str] = None,
        browser: str = "Chrome"
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for closing a browser.
        
        Args:
            output_file: File to save the generated script
            url: Optional URL to navigate to before closing
            browser: Browser to use (default is Chrome)
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate browser close script")
        result = generate_close_script(output_file, url, browser)
        return result 