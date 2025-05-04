#!/usr/bin/env python
"""
MCP Tool: Robot Browser Drag
Performs drag and drop between elements on a web page for Robot Framework through MCP.
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
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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

logger = logging.getLogger('robot_tool.browser_drag')

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

def drag_and_drop(
    start_locator: str,
    end_locator: str,
    url: Optional[str] = None,
    wait_time: int = 5
) -> Dict[str, Any]:
    """
    Perform drag and drop operation from one element to another.
    
    Args:
        start_locator: Locator string for the source element
        end_locator: Locator string for the target element
        url: URL to navigate to (optional, if not provided, will use current page)
        wait_time: Time to wait for elements to be available in seconds
        
    Returns:
        Dictionary with the drag operation result
    """
    result = {
        "start_locator": start_locator,
        "end_locator": end_locator,
        "url": url,
        "status": "success",
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
            driver.set_page_load_timeout(wait_time * 2)
            try:
                driver.get(url)
            except TimeoutException:
                result["status"] = "error"
                result["error"] = f"Timeout after {wait_time*2} seconds while loading {url}"
                return result
            
            # Get page metadata
            result["url"] = driver.current_url
            result["title"] = driver.title
        
        # Parse locators
        start_by, start_value = parse_locator(start_locator)
        end_by, end_value = parse_locator(end_locator)
        
        # Wait for source element to be present
        logger.info(f"Waiting for source element: {start_locator}")
        try:
            source_element = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((start_by, start_value))
            )
        except TimeoutException:
            result["status"] = "error"
            result["error"] = f"Source element not found with locator: {start_locator}"
            return result
        
        # Wait for target element to be present
        logger.info(f"Waiting for target element: {end_locator}")
        try:
            target_element = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((end_by, end_value))
            )
        except TimeoutException:
            result["status"] = "error"
            result["error"] = f"Target element not found with locator: {end_locator}"
            return result
        
        # Perform drag and drop operation
        logger.info(f"Performing drag and drop from {start_locator} to {end_locator}")
        try:
            actions = ActionChains(driver)
            
            # Try multiple drag and drop methods
            try:
                # Method 1: Classic drag and drop
                actions.drag_and_drop(source_element, target_element).perform()
            except Exception as e:
                logger.warning(f"Classic drag and drop failed: {e}. Trying alternative method.")
                
                # Method 2: Click and hold, move, release
                actions.click_and_hold(source_element)\
                       .pause(0.5)\
                       .move_to_element(target_element)\
                       .pause(0.5)\
                       .release()\
                       .perform()
                       
            # Add success details
            source_text = source_element.text.strip() if source_element.text else "[No text]"
            target_text = target_element.text.strip() if target_element.text else "[No text]"
            
            result["source_element_text"] = source_text
            result["target_element_text"] = target_text
            result["source_element_tag"] = source_element.tag_name
            result["target_element_tag"] = target_element.tag_name
            
        except ElementNotInteractableException:
            result["status"] = "error"
            result["error"] = "Element not interactable for drag and drop"
            return result
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Error performing drag and drop: {str(e)}"
            return result
        
        # Generate Robot Framework command for drag and drop
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Perform Drag And Drop
    Open Browser    {url}    Chrome
    Maximize Browser Window
    Wait Until Element Is Visible    {start_locator}    timeout={wait_time}s
    Wait Until Element Is Visible    {end_locator}    timeout={wait_time}s
    Drag And Drop    {start_locator}    {end_locator}
    Close Browser
"""

        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error during drag and drop operation: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_drag_drop_script(
    url: str,
    output_file: str,
    start_locator: str,
    end_locator: str,
    browser: str = "Chrome",
    include_verification: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for drag and drop operation.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        start_locator: Locator string for source element
        end_locator: Locator string for target element
        browser: Browser to use (default is Chrome)
        include_verification: Whether to include verification steps
        
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
Documentation     Robot Framework script for drag and drop operation
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}                 {url}
${{BROWSER}}             {browser}
${{SOURCE_LOCATOR}}      {start_locator}
${{TARGET_LOCATOR}}      {end_locator}

*** Test Cases ***
Perform Drag And Drop Operation
    [Documentation]    Performs drag and drop from one element to another
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    
    # Wait for elements to be ready
    Wait Until Element Is Visible    ${{SOURCE_LOCATOR}}    timeout=10s
    Wait Until Element Is Visible    ${{TARGET_LOCATOR}}    timeout=10s
    
    # Perform drag and drop
    Drag And Drop    ${{SOURCE_LOCATOR}}    ${{TARGET_LOCATOR}}
"""

        if include_verification:
            script_content += """    
    # Add verification steps here based on your application's behavior
    # For example:
    # Wait Until Element Contains    result_element    Successfully moved
    # Element Should Be Visible      completion_indicator
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
        logger.error(f"Error generating drag and drop script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register MCP tool."""
    
    @mcp.tool()
    async def robot_browser_drag(
        start_locator: str,
        end_locator: str,
        url: Optional[str] = None,
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Perform drag and drop operation from one element to another.
        
        This tool performs a drag and drop operation from a source element to a target element
        on a web page using provided locators.
        
        Args:
            start_locator: Locator string for the source element (e.g., "xpath=//div[@id='draggable']")
            end_locator: Locator string for the target element (e.g., "id=droppable")
            url: URL to navigate to (optional, if not provided, will use current page)
            wait_time: Time to wait for elements to be available in seconds
            
        Returns:
            Dictionary with the drag operation result
        """
        return drag_and_drop(start_locator, end_locator, url, wait_time)
    
    @mcp.tool()
    async def robot_browser_generate_drag_drop_script(
        url: str,
        output_file: str,
        start_locator: str,
        end_locator: str,
        browser: str = "Chrome",
        include_verification: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for drag and drop operation.
        
        This tool generates a Robot Framework script that navigates to a URL
        and performs a drag and drop operation between specified elements.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            start_locator: Locator string for source element
            end_locator: Locator string for target element
            browser: Browser to use (default is Chrome)
            include_verification: Whether to include verification steps
            
        Returns:
            Dictionary with generation status and file path
        """
        return generate_drag_drop_script(
            url, 
            output_file, 
            start_locator, 
            end_locator, 
            browser, 
            include_verification
        ) 