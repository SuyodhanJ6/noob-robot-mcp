#!/usr/bin/env python
"""
MCP Tool: Robot Browser Tabs
Provides browser tab management functionality for Robot Framework through MCP.
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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_tabs')

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

def list_tabs(url: Optional[str] = None) -> Dict[str, Any]:
    """
    List all open tabs in the browser.
    
    Args:
        url: Optional URL to navigate to first
        
    Returns:
        Dictionary with list of tabs
    """
    result = {
        "url": url,
        "status": "success",
        "tabs": [],
        "current_tab_index": None,
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
            
        # Get current window handle
        current_handle = driver.current_window_handle
        
        # List tabs
        handles = driver.window_handles
        tabs = []
        current_tab_index = None
        
        for i, handle in enumerate(handles):
            driver.switch_to.window(handle)
            is_current = handle == current_handle
            
            tab_info = {
                "index": i,
                "handle": handle,
                "url": driver.current_url,
                "title": driver.title,
                "is_current": is_current
            }
            
            tabs.append(tab_info)
            
            if is_current:
                current_tab_index = i
                
        # Switch back to the original tab
        driver.switch_to.window(current_handle)
        
        result["tabs"] = tabs
        result["current_tab_index"] = current_tab_index
        
        # Generate Robot Framework command
        robot_command = """*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
List Browser Tabs
    @{handles}=    Get Window Handles
    ${current_handle}=    Get Window Handle
    ${count}=    Get Length    ${handles}
    Log    Number of open tabs: ${count}
    
    FOR    ${index}    ${handle}    IN ENUMERATE    @{handles}
        Switch Window    ${handle}
        ${url}=    Get Location
        ${title}=    Get Title
        ${is_current}=    Evaluate    '${handle}' == '${current_handle}'
        Log    Tab ${index}: ${title} (${url}) - Current: ${is_current}
    END
    
    # Switch back to original window
    Switch Window    ${current_handle}
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error listing tabs: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def new_tab(url: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Open a new tab and navigate to a URL.
    
    Args:
        url: URL to navigate to in the new tab
        base_url: Optional URL to navigate to first in the original tab
        
    Returns:
        Dictionary with tab status
    """
    result = {
        "url": url,
        "base_url": base_url,
        "status": "success",
        "tab_info": None,
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
            
        # Navigate to base URL if provided
        if base_url:
            logger.info(f"Navigating to base URL: {base_url}")
            driver.get(base_url)
            
        # Original window handle
        original_handle = driver.current_window_handle
        
        # Execute JavaScript to open a new tab
        logger.info(f"Opening new tab with URL: {url}")
        driver.execute_script(f"window.open('{url}', '_blank');")
        
        # Wait for the new tab to open
        time.sleep(2)
        
        # Switch to the new tab (should be the last handle)
        handles = driver.window_handles
        new_handle = handles[-1]
        driver.switch_to.window(new_handle)
        
        # Wait for page to load in the new tab
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            result["status"] = "warning"
            result["warning"] = "Timeout waiting for page to load in new tab"
            # Continue anyway
            
        # Get tab info
        tab_info = {
            "handle": new_handle,
            "url": driver.current_url,
            "title": driver.title,
            "index": handles.index(new_handle)
        }
        
        result["tab_info"] = tab_info
        
        # Generate Robot Framework command
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Open New Tab
    [Arguments]    ${{url}}
    Open Browser    about:blank    Chrome
    Execute Javascript    window.open('{url}', '_blank');
    @{{handles}}=    Get Window Handles
    Switch Window    ${{handles}}[-1]
    Wait Until Page Contains Element    tag:body    timeout=10s
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error opening new tab: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def select_tab(index: int, url: Optional[str] = None) -> Dict[str, Any]:
    """
    Select a tab by index.
    
    Args:
        index: Index of the tab to select (0-based)
        url: Optional URL to navigate to first
        
    Returns:
        Dictionary with tab selection status
    """
    result = {
        "index": index,
        "url": url,
        "status": "success",
        "tab_info": None,
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
            
        # Get handles
        handles = driver.window_handles
        
        # Check if the index is valid
        if index < 0 or index >= len(handles):
            result["status"] = "error"
            result["error"] = f"Invalid tab index: {index}. Valid range: 0-{len(handles)-1}"
            return result
            
        # Select the tab
        logger.info(f"Selecting tab at index: {index}")
        handle = handles[index]
        driver.switch_to.window(handle)
        
        # Wait for page to be active
        time.sleep(1)
        
        # Get tab info
        tab_info = {
            "handle": handle,
            "url": driver.current_url,
            "title": driver.title,
            "index": index
        }
        
        result["tab_info"] = tab_info
        
        # Generate Robot Framework command
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Select Tab By Index
    [Arguments]    ${{index}}
    @{{handles}}=    Get Window Handles
    ${{\$handle}}=    Get From List    ${{handles}}    ${{index}}
    Switch Window    ${{\$handle}}
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error selecting tab: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def close_tab(index: Optional[int] = None, url: Optional[str] = None) -> Dict[str, Any]:
    """
    Close a tab by index or the current tab.
    
    Args:
        index: Index of the tab to close (0-based), or None for current tab
        url: Optional URL to navigate to first
        
    Returns:
        Dictionary with tab close status
    """
    result = {
        "index": index,
        "url": url,
        "status": "success",
        "tabs_remaining": 0,
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
            
        # Get handles
        handles = driver.window_handles
        
        # Check if there are any tabs
        if not handles:
            result["status"] = "error"
            result["error"] = "No tabs available to close"
            return result
            
        # Determine which tab to close
        if index is not None:
            # Check if the index is valid
            if index < 0 or index >= len(handles):
                result["status"] = "error"
                result["error"] = f"Invalid tab index: {index}. Valid range: 0-{len(handles)-1}"
                return result
                
            # Select and close the tab
            logger.info(f"Closing tab at index: {index}")
            handle = handles[index]
            driver.switch_to.window(handle)
        else:
            # Close the current tab
            logger.info("Closing current tab")
            
        # Store information about which tab will be active after closing
        next_active_index = None
        if len(handles) > 1:
            current_index = handles.index(driver.current_window_handle)
            if current_index == len(handles) - 1:
                # If we're closing the last tab, the previous one will become active
                next_active_index = current_index - 1
            else:
                # Otherwise, the next tab will become active
                next_active_index = current_index
                
        # Close the tab
        driver.close()
        
        # Remaining tabs
        time.sleep(1)  # Give time for the tab to close
        remaining_handles = driver.window_handles
        result["tabs_remaining"] = len(remaining_handles)
        
        # Switch to a remaining tab if any
        if remaining_handles:
            if next_active_index is not None and next_active_index < len(remaining_handles):
                driver.switch_to.window(remaining_handles[next_active_index])
            else:
                driver.switch_to.window(remaining_handles[0])
                
        # Generate Robot Framework command
        if index is not None:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Close Tab By Index
    [Arguments]    ${{index}}
    @{{handles}}=    Get Window Handles
    ${{\$handle}}=    Get From List    ${{handles}}    ${{index}}
    Switch Window    ${{\$handle}}
    Close Window
    # Switch to first remaining window if any
    @{{remaining_handles}}=    Get Window Handles
    Run Keyword If    len(${{remaining_handles}}) > 0    Switch Window    ${{remaining_handles}}[0]
"""
        else:
            robot_command = """*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Close Current Tab
    Close Window
    # Switch to first remaining window if any
    @{remaining_handles}=    Get Window Handles
    Run Keyword If    len(${remaining_handles}) > 0    Switch Window    ${remaining_handles}[0]
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error closing tab: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_tabs_script(
    output_file: str,
    url: str,
    browser: str = "Chrome",
    num_tabs: int = 3,
    tab_urls: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for tab management.
    
    Args:
        output_file: File to save the generated script
        url: Base URL to navigate to
        browser: Browser to use (default is Chrome)
        num_tabs: Number of tabs to open
        tab_urls: Optional list of URLs for each tab
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Use provided URLs or generate dummy ones
        if tab_urls and len(tab_urls) >= num_tabs:
            urls = tab_urls[:num_tabs]
        else:
            urls = [url]
            for i in range(1, num_tabs):
                urls.append(f"{url}#{i}")
                
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for managing browser tabs
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{BASE_URL}}     {url}
${{BROWSER}}      {browser}

*** Test Cases ***
Browser Tab Management
    [Documentation]    Open multiple tabs and perform tab operations
    
    # Open first tab with base URL
    Open Browser    ${{BASE_URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=10s
    ${{\$title1}}=    Get Title
    Log    Tab 1 Title: ${{\$title1}}
    
"""
        
        # Add commands for opening additional tabs
        for i, tab_url in enumerate(urls[1:], start=2):
            script_content += f"""    # Open tab {i}
    Execute Javascript    window.open('{tab_url}', '_blank');
    @{{handles}}=    Get Window Handles
    Switch Window    ${{handles}}[{i-1}]
    Wait Until Page Contains Element    tag:body    timeout=10s
    ${{\$title{i}}}=    Get Title
    Log    Tab {i} Title: ${{\$title{i}}}
    
"""
        
        # Add commands for tab switching
        script_content += """    # List all tabs
    @{all_handles}=    Get Window Handles
    ${num_tabs}=    Get Length    ${all_handles}
    Log    Number of open tabs: ${num_tabs}
    
    # Switch between tabs
    Switch Window    ${all_handles}[0]
    Log    Switched to tab 1
    Sleep    1s
    
"""
        
        # Add tab cycling
        if num_tabs > 1:
            script_content += """    # Cycle through all tabs
    FOR    ${index}    IN RANGE    0    ${num_tabs}
        Switch Window    ${all_handles}[${index}]
        ${url}=    Get Location
        ${title}=    Get Title
        Log    Tab ${index+1}: ${title} (${url})
        Sleep    1s
    END
    
"""
        
        # Add tab closing
        if num_tabs > 1:
            script_content += """    # Close the last tab
    Switch Window    ${all_handles}[-1]
    Close Window
    
    # Verify number of tabs has decreased
    @{remaining_handles}=    Get Window Handles
    ${remaining_tabs}=    Get Length    ${remaining_handles}
    Should Be Equal As Numbers    ${remaining_tabs}    ${num_tabs - 1}
    
    # Switch back to the first tab
    Switch Window    ${remaining_handles}[0]
    Log    Switched back to the first tab
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
        logger.error(f"Error generating tabs script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser tab management tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_list_tabs(
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List all open tabs in the browser.
        
        Args:
            url: Optional URL to navigate to first
            
        Returns:
            Dictionary with list of tabs
        """
        logger.info("Received request to list browser tabs")
        result = list_tabs(url)
        return result
    
    @mcp.tool()
    async def robot_browser_new_tab(
        url: str,
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Open a new tab and navigate to a URL.
        
        Args:
            url: URL to navigate to in the new tab
            base_url: Optional URL to navigate to first in the original tab
            
        Returns:
            Dictionary with tab status
        """
        logger.info(f"Received request to open new tab with URL: {url}")
        result = new_tab(url, base_url)
        return result
    
    @mcp.tool()
    async def robot_browser_select_tab(
        index: int,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Select a tab by index.
        
        Args:
            index: Index of the tab to select (0-based)
            url: Optional URL to navigate to first
            
        Returns:
            Dictionary with tab selection status
        """
        logger.info(f"Received request to select tab at index: {index}")
        result = select_tab(index, url)
        return result
    
    @mcp.tool()
    async def robot_browser_close_tab(
        index: Optional[int] = None,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Close a tab by index or the current tab.
        
        Args:
            index: Index of the tab to close (0-based), or None for current tab
            url: Optional URL to navigate to first
            
        Returns:
            Dictionary with tab close status
        """
        if index is not None:
            logger.info(f"Received request to close tab at index: {index}")
        else:
            logger.info("Received request to close current tab")
        result = close_tab(index, url)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_tabs_script(
        output_file: str,
        url: str,
        browser: str = "Chrome",
        num_tabs: int = 3,
        tab_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for tab management.
        
        Args:
            output_file: File to save the generated script
            url: Base URL to navigate to
            browser: Browser to use (default is Chrome)
            num_tabs: Number of tabs to open
            tab_urls: Optional list of URLs for each tab
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate tab management script with {num_tabs} tabs")
        result = generate_tabs_script(output_file, url, browser, num_tabs, tab_urls)
        return result 