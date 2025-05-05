#!/usr/bin/env python
"""
MCP Tool: Robot Browser Click
Provides functionality to click on web elements using Robot Framework.
"""

import os
import logging
import time
import json
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# Import shared browser manager
from ..robot_browser_manager import BrowserManager

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
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException,
    NoSuchElementException,
    ElementNotInteractableException
)

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_click')

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def parse_locator(locator: str) -> Tuple[str, str]:
    """
    Parse a locator string into its type and value.
    
    Args:
        locator: Locator string (e.g., "xpath=//button", "id=submit")
        
    Returns:
        Tuple of (locator_type, locator_value)
    """
    # Default to XPath if no prefix is given
    if "=" not in locator:
        return By.XPATH, locator
    
    prefix, value = locator.split("=", 1)
    prefix = prefix.lower().strip()
    
    if prefix == "id":
        return By.ID, value
    elif prefix == "name":
        return By.NAME, value
    elif prefix == "class":
        return By.CLASS_NAME, value
    elif prefix == "tag":
        return By.TAG_NAME, value
    elif prefix == "link":
        return By.LINK_TEXT, value
    elif prefix == "partiallink":
        return By.PARTIAL_LINK_TEXT, value
    elif prefix == "css":
        return By.CSS_SELECTOR, value
    elif prefix == "xpath":
        return By.XPATH, value
    else:
        # Default to XPath for unknown prefixes
        return By.XPATH, locator

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def click_element(url: str, element_locator: str, wait_time: int = 10) -> Dict[str, Any]:
    """
    Click on a web element identified by a locator.
    
    Args:
        url: URL of the web page
        element_locator: Locator for the element to click (id=, name=, xpath=, css=)
        wait_time: Time to wait for element to be clickable in seconds
        
    Returns:
        Dictionary with click status and result
    """
    result = {
        "url": url,
        "element_locator": element_locator,
        "status": "success",
        "robot_command": None,
        "error": None
    }
    
    try:
        # Get WebDriver instance from the manager
        driver = BrowserManager.get_driver()
        
        # Navigate to the URL (if the current URL is different or no URL is loaded)
        # This assumes the browser is already open from a previous step
        current_url_before_nav = driver.current_url
        if url != current_url_before_nav:
            logger.info(f"Navigating to URL: {url}")
            driver.set_page_load_timeout(wait_time * 2)
            driver.get(url)
        else:
            logger.info(f"Already at URL: {url}")
        
        # Wait for page to load
        time.sleep(2)
        
        # Parse locator
        by_type, locator_value = parse_locator(element_locator)
        
        # Wait for element to be clickable
        logger.info(f"Waiting for element to be clickable: {element_locator}")
        wait = WebDriverWait(driver, wait_time)
        element = wait.until(EC.element_to_be_clickable((by_type, locator_value)))
        
        # Get element information before clicking
        element_tag = element.tag_name
        element_text = element.text.strip() if element.text else ""
        element_attrs = {}
        for attr in ["id", "name", "class", "href", "type", "value"]:
            try:
                attr_value = element.get_attribute(attr)
                if attr_value:
                    element_attrs[attr] = attr_value
            except:
                pass
                
        # Click the element
        logger.info(f"Clicking element: {element_locator}")
        element.click()
        
        # Wait for potential page load after click
        time.sleep(2)
        
        # Get page title after click
        current_title = driver.title
        current_url = driver.current_url
        
        # Generate Robot Framework command for clicking
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Click Element On Page
    Open Browser    {url}    Chrome
    Maximize Browser Window
    Wait Until Element Is Visible    {element_locator}    timeout={wait_time}s
    Click Element    {element_locator}
"""

        result.update({
            "robot_command": robot_command,
            "element_info": {
                "tag": element_tag,
                "text": element_text,
                "attributes": element_attrs
            },
            "after_click": {
                "title": current_title,
                "url": current_url
            }
        })
        
        return result
    except TimeoutException:
        logger.error(f"Timeout waiting for element: {element_locator}")
        result["status"] = "error"
        result["error"] = f"Timeout after {wait_time} seconds waiting for element to be clickable"
        return result
    except NoSuchElementException:
        logger.error(f"Element not found: {element_locator}")
        result["status"] = "error"
        result["error"] = f"Element not found: {element_locator}"
        return result
    except ElementNotInteractableException:
        logger.error(f"Element not interactable: {element_locator}")
        result["status"] = "error"
        result["error"] = f"Element found but not interactable: {element_locator}"
        return result
    except Exception as e:
        logger.error(f"Error clicking element: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

def generate_click_script(
    url: str,
    element_locator: str,
    output_file: str,
    wait_time: int = 10,
    browser: str = "Chrome",
    verify_navigation: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for clicking an element.
    
    Args:
        url: URL of the web page
        element_locator: Locator for the element to click (id=, name=, xpath=, css=)
        output_file: File to save the generated script
        wait_time: Time to wait for element to be clickable in seconds
        browser: Browser to use (default is Chrome)
        verify_navigation: Whether to verify navigation after clicking
        
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
Documentation     Robot Framework script for clicking element at {url}
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}                  {url}
${{BROWSER}}              {browser}
${{ELEMENT_LOCATOR}}      {element_locator}
${{WAIT_TIME}}            {wait_time}

*** Test Cases ***
Click Element Test
    [Documentation]    Navigate to the URL and click on the specified element
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Element Is Visible    ${{ELEMENT_LOCATOR}}    timeout=${{WAIT_TIME}}s
    Click Element    ${{ELEMENT_LOCATOR}}
"""
        
        if verify_navigation:
            script_content += """    # Verify navigation after click
    Wait Until Page Contains Element    tag:body    timeout=${WAIT_TIME}s
    ${current_url}=    Get Location
    Log    Current URL after click: ${current_url}
"""
        
        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Write to file
        with open(output_file, "w") as file:
            file.write(script_content)
        
        result["script_content"] = script_content
        
        return result
    except Exception as e:
        logger.error(f"Error generating click script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser click tool with MCP."""
    logger.info("Registering Robot Browser Click tool")

    @mcp.tool()
    async def robot_browser_click_element(
        url: str,
        element_locator: str,
        wait_time: int = 10
    ) -> Dict[str, Any]:
        """
        Click on a web element identified by a locator using Robot Framework.
        
        This tool navigates to a URL and clicks on an element identified by the provided
        locator. It returns information about the element and the result of the click.
        
        Args:
            url: URL of the web page
            element_locator: Locator for the element to click (id=, name=, xpath=, css=)
            wait_time: Time to wait for element to be clickable in seconds
            
        Returns:
            Dictionary with click status, element info, and Robot Framework command
        """
        logger.info(f"Received request to click element: {element_locator} on URL: {url}")
        # Call the modified click_element function
        return click_element(url=url, element_locator=element_locator, wait_time=wait_time)
    
    @mcp.tool()
    async def robot_browser_generate_click_script(
        url: str,
        element_locator: str,
        output_file: str,
        wait_time: int = 10,
        browser: str = "Chrome",
        verify_navigation: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for clicking an element.
        
        This tool creates a Robot Framework script that navigates to a URL and
        clicks on an element identified by the provided locator.
        
        Args:
            url: URL of the web page
            element_locator: Locator for the element to click (id=, name=, xpath=, css=)
            output_file: File to save the generated script
            wait_time: Time to wait for element to be clickable in seconds
            browser: Browser to use (default is Chrome)
            verify_navigation: Whether to verify navigation after clicking
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate click script for element: {element_locator} on URL: {url}")
        # Call the existing script generation function (no changes needed here)
        return generate_click_script(
            url=url,
            element_locator=element_locator,
            output_file=output_file,
            wait_time=wait_time,
            browser=browser,
            verify_navigation=verify_navigation
        ) 