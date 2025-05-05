#!/usr/bin/env python
"""
MCP Tool: Robot Browser Tab New
Provides functionality to open a new browser tab through MCP.
"""

import logging
import base64
from typing import Dict, Any, Optional

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

# Import the browser manager to use existing session
from src.mcp_tools.robot_browser_manager import BrowserManager
from selenium.common.exceptions import WebDriverException

# Configure logging
logger = logging.getLogger('robot_tool.browser_tab_new')

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

async def open_new_tab(
    url: Optional[str] = None,
    take_screenshot: bool = True,
    wait_time: int = 3
) -> Dict[str, Any]:
    """
    Open a new browser tab and optionally navigate to a URL.
    
    Args:
        url: URL to navigate to in the new tab (optional)
        take_screenshot: Whether to take a screenshot after opening the tab
        wait_time: Time to wait for the tab to load in seconds
        
    Returns:
        Dictionary with operation status and tab information
    """
    result = {
        "status": "success",
        "url": url,
        "error": None,
        "tab_count": 0,
        "current_tab_index": 0,
        "screenshot": None
    }
    
    try:
        # Get the browser instance
        browser = BrowserManager.get_driver()
        
        # Get initial tab/window handles to compare later
        initial_handles = browser.window_handles
        initial_tab_count = len(initial_handles)
        
        # Execute JavaScript to open a new tab
        browser.execute_script("window.open();")
        
        # Wait for the new tab to be available
        import time
        time.sleep(1)  # Brief wait for tab to open
        
        # Switch to the new tab (should be the last handle)
        new_handles = browser.window_handles
        result["tab_count"] = len(new_handles)
        
        if len(new_handles) <= initial_tab_count:
            result["status"] = "error"
            result["error"] = "Failed to open new tab"
            return result
        
        # Switch to the new tab (last one)
        new_tab = new_handles[-1]
        browser.switch_to.window(new_tab)
        result["current_tab_index"] = new_handles.index(new_tab)
        
        # Navigate to URL if provided
        if url:
            browser.get(url)
            # Wait for page to load
            time.sleep(wait_time)
            result["current_url"] = browser.current_url
        else:
            # Default to blank page if no URL provided
            result["current_url"] = browser.current_url
        
        # Take screenshot if requested
        if take_screenshot:
            try:
                result["screenshot"] = browser.get_screenshot_as_base64()
            except Exception as e:
                logger.warning(f"Failed to take screenshot: {e}")
        
        # Generate Robot Framework command for this operation
        robot_command = """*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Open New Browser Tab
    [Arguments]    ${url}=${NONE}
    Execute Javascript    window.open()
    ${handles}=    Get Window Handles
    Switch Window    ${handles}[-1]
    Run Keyword If    "${url}" != "${NONE}"    Go To    ${url}
"""
        result["robot_command"] = robot_command
        
        return result
        
    except WebDriverException as e:
        logger.error(f"WebDriver error opening new tab: {e}")
        result["status"] = "error"
        result["error"] = f"WebDriver error: {str(e)}"
        return result
    except Exception as e:
        logger.error(f"Error opening new tab: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser tab new tool with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_tab_new(
        url: Optional[str] = None,
        take_screenshot: bool = True,
        wait_time: int = 3
    ) -> Dict[str, Any]:
        """
        Open a new browser tab and optionally navigate to a URL.
        
        This tool opens a new browser tab in the current browser session
        and can optionally navigate to a specified URL.
        
        Args:
            url: URL to navigate to in the new tab (optional)
            take_screenshot: Whether to take a screenshot after opening the tab
            wait_time: Time to wait for the tab to load in seconds
            
        Returns:
            Dictionary with operation status and tab information
        """
        logger.info(f"Opening new browser tab with URL: {url if url else 'blank'}")
        return await open_new_tab(url, take_screenshot, wait_time) 