#!/usr/bin/env python
"""
MCP Tool: Robot Browser Tab Select
Provides functionality to switch between browser tabs through MCP.
"""

import logging
import base64
from typing import Dict, Any, Optional, List, Union

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
from selenium.common.exceptions import WebDriverException, NoSuchWindowException

# Configure logging
logger = logging.getLogger('robot_tool.browser_tab_select')

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

async def select_tab(
    tab_index: int,
    take_screenshot: bool = True,
    wait_time: int = 1
) -> Dict[str, Any]:
    """
    Switch to a specific browser tab by index.
    
    Args:
        tab_index: Zero-based index of the tab to select
        take_screenshot: Whether to take a screenshot after switching
        wait_time: Time to wait after switching tabs in seconds
        
    Returns:
        Dictionary with operation status and tab information
    """
    result = {
        "status": "success",
        "tab_index": tab_index,
        "error": None,
        "tab_count": 0,
        "current_tab_index": 0,
        "screenshot": None,
        "tabs": []
    }
    
    try:
        # Get the browser instance
        browser = BrowserManager.get_driver()
        
        # Get all window handles
        handles = browser.window_handles
        result["tab_count"] = len(handles)
        
        # Map of all tabs for informational purposes
        tab_info = []
        current_handle = browser.current_window_handle
        current_index = handles.index(current_handle)
        
        # Store information about the current tab configuration
        result["current_tab_index"] = current_index
        
        # Validate tab index
        if tab_index < 0 or tab_index >= len(handles):
            result["status"] = "error"
            result["error"] = f"Invalid tab index: {tab_index}. Valid range: 0-{len(handles)-1}"
            return result
        
        # Switch to the requested tab
        target_handle = handles[tab_index]
        browser.switch_to.window(target_handle)
        
        # Brief pause to allow the tab to become active
        import time
        time.sleep(wait_time)
        
        # Get information about all tabs
        for i, handle in enumerate(handles):
            # Store minimal info without switching to each tab
            tab_info.append({
                "index": i,
                "handle": handle,
                "is_current": (i == tab_index)
            })
        
        # Store current URL after switch
        result["current_url"] = browser.current_url
        result["page_title"] = browser.title
        result["tabs"] = tab_info
        
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
Select Browser Tab By Index
    [Arguments]    ${tab_index}
    ${handles}=    Get Window Handles
    Switch Window    ${handles}[${tab_index}]
"""
        result["robot_command"] = robot_command
        
        return result
        
    except NoSuchWindowException as e:
        logger.error(f"Tab/window no longer exists: {e}")
        result["status"] = "error"
        result["error"] = f"Tab does not exist: {str(e)}"
        return result
    except WebDriverException as e:
        logger.error(f"WebDriver error selecting tab: {e}")
        result["status"] = "error"
        result["error"] = f"WebDriver error: {str(e)}"
        return result
    except Exception as e:
        logger.error(f"Error selecting tab: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

async def list_tabs() -> Dict[str, Any]:
    """
    List all available browser tabs.
    
    Returns:
        Dictionary with information about all tabs
    """
    result = {
        "status": "success",
        "tab_count": 0,
        "current_tab_index": 0,
        "tabs": [],
        "error": None
    }
    
    try:
        # Get the browser instance
        browser = BrowserManager.get_driver()
        
        # Get all window handles
        handles = browser.window_handles
        result["tab_count"] = len(handles)
        
        # Get current window handle to identify current tab
        current_handle = browser.current_window_handle
        current_index = handles.index(current_handle)
        result["current_tab_index"] = current_index
        
        # Store current URL and title
        current_url = browser.current_url
        current_title = browser.title
        
        # Initialize tabs info
        tabs_info = []
        
        # Collect info about all tabs
        for i, handle in enumerate(handles):
            tab_info = {
                "index": i,
                "handle": handle,
                "is_current": (handle == current_handle)
            }
            
            # Add URL and title for current tab without switching
            if handle == current_handle:
                tab_info["url"] = current_url
                tab_info["title"] = current_title
            
            tabs_info.append(tab_info)
        
        result["tabs"] = tabs_info
        
        return result
    except WebDriverException as e:
        logger.error(f"WebDriver error listing tabs: {e}")
        result["status"] = "error"
        result["error"] = f"WebDriver error: {str(e)}"
        return result
    except Exception as e:
        logger.error(f"Error listing tabs: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser tab select tool with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_tab_select(
        tab_index: int,
        take_screenshot: bool = True,
        wait_time: int = 1
    ) -> Dict[str, Any]:
        """
        Switch to a specific browser tab by index.
        
        This tool allows switching between open browser tabs in the
        current browser session.
        
        Args:
            tab_index: Zero-based index of the tab to select
            take_screenshot: Whether to take a screenshot after switching
            wait_time: Time to wait after switching tabs in seconds
            
        Returns:
            Dictionary with operation status and tab information
        """
        logger.info(f"Selecting browser tab with index: {tab_index}")
        return await select_tab(tab_index, take_screenshot, wait_time)
    
    @mcp.tool()
    async def robot_browser_tab_list() -> Dict[str, Any]:
        """
        List all available browser tabs.
        
        This tool returns information about all open tabs in the current
        browser session.
        
        Returns:
            Dictionary with information about all tabs
        """
        logger.info("Listing all browser tabs")
        return await list_tabs() 