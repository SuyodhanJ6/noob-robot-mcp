#!/usr/bin/env python
"""
MCP Tool: Robot Browser Resize
Provides browser window resizing functionality for Robot Framework through MCP.
"""

import os
import logging
import json
from typing import Dict, Any, Optional, Tuple
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

logger = logging.getLogger('robot_tool.browser_resize')

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
    
    # Do not set window size here as we'll resize it later
    
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

def resize_browser_window(
    url: Optional[str],
    width: int,
    height: int,
    maximize: bool = False
) -> Dict[str, Any]:
    """
    Resize the browser window.
    
    Args:
        url: Optional URL to navigate to
        width: Window width in pixels
        height: Window height in pixels
        maximize: Whether to maximize the window (overrides width/height)
        
    Returns:
        Dictionary with resize status and window size information
    """
    result = {
        "url": url,
        "width": width,
        "height": height,
        "maximize": maximize,
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
        
        # Navigate to URL if provided
        if url:
            logger.info(f"Navigating to URL: {url}")
            driver.get(url)
        
        # Get the current window size before resizing
        current_size = driver.get_window_size()
        result["previous_width"] = current_size["width"]
        result["previous_height"] = current_size["height"]
        
        # Resize or maximize the window
        if maximize:
            logger.info("Maximizing browser window")
            driver.maximize_window()
        else:
            logger.info(f"Resizing browser window to {width}x{height}")
            driver.set_window_size(width, height)
        
        # Get the new window size
        new_size = driver.get_window_size()
        result["new_width"] = new_size["width"]
        result["new_height"] = new_size["height"]
        
        # Generate Robot Framework command
        if maximize:
            robot_command = """*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Maximize Browser Window
    [Arguments]    ${url}
    Open Browser    ${url}    Chrome
    Maximize Browser Window
"""
        else:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Resize Browser Window
    [Arguments]    ${{url}}    ${{width}}    ${{height}}
    Open Browser    ${{url}}    Chrome
    Set Window Size    {width}    {height}
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error resizing browser window: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_resize_script(
    output_file: str,
    url: str,
    width: int = 1920,
    height: int = 1080,
    maximize: bool = False,
    browser: str = "Chrome",
    responsive_check: bool = False
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for resizing a browser window.
    
    Args:
        output_file: File to save the generated script
        url: URL to navigate to
        width: Window width in pixels
        height: Window height in pixels
        maximize: Whether to maximize the window (overrides width/height)
        browser: Browser to use (default is Chrome)
        responsive_check: Whether to include responsive size checks
        
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
Documentation     Robot Framework script for resizing a browser window
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
"""

        if not maximize:
            script_content += f"""${{WIDTH}}        {width}
${{HEIGHT}}       {height}

"""
            
        # Add test case
        if maximize:
            script_content += """
*** Test Cases ***
Maximize Browser Window
    [Documentation]    Open a browser and maximize the window
    
    # Open browser
    Open Browser    ${URL}    ${BROWSER}
    
    # Maximize window
    Maximize Browser Window
    
    # Get window size
    ${width}    ${height}=    Get Window Size
    Log    Window size: ${width}x${height}
"""
        else:
            script_content += """
*** Test Cases ***
Resize Browser Window
    [Documentation]    Open a browser and resize the window
    
    # Open browser
    Open Browser    ${URL}    ${BROWSER}
    
    # Resize window
    Set Window Size    ${WIDTH}    ${HEIGHT}
    
    # Verify size
    ${actual_width}    ${actual_height}=    Get Window Size
    Log    Window size: ${actual_width}x${actual_height}
    Should Be Equal As Numbers    ${actual_width}    ${WIDTH}
    Should Be Equal As Numbers    ${actual_height}    ${HEIGHT}
"""
        
        # Add responsive design testing if requested
        if responsive_check:
            script_content += """
    # Optional responsive design testing
    # Test different screen sizes
    
    # Mobile portrait (360x640)
    Set Window Size    360    640
    Sleep    1s
    
    # Mobile landscape (640x360)
    Set Window Size    640    360
    Sleep    1s
    
    # Tablet portrait (768x1024)
    Set Window Size    768    1024
    Sleep    1s
    
    # Tablet landscape (1024x768)
    Set Window Size    1024    768
    Sleep    1s
    
    # Desktop (1366x768)
    Set Window Size    1366    768
    Sleep    1s
    
    # Large desktop (1920x1080)
    Set Window Size    1920    1080
    Sleep    1s
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
        logger.error(f"Error generating resize script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser resize tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_resize_window(
        width: int,
        height: int,
        url: Optional[str] = None,
        maximize: bool = False
    ) -> Dict[str, Any]:
        """
        Resize the browser window.
        
        Args:
            width: Window width in pixels
            height: Window height in pixels
            url: Optional URL to navigate to
            maximize: Whether to maximize the window (overrides width/height)
            
        Returns:
            Dictionary with resize status and window size information
        """
        logger.info(f"Received request to resize browser window to {width}x{height}")
        result = resize_browser_window(url, width, height, maximize)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_resize_script(
        output_file: str,
        url: str,
        width: int = 1920,
        height: int = 1080,
        maximize: bool = False,
        browser: str = "Chrome",
        responsive_check: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for resizing a browser window.
        
        Args:
            output_file: File to save the generated script
            url: URL to navigate to
            width: Window width in pixels
            height: Window height in pixels
            maximize: Whether to maximize the window (overrides width/height)
            browser: Browser to use (default is Chrome)
            responsive_check: Whether to include responsive size checks
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate resize script for size {width}x{height}")
        result = generate_resize_script(output_file, url, width, height, maximize, browser, responsive_check)
        return result 