#!/usr/bin/env python
"""
MCP Tool: Robot Browser Screenshot
Takes screenshots of web pages for Robot Framework through MCP.
"""

import os
import logging
import json
import base64
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException
)

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_screenshot')

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

def save_base64_to_file(base64_data: str, output_path: str, format_type: str = "png") -> bool:
    """
    Save base64 encoded image to a file.
    
    Args:
        base64_data: Base64 encoded image data
        output_path: Path to save the image
        format_type: Image format type (png, jpg, etc.)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create the directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Decode and save the image
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(base64_data))
            
        return True
    except Exception as e:
        logger.error(f"Error saving base64 to file: {e}")
        return False

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def take_screenshot(
    url: Optional[str] = None,
    element_locator: Optional[str] = None,
    save_path: Optional[str] = None,
    wait_time: int = 5,
    full_page: bool = False,
    format_type: str = "png"
) -> Dict[str, Any]:
    """
    Take a screenshot of a web page or specific element.
    
    Args:
        url: URL to navigate to (optional, if not provided, will use current page)
        element_locator: Locator string for a specific element to screenshot (optional)
        save_path: Path to save the screenshot (optional)
        wait_time: Time to wait for page/element to load in seconds
        full_page: Whether to take a full page screenshot (not just viewport)
        format_type: Image format type (png, jpg)
        
    Returns:
        Dictionary with screenshot data and metadata
    """
    result = {
        "url": url,
        "element_locator": element_locator,
        "save_path": save_path,
        "format_type": format_type,
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
        
        # Wait for page to be fully loaded
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Take screenshot of specific element if requested
        if element_locator:
            logger.info(f"Taking screenshot of element: {element_locator}")
            try:
                # Parse locator
                by_type, by_value = parse_locator(element_locator)
                
                # Wait for element to be present
                element = WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((by_type, by_value))
                )
                
                # Take screenshot of the element
                screenshot = element.screenshot_as_base64
                result["element_screenshot"] = True
                
            except NoSuchElementException:
                result["status"] = "error"
                result["error"] = f"Element not found with locator: {element_locator}"
                return result
            except Exception as e:
                logger.error(f"Error taking element screenshot: {e}")
                result["status"] = "error"
                result["error"] = f"Error taking element screenshot: {str(e)}"
                return result
                
        else:
            # Take screenshot of the entire page
            logger.info("Taking screenshot of the entire page")
            
            if full_page and hasattr(driver, "get_full_page_screenshot_as_base64"):
                # Take full page screenshot if supported
                screenshot = driver.get_full_page_screenshot_as_base64()
                result["full_page_screenshot"] = True
            else:
                # Take regular viewport screenshot
                screenshot = driver.get_screenshot_as_base64()
                result["full_page_screenshot"] = False
        
        # Store screenshot in the result
        result["screenshot"] = screenshot
        
        # Save to file if requested
        if save_path:
            logger.info(f"Saving screenshot to: {save_path}")
            save_success = save_base64_to_file(screenshot, save_path, format_type)
            if save_success:
                result["saved_to_file"] = True
                result["file_path"] = os.path.abspath(save_path)
            else:
                result["saved_to_file"] = False
                result["save_error"] = "Failed to save screenshot to file"
        
        # Generate Robot Framework command
        if element_locator:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Take Element Screenshot
    Open Browser    {url}    Chrome
    Maximize Browser Window
    Wait Until Element Is Visible    {element_locator}    timeout={wait_time}s
    Capture Element Screenshot    {element_locator}    {save_path or "screenshot.png"}
    Close Browser
"""
        else:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Take Page Screenshot
    Open Browser    {url}    Chrome
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout={wait_time}s
    Capture Page Screenshot    {save_path or "screenshot.png"}
    Close Browser
"""

        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error taking screenshot: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_screenshot_script(
    url: str,
    output_file: str,
    screenshot_path: str,
    element_locator: Optional[str] = None,
    browser: str = "Chrome",
    include_verification: bool = False
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for taking a screenshot.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        screenshot_path: Path to save the screenshot
        element_locator: Locator string for a specific element to screenshot (optional)
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
Documentation     Robot Framework script for taking a {"element" if element_locator else "page"} screenshot
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}                 {url}
${{BROWSER}}             {browser}
${{SCREENSHOT_PATH}}     {screenshot_path}
"""

        if element_locator:
            script_content += f"${{ELEMENT_LOCATOR}}     {element_locator}\n"

        script_content += """
*** Test Cases ***
"""
        
        if element_locator:
            script_content += f"""Take Element Screenshot
    [Documentation]    Navigate to the specified URL and take a screenshot of a specific element
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    
    # Wait for element to be ready
    Wait Until Element Is Visible    ${{ELEMENT_LOCATOR}}    timeout=10s
    
    # Take screenshot of the element
    Capture Element Screenshot    ${{ELEMENT_LOCATOR}}    ${{SCREENSHOT_PATH}}
"""
        else:
            script_content += f"""Take Page Screenshot
    [Documentation]    Navigate to the specified URL and take a page screenshot
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    
    # Wait for page to be loaded
    Wait Until Page Contains Element    tag:body    timeout=10s
    
    # Take screenshot of the entire page
    Capture Page Screenshot    ${{SCREENSHOT_PATH}}
"""

        if include_verification:
            script_content += """    
    # Add verification steps here to verify screenshot was taken
    # This is a placeholder as Robot Framework doesn't have built-in
    # methods to verify screenshot content, but you could check
    # for file existence in a custom keyword
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
        logger.error(f"Error generating screenshot script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register MCP tool."""
    
    @mcp.tool()
    async def robot_browser_screenshot(
        url: Optional[str] = None,
        element_locator: Optional[str] = None,
        save_path: Optional[str] = None,
        wait_time: int = 5,
        full_page: bool = False,
        format_type: str = "png"
    ) -> Dict[str, Any]:
        """
        Take a screenshot of a web page or specific element.
        
        This tool captures a screenshot of a web page or a specific element
        and returns it as a base64 encoded string.
        
        Args:
            url: URL to navigate to (optional, if not provided, will use current page)
            element_locator: Locator string for a specific element to screenshot (optional)
            save_path: Path to save the screenshot (optional)
            wait_time: Time to wait for page/element to load in seconds
            full_page: Whether to take a full page screenshot (not just viewport)
            format_type: Image format type (png, jpg)
            
        Returns:
            Dictionary with screenshot data and metadata
        """
        return take_screenshot(
            url,
            element_locator,
            save_path,
            wait_time,
            full_page,
            format_type
        )
    
    @mcp.tool()
    async def robot_browser_generate_screenshot_script(
        url: str,
        output_file: str,
        screenshot_path: str,
        element_locator: Optional[str] = None,
        browser: str = "Chrome",
        include_verification: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for taking a screenshot.
        
        This tool generates a Robot Framework script that navigates to a URL
        and takes a screenshot of the page or a specific element.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            screenshot_path: Path to save the screenshot
            element_locator: Locator string for a specific element to screenshot (optional)
            browser: Browser to use (default is Chrome)
            include_verification: Whether to include verification steps
            
        Returns:
            Dictionary with generation status and file path
        """
        return generate_screenshot_script(
            url,
            output_file,
            screenshot_path,
            element_locator,
            browser,
            include_verification
        ) 