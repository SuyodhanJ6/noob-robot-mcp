#!/usr/bin/env python
"""
MCP Tool: Robot Browser Press Key
Provides keyboard key pressing functionality for Robot Framework through MCP.
"""

import os
import logging
import time
import json
from typing import Dict, Any, Optional, List, Tuple
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
from selenium.webdriver.common.keys import Keys
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

logger = logging.getLogger('robot_tool.browser_press_key')

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

def get_key_attribute(key: str) -> Any:
    """
    Get the key attribute from the Keys class.
    
    Args:
        key: Key name (e.g., "ENTER", "TAB", "a")
        
    Returns:
        Key attribute or the key itself if not found
    """
    # Special keys dictionary for commonly used keys
    special_keys = {
        "enter": Keys.ENTER,
        "tab": Keys.TAB,
        "space": Keys.SPACE,
        "escape": Keys.ESCAPE,
        "esc": Keys.ESCAPE,
        "backspace": Keys.BACKSPACE,
        "delete": Keys.DELETE,
        "up": Keys.UP,
        "down": Keys.DOWN,
        "left": Keys.LEFT,
        "right": Keys.RIGHT,
        "pageup": Keys.PAGE_UP,
        "pagedown": Keys.PAGE_DOWN,
        "home": Keys.HOME,
        "end": Keys.END,
        "f1": Keys.F1,
        "f2": Keys.F2,
        "f3": Keys.F3,
        "f4": Keys.F4,
        "f5": Keys.F5,
        "f6": Keys.F6,
        "f7": Keys.F7,
        "f8": Keys.F8,
        "f9": Keys.F9,
        "f10": Keys.F10,
        "f11": Keys.F11,
        "f12": Keys.F12,
        "control": Keys.CONTROL,
        "ctrl": Keys.CONTROL,
        "alt": Keys.ALT,
        "shift": Keys.SHIFT,
        "command": Keys.COMMAND,
        "cmd": Keys.COMMAND,
        "return": Keys.RETURN
    }
    
    # Check if the key is a special key
    key_lower = key.lower()
    if key_lower in special_keys:
        return special_keys[key_lower]
    
    # For single character keys, return the key itself
    return key

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def press_key(
    url: str,
    key: str,
    element_locator: Optional[str] = None,
    wait_time: int = 10,
    modifiers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Press a key on the keyboard, optionally on a specific element.
    
    Args:
        url: URL to navigate to
        key: Key to press (e.g., "ENTER", "TAB", "a")
        element_locator: Locator for the element to focus on (optional)
        wait_time: Time to wait for element to be clickable in seconds
        modifiers: List of modifier keys to press (e.g., ["CONTROL", "SHIFT"])
        
    Returns:
        Dictionary with status
    """
    result = {
        "url": url,
        "key": key,
        "element_locator": element_locator,
        "modifiers": modifiers,
        "status": "success",
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
        
        # Wait for page to load
        time.sleep(2)
        
        # Get key to press
        key_to_press = get_key_attribute(key)
        
        # Get modifier keys (if any)
        modifier_keys = []
        if modifiers:
            for mod in modifiers:
                modifier_key = get_key_attribute(mod)
                if modifier_key:
                    modifier_keys.append(modifier_key)
        
        # Create action chains instance
        actions = ActionChains(driver)
        
        # Focus on element if specified
        if element_locator:
            try:
                # Parse locator
                by_type, locator_value = parse_locator(element_locator)
                
                # Wait for element to be clickable
                logger.info(f"Waiting for element to be clickable: {element_locator}")
                wait = WebDriverWait(driver, wait_time)
                element = wait.until(EC.element_to_be_clickable((by_type, locator_value)))
                
                # Focus on the element
                element.click()
                
                # Get element information
                element_tag = element.tag_name
                element_attrs = {}
                for attr in ["id", "name", "class", "type"]:
                    try:
                        attr_value = element.get_attribute(attr)
                        if attr_value:
                            element_attrs[attr] = attr_value
                    except:
                        pass
                
                result["element_info"] = {
                    "tag": element_tag,
                    "attributes": element_attrs
                }
                
            except NoSuchElementException:
                result["status"] = "error"
                result["error"] = f"Element not found with locator: {element_locator}"
                return result
            except ElementNotInteractableException:
                result["status"] = "error"
                result["error"] = f"Element not interactable with locator: {element_locator}"
                return result
        
        # Press modifier keys if any
        for mod_key in modifier_keys:
            actions = actions.key_down(mod_key)
        
        # Press the key
        logger.info(f"Pressing key: {key}")
        actions = actions.send_keys(key_to_press)
        
        # Release modifier keys if any
        for mod_key in modifier_keys:
            actions = actions.key_up(mod_key)
        
        # Perform the action
        actions.perform()
        
        # Wait a moment for key press to take effect
        time.sleep(0.5)
        
        # Generate Robot Framework command
        robot_key = key.upper() if len(key) > 1 else key
        
        if element_locator:
            if modifiers:
                robot_modifiers = " ".join([m.upper() for m in modifiers])
                robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Press Key With Modifiers
    [Arguments]    ${{url}}    ${{locator}}    ${{key}}    ${{modifiers}}
    Open Browser    ${{url}}    Chrome
    Wait Until Element Is Enabled    {element_locator}    timeout={wait_time}
    Press Keys    {element_locator}    {robot_modifiers}+{robot_key}
"""
            else:
                robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Press Key On Element
    [Arguments]    ${{url}}    ${{locator}}    ${{key}}
    Open Browser    ${{url}}    Chrome
    Wait Until Element Is Enabled    {element_locator}    timeout={wait_time}
    Press Keys    {element_locator}    {robot_key}
"""
        else:
            if modifiers:
                robot_modifiers = " ".join([m.upper() for m in modifiers])
                robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Press Key With Modifiers
    [Arguments]    ${{url}}    ${{key}}    ${{modifiers}}
    Open Browser    ${{url}}    Chrome
    Wait Until Page Contains Element    tag:body    timeout={wait_time}
    Press Keys    None    {robot_modifiers}+{robot_key}
"""
            else:
                robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Press Key
    [Arguments]    ${{url}}    ${{key}}
    Open Browser    ${{url}}    Chrome
    Wait Until Page Contains Element    tag:body    timeout={wait_time}
    Press Keys    None    {robot_key}
"""
        
        result["robot_command"] = robot_command
        
        return result
    except TimeoutException:
        logger.error(f"Timeout while loading URL: {url}")
        result["status"] = "error"
        result["error"] = f"Timeout after {wait_time*2} seconds"
        return result
    except Exception as e:
        logger.error(f"Error pressing key: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_key_press_script(
    url: str, 
    output_file: str,
    key: str,
    element_locator: Optional[str] = None,
    modifiers: Optional[List[str]] = None,
    browser: str = "Chrome",
    wait_time: int = 10,
    verify_result: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for pressing keys.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        key: Key to press (e.g., "ENTER", "TAB", "a")
        element_locator: Locator for the element to focus on (optional)
        modifiers: List of modifier keys to press (e.g., ["CONTROL", "SHIFT"])
        browser: Browser to use (default is Chrome)
        wait_time: Time to wait for page/element to load in seconds
        verify_result: Whether to include verification steps
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Prepare Robot Framework key press command
        robot_key = key.upper() if len(key) > 1 else key
        
        # Format modifiers if provided
        modifier_text = ""
        robot_key_cmd = robot_key
        
        if modifiers and len(modifiers) > 0:
            robot_modifiers = "+".join([m.upper() for m in modifiers])
            robot_key_cmd = f"{robot_modifiers}+{robot_key}"
            modifier_text = f" with modifiers {robot_modifiers}"
        
        # Generate appropriate description based on whether we have an element or not
        if element_locator:
            action_desc = f"Press {robot_key_cmd} on element {element_locator}"
        else:
            action_desc = f"Press {robot_key_cmd} on the page"
        
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for pressing keys{modifier_text}
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
${{WAIT_TIME}}    {wait_time}
${{KEY}}          {robot_key}

*** Test Cases ***
Press Key Test
    [Documentation]    {action_desc}
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
"""
        
        # Add element focus if specified
        if element_locator:
            script_content += f"""    
    # Wait for element to be ready
    Wait Until Element Is Enabled    {element_locator}    timeout=${{WAIT_TIME}}s
    
    # Focus on the element
    Click Element    {element_locator}
    
"""
        
        # Add key press command
        script_content += f"""    # Press the key{modifier_text}
    Press Keys    {'None' if not element_locator else element_locator}    {robot_key_cmd}
    
"""
        
        # Add verification if requested
        if verify_result:
            script_content += """    # Add verification steps here based on the expected behavior after key press
    # For example:
    # - Check if a specific element appears after pressing Enter on a form
    # - Check if a character appears in an input field
    # - Check if navigation occurred
    Sleep    1s    # Wait for any actions triggered by the key press
    
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
        logger.error(f"Error generating key press script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser press key tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_press_key(
        url: str,
        key: str,
        element_locator: Optional[str] = None,
        wait_time: int = 10,
        modifiers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Press a key on the keyboard, optionally on a specific element.
        
        Args:
            url: URL to navigate to
            key: Key to press (e.g., "ENTER", "TAB", "a")
            element_locator: Locator for the element to focus on (optional)
            wait_time: Time to wait for element to be clickable in seconds
            modifiers: List of modifier keys to press (e.g., ["CONTROL", "SHIFT"])
            
        Returns:
            Dictionary with status
        """
        logger.info(f"Received request to press key {key} at URL: {url}")
        result = press_key(url, key, element_locator, wait_time, modifiers)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_key_press_script(
        url: str,
        output_file: str,
        key: str,
        element_locator: Optional[str] = None,
        modifiers: Optional[List[str]] = None,
        browser: str = "Chrome",
        wait_time: int = 10,
        verify_result: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for pressing keys.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            key: Key to press (e.g., "ENTER", "TAB", "a")
            element_locator: Locator for the element to focus on (optional)
            modifiers: List of modifier keys to press (e.g., ["CONTROL", "SHIFT"])
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for page/element to load in seconds
            verify_result: Whether to include verification steps
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate key press script for key {key} at URL: {url}")
        result = generate_key_press_script(url, output_file, key, element_locator, modifiers, browser, wait_time, verify_result)
        return result 