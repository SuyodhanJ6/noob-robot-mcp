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

# Add import for AuthManager
from src.utils.auth_manager import AuthManager

# Configure logging
logger = logging.getLogger('robot_tool.browser_tab_select')

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

async def select_tab(
    tab_index: int,
    take_screenshot: bool = True,
    wait_time: int = 1,
    need_login: bool = False,
    url: Optional[str] = None,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    username_locator: Optional[str] = None,
    password_locator: Optional[str] = None,
    submit_locator: Optional[str] = None,
    success_indicator: Optional[str] = None
) -> Dict[str, Any]:
    """
    Switch to a specific browser tab by index.
    
    Args:
        tab_index: Zero-based index of the tab to select
        take_screenshot: Whether to take a screenshot after switching
        wait_time: Time to wait after switching tabs in seconds
        need_login: Whether login is required before tab selection
        url: URL to navigate to after tab selection (optional)
        login_url: URL of the login page if different from target URL
        username: Username for login
        password: Password for login
        username_locator: Locator for username field
        password_locator: Locator for password field
        submit_locator: Locator for submit button
        success_indicator: Optional element to verify successful login
        
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
        "tabs": [],
        "login_status": None
    }
    
    try:
        # Handle login if needed and URL is provided
        if need_login and url:
            # Check if already authenticated
            if not AuthManager.is_authenticated(url):
                if not all([username, password, username_locator, password_locator, submit_locator]):
                    result["status"] = "error"
                    result["error"] = "Login requested but missing required login parameters"
                    return result
                    
                # Perform login
                login_result = AuthManager.login(
                    login_url or url,
                    username,
                    password,
                    username_locator,
                    password_locator,
                    submit_locator,
                    success_indicator,
                    wait_time
                )
                
                result["login_status"] = login_result
                
                if not login_result["success"]:
                    result["status"] = "error"
                    result["error"] = f"Login failed: {login_result.get('message', 'Unknown error')}"
                    return result
            else:
                result["login_status"] = {"success": True, "message": "Already authenticated"}
        
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
        wait_time: int = 1,
        need_login: bool = False,
        url: Optional[str] = None,
        login_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        username_locator: Optional[str] = None,
        password_locator: Optional[str] = None,
        submit_locator: Optional[str] = None,
        success_indicator: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Switch to a specific browser tab by index.
        
        This tool allows switching between open browser tabs in the
        current browser session. It can optionally handle authentication 
        if needed.
        
        Args:
            tab_index: Zero-based index of the tab to select
            take_screenshot: Whether to take a screenshot after switching
            wait_time: Time to wait after switching tabs in seconds
            need_login: Whether login is required before tab selection
            url: URL to navigate to after tab selection (optional)
            login_url: URL of the login page if different from target URL
            username: Username for login
            password: Password for login
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for submit button
            success_indicator: Optional element to verify successful login
            
        Returns:
            Dictionary with operation status and tab information
        """
        logger.info(f"Selecting browser tab with index: {tab_index}")
        if need_login and url:
            logger.info("Authentication required for tab selection")
            
        return await select_tab(
            tab_index, 
            take_screenshot, 
            wait_time,
            need_login,
            url,
            login_url,
            username,
            password,
            username_locator,
            password_locator,
            submit_locator,
            success_indicator
        )
    
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