#!/usr/bin/env python
"""
MCP Tool: Robot Browser Select Option
Selects options in dropdown elements on a web page for Robot Framework through MCP.
"""

import os
import logging
import json
from typing import Dict, Any, Optional, Tuple, List, Union
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
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
    ElementNotInteractableException,
    NoSuchElementException,
    UnexpectedTagNameException
)

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

# Add import for AuthManager and BrowserManager
from src.utils.auth_manager import AuthManager
from src.mcp_tools.robot_browser_manager import BrowserManager

logger = logging.getLogger('robot_tool.browser_select_option')

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

def select_from_custom_dropdown(
    driver: webdriver.Chrome,
    dropdown_locator: str,
    option_text: str,
    wait_time: int = 5
) -> bool:
    """
    Select an option from a custom (non-select) dropdown.
    
    Args:
        driver: WebDriver instance
        dropdown_locator: Locator for the dropdown element
        option_text: Text of the option to select
        wait_time: Time to wait for elements in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Parse locator for dropdown
        dropdown_by, dropdown_value = parse_locator(dropdown_locator)
        
        # Click on the dropdown to open it
        dropdown = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable((dropdown_by, dropdown_value))
        )
        dropdown.click()
        
        # Wait a moment for dropdown to open
        import time
        time.sleep(0.5)
        
        # Try to find the option with matching text
        # First try direct child options
        options = driver.find_elements(By.XPATH, 
            f"//div[contains(@class, 'dropdown') or contains(@class, 'select')]//li[contains(text(), '{option_text}')]")
        
        # If not found, try more general approach
        if not options:
            options = driver.find_elements(By.XPATH, 
                f"//*[contains(@class, 'option') or contains(@class, 'item')][contains(text(), '{option_text}')]")
        
        # If still not found, look for any visible elements with matching text after dropdown click
        if not options:
            options = driver.find_elements(By.XPATH, f"//*[contains(text(), '{option_text}')]")
            # Filter to only visible elements
            options = [opt for opt in options if opt.is_displayed()]
        
        if options:
            # Click the first matching option
            options[0].click()
            return True
        else:
            logger.error(f"Could not find option '{option_text}' in custom dropdown")
            return False
            
    except Exception as e:
        logger.error(f"Error selecting from custom dropdown: {e}")
        return False

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def select_option(
    select_locator: str,
    option_values: Union[str, List[str]],
    url: Optional[str] = None,
    wait_time: int = 5,
    by_visible_text: bool = True,
    is_custom_dropdown: bool = False,
    need_login: bool = False,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    username_locator: Optional[str] = None,
    password_locator: Optional[str] = None,
    submit_locator: Optional[str] = None,
    success_indicator: Optional[str] = None
) -> Dict[str, Any]:
    """
    Select an option or multiple options in a dropdown element.
    
    Args:
        select_locator: Locator string for the dropdown element
        option_values: Value or list of values to select (text or value attribute)
        url: URL to navigate to (optional, if not provided, will use current page)
        wait_time: Time to wait for element to be available in seconds
        by_visible_text: Whether to select by visible text (True) or by value (False)
        is_custom_dropdown: Whether this is a custom (non-select) dropdown
        need_login: Whether login is required before selection
        login_url: URL of the login page if different from target URL
        username: Username for login
        password: Password for login
        username_locator: Locator for username field
        password_locator: Locator for password field
        submit_locator: Locator for submit button
        success_indicator: Optional element to verify successful login
        
    Returns:
        Dictionary with the selection operation result
    """
    result = {
        "select_locator": select_locator,
        "option_values": option_values,
        "url": url,
        "status": "success",
        "error": None,
        "login_status": None
    }
    
    # Convert single option to list for consistent handling
    if isinstance(option_values, str):
        option_values = [option_values]
    
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
        
        # Get browser instance from the manager
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
        by_type, by_value = parse_locator(select_locator)
        
        # Wait for select element to be present
        logger.info(f"Waiting for select element: {select_locator}")
        try:
            select_element = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((by_type, by_value))
            )
        except TimeoutException:
            result["status"] = "error"
            result["error"] = f"Select element not found with locator: {select_locator}"
            return result
        
        # Handle selection based on dropdown type
        if is_custom_dropdown:
            # Custom dropdown handling
            logger.info(f"Handling custom dropdown with {len(option_values)} options")
            
            # Only single selection is supported for custom dropdowns
            if len(option_values) > 1:
                logger.warning("Multiple selection not supported for custom dropdowns. Using first value.")
            
            success = select_from_custom_dropdown(driver, select_locator, option_values[0], wait_time)
            if not success:
                result["status"] = "error"
                result["error"] = f"Failed to select option '{option_values[0]}' from custom dropdown"
                return result
                
            result["selected_options"] = [option_values[0]]
            
        else:
            # Standard select element handling
            try:
                # Create a Select object
                select = Select(select_element)
                
                # Check if multi-select is allowed
                is_multiple = select.is_multiple
                result["is_multiple"] = is_multiple
                
                # Clear existing selections for multi-select
                if is_multiple and len(option_values) > 0:
                    select.deselect_all()
                
                # Perform selection(s)
                selected_options = []
                for value in option_values:
                    try:
                        if by_visible_text:
                            select.select_by_visible_text(value)
                        else:
                            select.select_by_value(value)
                        
                        selected_options.append(value)
                    except NoSuchElementException:
                        logger.warning(f"Option '{value}' not found in select element")
                        # Continue with other options even if one fails
                
                # Get all selected options
                all_selected = [option.text for option in select.all_selected_options]
                result["selected_options"] = all_selected
                
                # Log any options that couldn't be selected
                if len(selected_options) < len(option_values):
                    not_found = set(option_values) - set(selected_options)
                    logger.warning(f"These options were not found: {not_found}")
                    result["not_found_options"] = list(not_found)
                
            except UnexpectedTagNameException:
                # Element might be a custom dropdown, not a select
                logger.info("Element is not a standard select. Trying as custom dropdown.")
                
                # Fall back to custom dropdown handling
                success = select_from_custom_dropdown(driver, select_locator, option_values[0], wait_time)
                if not success:
                    result["status"] = "error"
                    result["error"] = f"Failed to select option '{option_values[0]}' from element (not a standard select)"
                    return result
                    
                result["selected_options"] = [option_values[0]]
                result["is_custom_dropdown"] = True
                
            except ElementNotInteractableException:
                result["status"] = "error"
                result["error"] = "Select element is not interactable"
                return result
            except Exception as e:
                result["status"] = "error"
                result["error"] = f"Error selecting option(s): {str(e)}"
                return result
        
        # Generate Robot Framework command for select
        selection_type = "visible text" if by_visible_text else "value"
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Select From Dropdown
    Open Browser    {url}    Chrome
    Maximize Browser Window
    Wait Until Element Is Visible    {select_locator}    timeout={wait_time}s
"""
        
        for value in option_values:
            robot_command += f"    Select From List By {selection_type.title()}    {select_locator}    {value}\n"
            
        robot_command += "    Close Browser\n"

        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error during select operation: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_select_script(
    url: str,
    output_file: str,
    select_locator: str,
    option_values: Union[str, List[str]],
    browser: str = "Chrome",
    by_visible_text: bool = True,
    is_custom_dropdown: bool = False,
    include_verification: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for selecting options in a dropdown.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        select_locator: Locator string for the dropdown element
        option_values: Value or list of values to select
        browser: Browser to use (default is Chrome)
        by_visible_text: Whether to select by visible text (True) or by value (False)
        is_custom_dropdown: Whether this is a custom (non-select) dropdown
        include_verification: Whether to include verification steps
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    # Convert single option to list for consistent handling
    if isinstance(option_values, str):
        option_values = [option_values]
        
    try:
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for selecting dropdown options
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}                 {url}
${{BROWSER}}             {browser}
${{SELECT_LOCATOR}}      {select_locator}
"""

        # Add option variables
        for i, value in enumerate(option_values):
            script_content += f"${{OPTION_{i+1}}}           {value}\n"

        script_content += """
*** Test Cases ***
Select Dropdown Options
    [Documentation]    Selects options from a dropdown element
    Open Browser    ${URL}    ${BROWSER}
    Maximize Browser Window
    
    # Wait for element to be ready
    Wait Until Element Is Visible    ${SELECT_LOCATOR}    timeout=10s
    
"""
        
        # Add selection commands based on dropdown type
        selection_type = "visible text" if by_visible_text else "value"
        
        if is_custom_dropdown:
            script_content += f"""    # Handle custom dropdown
    Click Element    ${{SELECT_LOCATOR}}
    Wait Until Element Is Visible    xpath=//*[contains(text(), "${{OPTION_1}}")]    timeout=5s
    Click Element    xpath=//*[contains(text(), "${{OPTION_1}}")]
"""
        else:
            # Standard select handling
            for i in range(len(option_values)):
                script_content += f"    Select From List By {selection_type.title()}    ${{SELECT_LOCATOR}}    ${{OPTION_{i+1}}}\n"

        if include_verification:
            script_content += """    
    # Add verification steps here based on your application's behavior
    # For example:
    # ${selected}=    Get Selected List Value    ${SELECT_LOCATOR}
    # Should Be Equal    ${selected}    ${OPTION_1}
    # Page Should Contain    Selection complete
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
        logger.error(f"Error generating select script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register browser select option tool with MCP."""
    
    @mcp.tool()
    async def robot_browser_select_option(
        select_locator: str,
        option_values: Union[str, List[str]],
        url: Optional[str] = None,
        wait_time: int = 5,
        by_visible_text: bool = True,
        is_custom_dropdown: bool = False,
        need_login: bool = False,
        login_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        username_locator: Optional[str] = None,
        password_locator: Optional[str] = None,
        submit_locator: Optional[str] = None,
        success_indicator: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Select an option or multiple options in a dropdown element.
        
        This tool allows selecting options in standard select elements and custom
        dropdown controls. It can optionally navigate to a URL first and handle
        authentication if needed.
        
        Args:
            select_locator: Locator string for the dropdown element
            option_values: Value or list of values to select (text or value attribute)
            url: URL to navigate to (optional, if not provided, will use current page)
            wait_time: Time to wait for element to be available in seconds
            by_visible_text: Whether to select by visible text (True) or by value (False)
            is_custom_dropdown: Whether this is a custom (non-select) dropdown
            need_login: Whether login is required before selection
            login_url: URL of the login page if different from target URL
            username: Username for login
            password: Password for login
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for submit button
            success_indicator: Optional element to verify successful login
            
        Returns:
            Dictionary with the selection operation result
        """
        logger.info(f"Selecting option(s) {option_values} in dropdown: {select_locator}")
        if need_login and url:
            logger.info("Authentication required for selection")
            
        return select_option(
            select_locator,
            option_values,
            url,
            wait_time,
            by_visible_text,
            is_custom_dropdown,
            need_login,
            login_url,
            username,
            password,
            username_locator,
            password_locator,
            submit_locator,
            success_indicator
        )
    
    @mcp.tool()
    async def robot_browser_generate_select_script(
        url: str,
        output_file: str,
        select_locator: str,
        option_values: Union[str, List[str]],
        browser: str = "Chrome",
        by_visible_text: bool = True,
        is_custom_dropdown: bool = False,
        include_verification: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for selecting options in a dropdown.
        
        This tool generates a Robot Framework script that navigates to a URL
        and selects options in a dropdown element.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            select_locator: Locator string for the dropdown element
            option_values: Value or list of values to select
            browser: Browser to use (default is Chrome)
            by_visible_text: Whether to select by visible text (True) or by value (False)
            is_custom_dropdown: Whether this is a custom (non-select) dropdown
            include_verification: Whether to include verification steps
            
        Returns:
            Dictionary with generation status and file path
        """
        return generate_select_script(
            url,
            output_file,
            select_locator,
            option_values,
            browser,
            by_visible_text,
            is_custom_dropdown,
            include_verification
        ) 