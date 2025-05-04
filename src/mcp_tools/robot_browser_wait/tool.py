#!/usr/bin/env python
"""
MCP Tool: Robot Browser Wait
Provides browser waiting functionality for Robot Framework through MCP.
"""

import os
import logging
import time
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException, 
    NoSuchElementException,
    StaleElementReferenceException
)

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_wait')

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

def wait_for_element(
    url: str,
    element_locator: str,
    wait_type: str = "visible",
    wait_time: int = 10,
    poll_frequency: float = 0.5
) -> Dict[str, Any]:
    """
    Wait for an element to be present, visible, clickable, or disappear.
    
    Args:
        url: URL to navigate to
        element_locator: Locator string for the element to wait for
        wait_type: Type of wait ('present', 'visible', 'clickable', 'invisible')
        wait_time: Maximum time to wait in seconds
        poll_frequency: How often to check for the element in seconds
        
    Returns:
        Dictionary with wait status and element info
    """
    result = {
        "url": url,
        "element_locator": element_locator,
        "wait_type": wait_type,
        "wait_time": wait_time,
        "poll_frequency": poll_frequency,
        "status": "success",
        "element_found": False,
        "time_elapsed": None,
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
            
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(url)
        
        # Parse locator
        by_type, locator_value = parse_locator(element_locator)
        
        # Set up expected condition based on wait type
        if wait_type.lower() == "present":
            condition = EC.presence_of_element_located((by_type, locator_value))
        elif wait_type.lower() == "clickable":
            condition = EC.element_to_be_clickable((by_type, locator_value))
        elif wait_type.lower() == "invisible":
            condition = EC.invisibility_of_element_located((by_type, locator_value))
        else:  # default to visible
            condition = EC.visibility_of_element_located((by_type, locator_value))
        
        # Create a WebDriverWait instance
        wait = WebDriverWait(
            driver, 
            wait_time, 
            poll_frequency=poll_frequency,
            ignored_exceptions=(NoSuchElementException, StaleElementReferenceException)
        )
        
        # Start timing
        start_time = time.time()
        
        try:
            # Wait for the condition
            logger.info(f"Waiting for element '{element_locator}' to be {wait_type}")
            element = wait.until(condition)
            
            result["element_found"] = True
            
            # Get element information if found (except for "invisible" wait type)
            if wait_type.lower() != "invisible" and element:
                result["element_info"] = {
                    "tag_name": element.tag_name
                }
                
                # Get basic attributes
                attrs = {}
                for attr in ["id", "name", "class", "href", "value", "type"]:
                    try:
                        attr_value = element.get_attribute(attr)
                        if attr_value:
                            attrs[attr] = attr_value
                    except:
                        pass
                
                result["element_info"]["attributes"] = attrs
                
                # Get element location and size
                try:
                    location = element.location
                    size = element.size
                    result["element_info"]["location"] = location
                    result["element_info"]["size"] = size
                except:
                    pass
                
        except TimeoutException:
            result["status"] = "warning"
            result["element_found"] = False
            result["error"] = f"Timeout waiting for element '{element_locator}' to be {wait_type} after {wait_time} seconds"
        
        # Calculate elapsed time
        end_time = time.time()
        result["time_elapsed"] = round(end_time - start_time, 2)
        
        # Generate Robot Framework command
        if wait_type.lower() == "present":
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Wait For Element Present
    [Arguments]    ${{url}}    ${{locator}}
    Open Browser    ${{url}}    Chrome
    Wait Until Page Contains Element    {element_locator}    timeout={wait_time}s
"""
        elif wait_type.lower() == "clickable":
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Wait For Element Clickable
    [Arguments]    ${{url}}    ${{locator}}
    Open Browser    ${{url}}    Chrome
    Wait Until Element Is Enabled    {element_locator}    timeout={wait_time}s
"""
        elif wait_type.lower() == "invisible":
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Wait For Element Invisible
    [Arguments]    ${{url}}    ${{locator}}
    Open Browser    ${{url}}    Chrome
    Wait Until Element Is Not Visible    {element_locator}    timeout={wait_time}s
"""
        else:  # default to visible
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Wait For Element Visible
    [Arguments]    ${{url}}    ${{locator}}
    Open Browser    ${{url}}    Chrome
    Wait Until Element Is Visible    {element_locator}    timeout={wait_time}s
"""
        
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error while waiting for element: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def wait_fixed_time(
    url: Optional[str],
    wait_time: float
) -> Dict[str, Any]:
    """
    Wait for a fixed amount of time.
    
    Args:
        url: Optional URL to navigate to
        wait_time: Time to wait in seconds
        
    Returns:
        Dictionary with wait status
    """
    result = {
        "url": url,
        "wait_time": wait_time,
        "status": "success",
        "robot_command": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize WebDriver if URL is provided
        if url:
            driver = initialize_webdriver()
            if not driver:
                result["status"] = "error"
                result["error"] = "Failed to initialize WebDriver"
                return result
                
            # Navigate to the URL
            logger.info(f"Navigating to URL: {url}")
            driver.get(url)
        
        # Wait for the specified time
        logger.info(f"Waiting for {wait_time} seconds")
        time.sleep(wait_time)
        
        # Generate Robot Framework command
        if url:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Wait Fixed Time
    [Arguments]    ${{url}}    ${{wait_time}}
    Open Browser    ${{url}}    Chrome
    Sleep    {wait_time}s
"""
        else:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Wait Fixed Time
    [Arguments]    ${{wait_time}}
    Sleep    {wait_time}s
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error during fixed wait: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_wait_script(
    output_file: str,
    url: str,
    browser: str = "Chrome",
    element_locator: Optional[str] = None,
    wait_type: str = "visible",
    wait_time: float = 10,
    poll_frequency: float = 0.5,
    fixed_wait: bool = False
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for waiting.
    
    Args:
        output_file: File to save the generated script
        url: URL to navigate to
        browser: Browser to use (default is Chrome)
        element_locator: Locator string for the element to wait for
        wait_type: Type of wait ('present', 'visible', 'clickable', 'invisible')
        wait_time: Maximum time to wait in seconds
        poll_frequency: How often to check for the element in seconds
        fixed_wait: Whether to use a fixed wait time instead of element wait
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Generate the script differently based on wait type
        if fixed_wait:
            script_content = f"""*** Settings ***
Documentation     Robot Framework script for waiting a fixed amount of time
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
${{WAIT_TIME}}    {wait_time}

*** Test Cases ***
Wait Fixed Time
    [Documentation]    Navigate to a URL and wait for a fixed amount of time
    
    # Open browser and navigate to URL
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    
    # Wait for the specified time
    Sleep    ${{WAIT_TIME}}s
    
    Log    Waited for ${{WAIT_TIME}} seconds
"""
        else:
            # Map wait type to Robot Framework keyword
            if wait_type.lower() == "present":
                robot_wait_keyword = "Wait Until Page Contains Element"
            elif wait_type.lower() == "clickable":
                robot_wait_keyword = "Wait Until Element Is Enabled"
            elif wait_type.lower() == "invisible":
                robot_wait_keyword = "Wait Until Element Is Not Visible"
            else:  # default to visible
                robot_wait_keyword = "Wait Until Element Is Visible"
            
            script_content = f"""*** Settings ***
Documentation     Robot Framework script for waiting for an element
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
${{LOCATOR}}      {element_locator or "xpath=//body"}
${{WAIT_TIME}}    {wait_time}

*** Test Cases ***
Wait For Element
    [Documentation]    Navigate to a URL and wait for an element to be {wait_type}
    
    # Open browser and navigate to URL
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    
    # Wait for the element with the specified condition
    {robot_wait_keyword}    ${{LOCATOR}}    timeout=${{WAIT_TIME}}s
    
    # Log success
    Run Keyword If    "{wait_type.lower()}" != "invisible"    Log Element Status    ${{LOCATOR}}
    
*** Keywords ***
Log Element Status
    [Arguments]    ${{locator}}
    ${{\$tag}}=    Get Element Attribute    ${{locator}}    tagName
    ${{\$text}}=    Get Text    ${{locator}}
    Log    Element ${{locator}} is a ${{\\$tag}} element with text: ${{\\$text}}
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
        logger.error(f"Error generating wait script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser wait tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_wait_for_element(
        url: str,
        element_locator: str,
        wait_type: str = "visible",
        wait_time: int = 10,
        poll_frequency: float = 0.5
    ) -> Dict[str, Any]:
        """
        Wait for an element to be present, visible, clickable, or disappear.
        
        Args:
            url: URL to navigate to
            element_locator: Locator string for the element to wait for
            wait_type: Type of wait ('present', 'visible', 'clickable', 'invisible')
            wait_time: Maximum time to wait in seconds
            poll_frequency: How often to check for the element in seconds
            
        Returns:
            Dictionary with wait status and element info
        """
        logger.info(f"Received request to wait for element '{element_locator}' to be {wait_type}")
        result = wait_for_element(url, element_locator, wait_type, wait_time, poll_frequency)
        return result
    
    @mcp.tool()
    async def robot_browser_wait_fixed_time(
        wait_time: float,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Wait for a fixed amount of time.
        
        Args:
            wait_time: Time to wait in seconds
            url: Optional URL to navigate to
            
        Returns:
            Dictionary with wait status
        """
        logger.info(f"Received request to wait for {wait_time} seconds")
        result = wait_fixed_time(url, wait_time)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_wait_script(
        output_file: str,
        url: str,
        browser: str = "Chrome",
        element_locator: Optional[str] = None,
        wait_type: str = "visible",
        wait_time: float = 10,
        poll_frequency: float = 0.5,
        fixed_wait: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for waiting.
        
        Args:
            output_file: File to save the generated script
            url: URL to navigate to
            browser: Browser to use (default is Chrome)
            element_locator: Locator string for the element to wait for
            wait_type: Type of wait ('present', 'visible', 'clickable', 'invisible')
            wait_time: Maximum time to wait in seconds
            poll_frequency: How often to check for the element in seconds
            fixed_wait: Whether to use a fixed wait time instead of element wait
            
        Returns:
            Dictionary with generation status and file path
        """
        wait_description = f"fixed time of {wait_time}s" if fixed_wait else f"element '{element_locator}' to be {wait_type}"
        logger.info(f"Received request to generate wait script for {wait_description}")
        result = generate_wait_script(output_file, url, browser, element_locator, wait_type, wait_time, poll_frequency, fixed_wait)
        return result 