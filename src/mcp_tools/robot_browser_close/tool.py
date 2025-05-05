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

# Import shared browser manager
from ..robot_browser_manager import BrowserManager

logger = logging.getLogger('robot_tool.browser_close')

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

# Remove initialize_webdriver as it's handled by BrowserManager
# def initialize_webdriver() -> Optional[webdriver.Chrome]:
#     """
#     Initialize the Chrome WebDriver with multiple fallback methods.
#     
#     Returns:
#         WebDriver object if successful, None otherwise
#     """
#     # Set up Chrome options for headless browsing
#     chrome_options = Options()
#     chrome_options.add_argument("--headless")
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--window-size=1920,1080")  # Set a large window size
#     
#     # Try different approaches to initialize the WebDriver
#     driver = None
#     last_error = None
#     
#     try:
#         if WEBDRIVER_MANAGER_AVAILABLE:
#             # Try with webdriver-manager if available
#             logger.info("Trying WebDriver Manager initialization")
#             driver = webdriver.Chrome(
#                 service=Service(ChromeDriverManager().install()),
#                 options=chrome_options
#             )
#         else:
#             # Direct WebDriver initialization
#             logger.info("Trying direct WebDriver initialization")
#             service = Service()
#             driver = webdriver.Chrome(service=service, options=chrome_options)
#             
#     except Exception as e:
#         last_error = str(e)
#         logger.warning(f"WebDriver initialization failed: {e}")
#             
#     if driver is None:
#         logger.error(f"All WebDriver initialization methods failed. Last error: {last_error}")
#         
#     return driver

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
    
    # driver = None # No longer needed
    try:
        # Optionally navigate to a URL using the existing browser
        if url:
            try:
                driver = BrowserManager.get_driver() # Get potentially existing driver
                logger.info(f"Navigating to URL before closing: {url}")
                driver.get(url)
                result["title"] = driver.title
            except WebDriverException as e:
                 logger.warning(f"Could not navigate to {url} before closing (maybe browser was already closed?): {e}")
                 result["warning"] = f"Could not navigate to {url} before closing: {e}"
            except Exception as e: # Catch other potential errors like BrowserManager init failure
                result["status"] = "error"
                result["error"] = f"Failed to get WebDriver to navigate before close: {e}"
                return result
            
        # Close the shared browser instance using the manager
        logger.info("Requesting BrowserManager to close browser")
        BrowserManager.close_driver()
        
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
    # finally:
        # The manager now handles closing
        # if driver:
        #     driver.quit()

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
    """Register the browser close tool with MCP."""
    logger.info("Registering Robot Browser Close tool")
    
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
        # Call the modified close_browser function
        return close_browser(url)
    
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
        # Call the existing script generation function (no changes needed here)
        return generate_close_script(
            output_file=output_file,
            url=url,
            browser=browser
        ) 