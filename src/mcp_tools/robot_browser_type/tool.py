#!/usr/bin/env python
"""
MCP Tool: Robot Browser Type
Types text into editable elements on a web page for Robot Framework through MCP.
"""

import os
import logging
import json
import time
from typing import Dict, Any, Optional, Tuple
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
from selenium.webdriver.common.keys import Keys
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

logger = logging.getLogger('robot_tool.browser_type')

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

def type_text(
    element_locator: str,
    text: str,
    url: Optional[str] = None,
    wait_time: int = 5,
    clear_first: bool = True,
    submit: bool = False,
    type_slowly: bool = False,
    delay_between_chars: float = 0.1
) -> Dict[str, Any]:
    """
    Type text into an editable element on a web page.
    
    Args:
        element_locator: Locator string for the element to type into
        text: Text to type into the element
        url: URL to navigate to (optional, if not provided, will use current page)
        wait_time: Time to wait for element to be available in seconds
        clear_first: Whether to clear the field before typing
        submit: Whether to submit the form after typing (press Enter)
        type_slowly: Whether to type one character at a time
        delay_between_chars: Delay between characters when typing slowly
        
    Returns:
        Dictionary with the typing operation result
    """
    result = {
        "element_locator": element_locator,
        "text": text,
        "url": url,
        "status": "success",
        "error": None
    }
    
    try:
        # Get WebDriver instance from the manager
        driver = BrowserManager.get_driver()
        
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
        
        # Parse locator
        by_type, by_value = parse_locator(element_locator)
        
        # Wait for element to be present and interactable
        logger.info(f"Waiting for element: {element_locator}")
        try:
            element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable((by_type, by_value))
            )
        except TimeoutException:
            result["status"] = "error"
            result["error"] = f"Element not found or not interactable with locator: {element_locator}"
            return result
        
        # Perform typing operation
        logger.info(f"Typing '{text}' into element: {element_locator}")
        try:
            # Get element type
            element_type = element.get_attribute("type")
            element_tag = element.tag_name.lower()
            result["element_type"] = element_type
            result["element_tag"] = element_tag
            
            # Clear field if requested
            if clear_first:
                element.clear()
            
            # Type the text
            if type_slowly:
                for char in text:
                    element.send_keys(char)
                    time.sleep(delay_between_chars)
            else:
                element.send_keys(text)
            
            # Submit if requested
            if submit:
                if element_tag == "input" and element_type in ["text", "password", "email", "search", "tel", "url"]:
                    # For input fields, press Enter
                    element.send_keys(Keys.ENTER)
                elif element_tag == "form":
                    # For form elements, submit the form
                    element.submit()
                else:
                    # Try pressing Enter as a fallback
                    element.send_keys(Keys.ENTER)
                    
                # Add brief delay to allow submission to complete
                time.sleep(1)
                
                # Update URL after submit
                result["current_url"] = driver.current_url
                
            # Capture the actual value after typing
            result["actual_value"] = element.get_attribute("value")
                
        except ElementNotInteractableException:
            result["status"] = "error"
            result["error"] = "Element not interactable for typing"
            return result
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Error typing into element: {str(e)}"
            return result
        
        # Generate Robot Framework command for typing
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Type Text Into Element
    Open Browser    {url}    Chrome
    Maximize Browser Window
    Wait Until Element Is Visible    {element_locator}    timeout={wait_time}s
"""
        if clear_first:
            robot_command += f"    Clear Element Text    {element_locator}\n"
            
        robot_command += f"    Input Text    {element_locator}    {text}\n"
        
        if submit:
            robot_command += f"    Press Keys    {element_locator}    RETURN\n"
            
        robot_command += "    Close Browser\n"

        result["robot_command"] = robot_command
        
        return result
    except WebDriverException as e:
        result["status"] = "error"
        result["error"] = f"WebDriver error during typing: {e}"
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"An unexpected error occurred: {e}"
    return result

def generate_typing_script(
    url: str,
    output_file: str,
    element_locator: str,
    text: str,
    browser: str = "Chrome",
    clear_first: bool = True,
    submit: bool = False,
    include_verification: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for typing text into an element.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        element_locator: Locator string for the element to type into
        text: Text to type into the element
        browser: Browser to use (default is Chrome)
        clear_first: Whether to clear the field before typing
        submit: Whether to submit the form after typing
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
Documentation     Robot Framework script for typing text into a field
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}                 {url}
${{BROWSER}}             {browser}
${{ELEMENT_LOCATOR}}     {element_locator}
${{TEXT_TO_TYPE}}        {text}

*** Test Cases ***
Type Text Into Element
    [Documentation]    Types text into an element on a web page
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    
    # Wait for element to be ready
    Wait Until Element Is Visible    ${{ELEMENT_LOCATOR}}    timeout=10s
"""
        if clear_first:
            script_content += """    
    # Clear existing text
    Clear Element Text    ${ELEMENT_LOCATOR}
"""
        
        script_content += """    
    # Type the text
    Input Text    ${ELEMENT_LOCATOR}    ${TEXT_TO_TYPE}
"""

        if submit:
            script_content += """    
    # Submit the form
    Press Keys    ${ELEMENT_LOCATOR}    RETURN
    
    # Wait briefly for form submission
    Sleep    1s
"""

        if include_verification:
            script_content += """    
    # Add verification steps here based on your application's behavior
    # For example:
    # ${value}=    Get Element Attribute    ${ELEMENT_LOCATOR}    value
    # Should Be Equal    ${value}    ${TEXT_TO_TYPE}
    # Page Should Contain    Success
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
        result["status"] = "error"
        result["error"] = f"Failed to generate script: {e}"
        
    return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser typing tool with MCP."""
    logger.info("Registering Robot Browser Type tool")
    
    @mcp.tool()
    async def robot_browser_type(
        element_locator: str,
        text: str,
        url: Optional[str] = None,
        wait_time: int = 5,
        clear_first: bool = True,
        submit: bool = False,
        type_slowly: bool = False,
        delay_between_chars: float = 0.1
    ) -> Dict[str, Any]:
        """
        Type text into an editable element on a web page.
        
        This tool types text into an editable element such as an input field,
        textarea, or contenteditable div.
        
        Args:
            element_locator: Locator string for the element to type into (e.g., "id=username")
            text: Text to type into the element
            url: URL to navigate to (optional, if not provided, will use current page)
            wait_time: Time to wait for element to be available in seconds
            clear_first: Whether to clear the field before typing
            submit: Whether to submit the form after typing (press Enter)
            type_slowly: Whether to type one character at a time
            delay_between_chars: Delay between characters when typing slowly
            
        Returns:
            Dictionary with the typing operation result
        """
        return type_text(
            element_locator,
            text,
            url,
            wait_time,
            clear_first,
            submit,
            type_slowly,
            delay_between_chars
        )
    
    @mcp.tool()
    async def robot_browser_generate_typing_script(
        url: str,
        output_file: str,
        element_locator: str,
        text: str,
        browser: str = "Chrome",
        clear_first: bool = True,
        submit: bool = False,
        include_verification: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for typing text into an element.
        
        This tool generates a Robot Framework script that navigates to a URL
        and types text into a specified element.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            element_locator: Locator string for the element to type into
            text: Text to type into the element
            browser: Browser to use (default is Chrome)
            clear_first: Whether to clear the field before typing
            submit: Whether to submit the form after typing
            include_verification: Whether to include verification steps
            
        Returns:
            Dictionary with generation status and file path
        """
        return generate_typing_script(
            url,
            output_file,
            element_locator,
            text,
            browser,
            clear_first,
            submit,
            include_verification
        ) 