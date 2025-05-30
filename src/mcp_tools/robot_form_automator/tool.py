#!/usr/bin/env python
"""
MCP Tool: Robot Form Automator
Creates and executes Robot Framework tests for web form automation.
Supports optional authentication through central AuthManager.
"""

import os
import logging
import json
import time
import sys
import shutil
import subprocess
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# Import selenium for web scraping
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.chrome.service import Service

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

# Import shared browser manager
from src.mcp_tools.robot_browser_manager import BrowserManager

# Import auth manager for optional login
from src.utils.auth_manager import AuthManager

from src.utils.helpers import (
    run_robot_command,
    is_robot_file,
    find_robot_files
)
from src.config.config import (
    ROBOT_OUTPUT_DIR,
    DEFAULT_TIMEOUT
)

logger = logging.getLogger('robot_tool.form_automator')

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def create_form_automation_test(
    url: str,
    form_fields: Dict[str, Dict[str, str]],
    output_file: str,
    test_name: str = "Automate Form Submission",
    wait_success_element: Optional[str] = None,
    success_message: Optional[str] = None,
    browser: str = "Chrome",
    overwrite: bool = False,
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
    Create a Robot Framework test for automating a web form.
    
    Args:
        url: URL of the form to automate
        form_fields: Dictionary of form fields with their details (locator, value, type)
        output_file: Path to save the Robot test file
        test_name: Name for the test case
        wait_success_element: Element locator to wait for after submission
        success_message: Text to verify after submission
        browser: Browser to use for automation
        overwrite: Whether to overwrite an existing file
        need_login: Whether login is required before form automation
        login_url: URL of the login page if different from form URL
        username: Username for login
        password: Password for login
        username_locator: Locator for username field
        password_locator: Locator for password field
        submit_locator: Locator for submit button
        success_indicator: Optional element to verify successful login
        
    Returns:
        Dictionary with file path, content, and any error
    """
    result = {
        "file_path": None,
        "content": None,
        "error": None,
        "login_status": None
    }
    
    try:
        output_path = Path(output_file)
        
        # Check if file exists and overwrite is not enabled
        if output_path.exists() and not overwrite:
            return {
                "file_path": None,
                "content": None,
                "error": f"File already exists: {output_file}. Set overwrite=True to overwrite."
            }
            
        # Create directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate variables section
        variables = [
            f"${{URL}}                     {url}",
            f"${{BROWSER}}                 {browser}"
        ]
        
        for field_name, field_details in form_fields.items():
            var_name = field_name.upper().replace(" ", "_").replace("-", "_")
            locator = field_details.get("locator", "")
            variables.append(f"${{{var_name}_FIELD}}         {locator}")
            
        if wait_success_element:
            variables.append(f"${{SUCCESS_ELEMENT}}         {wait_success_element}")
            
        # Add login variables if needed
        if need_login:
            if login_url:
                variables.append(f"${{LOGIN_URL}}             {login_url}")
            else:
                variables.append(f"${{LOGIN_URL}}             {url}")
                
            if username and password and username_locator and password_locator and submit_locator:
                variables.append(f"${{USERNAME}}               {username}")
                variables.append(f"${{PASSWORD}}               {password}")
                variables.append(f"${{USERNAME_FIELD}}         {username_locator}")
                variables.append(f"${{PASSWORD_FIELD}}         {password_locator}")
                variables.append(f"${{LOGIN_BUTTON}}           {submit_locator}")
                
                if success_indicator:
                    variables.append(f"${{LOGIN_SUCCESS}}         {success_indicator}")
        
        # Generate test case steps
        test_steps = []
        
        # Add login step if needed
        if need_login:
            test_steps.append("Login To System")
            
        test_steps.append("Open Browser And Navigate To Form Page")
        test_steps.append("Fill Form Fields")
        
        # Add submit step
        submit_locator = next((details.get("locator") for name, details in form_fields.items() 
                              if details.get("type") == "submit"), None)
        if submit_locator:
            test_steps.append("Submit Form")
            
        # Add verification step if needed
        if wait_success_element or success_message:
            test_steps.append("Verify Form Submission Success")
            
        # Generate keywords
        keywords = []
        
        # Add login keyword if needed
        if need_login:
            login_steps = [
                "Open Browser    ${LOGIN_URL}    ${BROWSER}",
                "Maximize Browser Window"
            ]
            
            if username and password and username_locator and password_locator and submit_locator:
                login_steps.extend([
                    "Wait Until Page Contains Element    ${USERNAME_FIELD}    timeout=10s",
                    "Input Text    ${USERNAME_FIELD}    ${USERNAME}",
                    "Input Password    ${PASSWORD_FIELD}    ${PASSWORD}",
                    "Click Button    ${LOGIN_BUTTON}"
                ])
                
                if success_indicator:
                    login_steps.append(f"Wait Until Page Contains Element    ${{LOGIN_SUCCESS}}    timeout=10s")
                else:
                    login_steps.append("Sleep    2s")
            
            keywords.append({
                "name": "Login To System",
                "steps": login_steps
            })
        
        # Open browser keyword
        browse_steps = []
        if need_login:
            # If we've already logged in, just navigate to the form page
            browse_steps = [
                "Go To    ${URL}",
                "Wait Until Page Contains Element    " + next(iter(form_fields.values())).get("locator") + "    timeout=10s"
            ]
        else:
            # Otherwise open a new browser
            browse_steps = [
                "Open Browser    ${URL}    ${BROWSER}",
                "Maximize Browser Window",
                "Wait Until Page Contains Element    " + next(iter(form_fields.values())).get("locator") + "    timeout=10s"
            ]
            
        keywords.append({
            "name": "Open Browser And Navigate To Form Page",
            "steps": browse_steps
        })
        
        # Fill form fields keyword
        fill_steps = []
        for field_name, field_details in form_fields.items():
            var_name = field_name.upper().replace(" ", "_").replace("-", "_")
            field_type = field_details.get("type", "text")
            value = field_details.get("value", "")
            
            if field_type == "text" or field_type == "email" or field_type == "tel":
                fill_steps.append(f"Input Text    ${{{var_name}_FIELD}}    {value}")
            elif field_type == "password":
                fill_steps.append(f"Input Password    ${{{var_name}_FIELD}}    {value}")
            elif field_type == "checkbox":
                if value.lower() in ("true", "yes", "1"):
                    fill_steps.append(f"Select Checkbox    ${{{var_name}_FIELD}}")
            elif field_type == "radio":
                fill_steps.append(f"Select Radio Button    {field_name}    {value}")
            elif field_type == "select":
                fill_steps.append(f"Select From List By Value    ${{{var_name}_FIELD}}    {value}")
                
        keywords.append({
            "name": "Fill Form Fields",
            "steps": fill_steps
        })
        
        # Submit form keyword
        if submit_locator:
            submit_field_name = next((name for name, details in form_fields.items() 
                                    if details.get("type") == "submit"), "SUBMIT")
            submit_var_name = submit_field_name.upper().replace(" ", "_").replace("-", "_")
            
            keywords.append({
                "name": "Submit Form",
                "steps": [
                    f"Click Button    ${{{submit_var_name}_FIELD}}"
                ]
            })
            
        # Verification keyword
        if wait_success_element or success_message:
            verify_steps = []
            if wait_success_element:
                verify_steps.append("Wait Until Page Contains Element    ${SUCCESS_ELEMENT}    timeout=10s")
            if success_message:
                verify_steps.append(f"Page Should Contain    {success_message}")
                
            keywords.append({
                "name": "Verify Form Submission Success",
                "steps": verify_steps
            })
            
        # Build robot file content
        content = []
        
        # Settings section
        content.append("*** Settings ***")
        content.append(f"Documentation     Robot Framework test for automating form at {url}")
        content.append("Library           SeleniumLibrary")
        content.append("Test Teardown     Close All Browsers")
        content.append("")
        
        # Variables section
        content.append("*** Variables ***")
        content.extend(variables)
        content.append("")
        
        # Test cases section
        content.append("*** Test Cases ***")
        content.append(test_name)
        content.append(f"    [Documentation]    Automate form submission at {url}")
        content.append("    [Tags]    form    automation")
        for step in test_steps:
            content.append(f"    {step}")
        content.append("")
        
        # Keywords section
        content.append("*** Keywords ***")
        for keyword in keywords:
            content.append(keyword["name"])
            for step in keyword["steps"]:
                content.append(f"    {step}")
            content.append("")
            
        # Write content to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
            
        result["file_path"] = str(output_path)
        result["content"] = "\n".join(content)
        
        logger.info(f"Created form automation test at {output_path}")
        return result
        
    except Exception as e:
        error_msg = f"Error creating form automation test: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "file_path": None,
            "content": None,
            "error": error_msg
        }

def detect_form_structure(
    url: str, 
    wait_time: int = 20,
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
    Detect form structure from a URL using Selenium to visit the page
    and extract form field information.
    
    Args:
        url: URL containing the form to analyze
        wait_time: Time to wait for page to load in seconds
        need_login: Whether login is required before form detection
        login_url: URL of the login page if different from form URL
        username: Username for login
        password: Password for login
        username_locator: Locator for username field
        password_locator: Locator for password field
        submit_locator: Locator for submit button
        success_indicator: Optional element to verify successful login
        
    Returns:
        Dictionary with form structure and any errors
    """
    result = {
        "url": url,
        "form_fields": {},
        "error": None,
        "login_status": None
    }
    
    try:
        # Handle login if needed
        if need_login:
            # Check if already authenticated
            if not AuthManager.is_authenticated(url):
                if not all([username, password, username_locator, password_locator, submit_locator]):
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
                    result["error"] = f"Login failed: {login_result.get('message', 'Unknown error')}"
                    return result
            else:
                result["login_status"] = {"success": True, "message": "Already authenticated"}
        
        # Get browser instance from manager
        driver = BrowserManager.get_driver()
        
        # Navigate to the form URL
        current_url = driver.current_url
        if current_url != url:
            logger.info(f"Navigating to URL: {url}")
            driver.set_page_load_timeout(wait_time * 2)
            driver.get(url)
            
            # Wait for page to load
            try:
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for page to load: {url}")
        
        # Find all forms on the page
        forms = driver.find_elements(By.TAG_NAME, "form")
        
        if not forms:
            result["error"] = "No forms found on the page"
            return result
        
        # If multiple forms found, use the first one or the one with most elements
        form = max(forms, key=lambda f: len(f.find_elements(By.TAG_NAME, "input")))
        
        # Find all form elements
        form_fields = {}
        
        # Process input elements
        inputs = form.find_elements(By.TAG_NAME, "input")
        for input_elem in inputs:
            try:
                input_id = input_elem.get_attribute("id")
                input_name = input_elem.get_attribute("name")
                input_type = input_elem.get_attribute("type") or "text"
                input_placeholder = input_elem.get_attribute("placeholder") or ""
                
                # Generate a field name
                field_name = input_name or input_id or input_placeholder
                if not field_name:
                    field_name = f"field_{len(form_fields) + 1}"
                
                # Skip hidden fields
                if input_type == "hidden":
                    continue
                
                # Determine the best locator
                locator = None
                if input_id:
                    locator = f"id={input_id}"
                elif input_name:
                    locator = f"name={input_name}"
                else:
                    # Use XPath as last resort
                    locator = generate_xpath(input_elem)
                
                # Default value based on type
                default_value = ""
                if input_type == "checkbox" or input_type == "radio":
                    default_value = "true"
                elif input_type == "email":
                    default_value = "user@example.com"
                elif input_type == "password":
                    default_value = "Password123!"
                elif input_type == "tel":
                    default_value = "1234567890"
                
                # Add to form fields dictionary
                form_fields[field_name] = {
                    "locator": locator,
                    "type": input_type,
                    "value": default_value
                }
            except Exception as e:
                logger.warning(f"Error processing input element: {e}")
        
        # Process select elements
        selects = form.find_elements(By.TAG_NAME, "select")
        for select_elem in selects:
            try:
                select_id = select_elem.get_attribute("id")
                select_name = select_elem.get_attribute("name")
                
                # Generate a field name
                field_name = select_name or select_id
                if not field_name:
                    field_name = f"select_{len(form_fields) + 1}"
                
                # Determine the best locator
                locator = None
                if select_id:
                    locator = f"id={select_id}"
                elif select_name:
                    locator = f"name={select_name}"
                else:
                    # Use XPath as last resort
                    locator = generate_xpath(select_elem)
                
                # Get first option as default value
                options = select_elem.find_elements(By.TAG_NAME, "option")
                default_value = options[0].get_attribute("value") if options else ""
                
                # Add to form fields dictionary
                form_fields[field_name] = {
                    "locator": locator,
                    "type": "select",
                    "value": default_value
                }
            except Exception as e:
                logger.warning(f"Error processing select element: {e}")
        
        # Process textarea elements
        textareas = form.find_elements(By.TAG_NAME, "textarea")
        for textarea_elem in textareas:
            try:
                textarea_id = textarea_elem.get_attribute("id")
                textarea_name = textarea_elem.get_attribute("name")
                textarea_placeholder = textarea_elem.get_attribute("placeholder") or ""
                
                # Generate a field name
                field_name = textarea_name or textarea_id or textarea_placeholder
                if not field_name:
                    field_name = f"textarea_{len(form_fields) + 1}"
                
                # Determine the best locator
                locator = None
                if textarea_id:
                    locator = f"id={textarea_id}"
                elif textarea_name:
                    locator = f"name={textarea_name}"
                else:
                    # Use XPath as last resort
                    locator = generate_xpath(textarea_elem)
                
                # Add to form fields dictionary
                form_fields[field_name] = {
                    "locator": locator,
                    "type": "text",
                    "value": "Sample text"
                }
            except Exception as e:
                logger.warning(f"Error processing textarea element: {e}")
        
        # Find submit button
        submit_buttons = form.find_elements(By.XPATH, ".//button[@type='submit'] | .//input[@type='submit']")
        if not submit_buttons:
            # Try to find a button that looks like a submit button
            submit_buttons = form.find_elements(By.XPATH, ".//button[contains(translate(., 'SUBMIT', 'submit'), 'submit')]")
            
        if submit_buttons:
            submit_btn = submit_buttons[0]
            submit_id = submit_btn.get_attribute("id")
            submit_name = submit_btn.get_attribute("name")
            
            # Generate a field name
            field_name = "submit"
            
            # Determine the best locator
            locator = None
            if submit_id:
                locator = f"id={submit_id}"
            elif submit_name:
                locator = f"name={submit_name}"
            else:
                # Use XPath as last resort
                locator = generate_xpath(submit_btn)
            
            # Add to form fields dictionary
            form_fields["submit"] = {
                "locator": locator,
                "type": "submit",
                "value": ""
            }
        
        result["form_fields"] = form_fields
        
        if not form_fields:
            result["error"] = "No form fields detected on the page"
            result["form_detected"] = False
            
        return result
        
    except Exception as e:
        error_msg = f"Error detecting form structure: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "form_detected": False,
            "form_fields": {},
            "error": error_msg
        }
    finally:
        if driver:
            driver.quit()

def generate_xpath(element) -> str:
    """
    Generate XPath for an element based on its attributes or position.
    
    Args:
        element: Selenium WebElement
        
    Returns:
        XPath locator string
    """
    try:
        tag_name = element.tag_name
        
        # Try to create an xpath with an ID
        element_id = element.get_attribute("id")
        if element_id:
            return f"xpath=//{tag_name}[@id='{element_id}']"
        
        # Try with name attribute
        element_name = element.get_attribute("name")
        if element_name:
            return f"xpath=//{tag_name}[@name='{element_name}']"
        
        # Try with class attribute
        element_class = element.get_attribute("class")
        if element_class:
            return f"xpath=//{tag_name}[@class='{element_class}']"
        
        # Last resort - use position in the DOM
        # Warning: this is fragile and can break if the page structure changes
        return f"xpath=(//{tag_name})[1]"
    except Exception as e:
        logger.error(f"Error generating XPath: {e}")
        return "xpath=//body"

def run_form_automation_test(
    test_file: str,
    timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Run a form automation test and return results.
    
    Args:
        test_file: Path to the Robot test file
        timeout: Timeout for test execution in seconds
        
    Returns:
        Dictionary with test results and any error
    """
    result = {
        "success": False,
        "output": {},
        "logs": {},
        "error": None
    }
    
    try:
        # Check if file exists and is a Robot Framework file
        file_path_obj = Path(test_file)
        if not file_path_obj.exists():
            return {
                "success": False,
                "output": {},
                "logs": {},
                "error": f"File not found: {test_file}"
            }
        
        if not is_robot_file(file_path_obj):
            return {
                "success": False,
                "output": {},
                "logs": {},
                "error": f"Not a valid Robot Framework file: {test_file}"
            }
            
        # Set up output directory
        output_path = Path(ROBOT_OUTPUT_DIR)
        os.makedirs(output_path, exist_ok=True)
        
        # Generate unique names for output files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_xml = output_path / f"output_{timestamp}.xml"
        log_html = output_path / f"log_{timestamp}.html"
        report_html = output_path / f"report_{timestamp}.html"
        
        # Build command
        cmd = [
            "robot",
            "--outputdir", str(output_path),
            "--output", str(output_xml.name),
            "--log", str(log_html.name),
            "--report", str(report_html.name),
            str(file_path_obj)
        ]
        
        # Run the command
        logger.info(f"Running form automation test: {' '.join(cmd)}")
        success, stdout, stderr = run_robot_command(cmd, timeout=timeout)
        
        result["logs"] = {
            "output_xml": str(output_xml),
            "log_html": str(log_html),
            "report_html": str(report_html),
            "stdout": stdout,
            "stderr": stderr
        }
        
        result["success"] = success
        
        if not success:
            result["error"] = f"Form automation test execution failed: {stderr}"
            
        logger.info(f"Test execution completed with success={success}")
        return result
        
    except Exception as e:
        error_msg = f"Error running form automation test: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "output": {},
            "logs": {},
            "error": error_msg
        }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the robot_form_automator tool with the MCP server."""
    
    @mcp.tool()
    async def robot_form_detect(
        url: str,
        wait_time: int = 20,
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
        Detect form structure from a URL.
        
        This tool analyzes a web page to find form elements and extracts
        their details for automation.
        
        If login is required, the tool can handle authentication through the
        shared AuthManager to maintain session state across tools.
        
        Args:
            url: URL containing the form to analyze
            wait_time: Time to wait for page to load in seconds
            need_login: Whether login is required before form detection
            login_url: URL of the login page if different from form URL
            username: Username for login
            password: Password for login
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for submit button
            success_indicator: Optional element to verify successful login
            
        Returns:
            Dictionary with form structure and any errors
        """
        logger.info(f"Detecting form structure at URL: {url}")
        logger.info(f"Need login: {need_login}")
        
        return detect_form_structure(
            url, 
            wait_time,
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
    async def robot_form_create(
        url: str,
        form_fields: Dict[str, Dict[str, str]],
        output_file: str,
        test_name: str = "Automate Form Submission",
        wait_success_element: Optional[str] = None,
        success_message: Optional[str] = None,
        browser: str = "Chrome",
        overwrite: bool = False,
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
        Create a Robot Framework test for automating a web form.
        
        This tool generates a Robot Framework script that can be executed
        to automate filling and submitting a web form.
        
        If login is required, the tool can handle authentication through the
        shared AuthManager to maintain session state across tools.
        
        Args:
            url: URL of the form to automate
            form_fields: Dictionary of form fields with details (locator, value, type)
            output_file: Path to save the Robot test file
            test_name: Name for the test case
            wait_success_element: Element locator to wait for after submission
            success_message: Text to verify after submission
            browser: Browser to use for automation
            overwrite: Whether to overwrite an existing file
            need_login: Whether login is required before form automation
            login_url: URL of the login page if different from form URL
            username: Username for login
            password: Password for login
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for submit button
            success_indicator: Optional element to verify successful login
            
        Returns:
            Dictionary with file path, content, and any error
        """
        logger.info(f"Creating form automation test for URL: {url}")
        logger.info(f"Need login: {need_login}")
        
        return create_form_automation_test(
            url,
            form_fields,
            output_file,
            test_name,
            wait_success_element,
            success_message,
            browser,
            overwrite,
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
    async def robot_form_run(
        test_file: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Dict[str, Any]:
        """
        Run a form automation test and return results.
        
        Args:
            test_file: Path to the Robot test file
            timeout: Timeout for test execution in seconds
            
        Returns:
            Dictionary with test results and any error
        """
        logger.info(f"Running form automation test: {test_file}")
        
        result = run_form_automation_test(
            test_file=test_file,
            timeout=timeout
        )
        
        return result

    @mcp.tool()
    async def robot_form_extract_and_create(
        url: str,
        test_name: str = "Automate Form Submission",
        browser: str = "Chrome",
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Extract form structure and create a Robot Framework test script.
        
        Args:
            url: URL of the web page to analyze
            test_name: Name for the test case
            browser: Browser to use for automation
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with script content, suggested filename, and form field details
        """
        from src.mcp_tools.robot_form_locator.tool import extract_all_locators
        
        logger.info(f"Detecting form structure at URL: {url}")
        form_data = detect_form_structure(url, wait_time)
        
        if form_data.get("error"):
            return {
                "file_path": None,
                "content": None,
                "form_fields": {},
                "error": form_data["error"]
            }
        
        # Skip all file handling - we'll just generate the content and return it
        logger.info(f"Generating Robot Framework test script for URL: {url} (no file will be saved)")
        
        # Build variables section
        variables = [
            f"${{URL}}                     {url}",
            f"${{BROWSER}}                 {browser}"
        ]
        
        # Add form field variables
        for field_name, field_data in form_data.get("form_fields", {}).items():
            var_name = field_name.upper().replace(" ", "_").replace("-", "_")
            locator = field_data.get("locator", "")
            variables.append(f"${{{var_name}_FIELD}}         {locator}")
        
        # Add success indicator if any
        success_indicators = form_data.get("success_indicators", [])
        success_message = None
        success_element = None
        
        if success_indicators:
            # Use the first success indicator
            indicator = success_indicators[0]
            success_element = indicator.get("locator", "")
            success_message = indicator.get("text", "")
            
            if success_element:
                variables.append(f"${{SUCCESS_ELEMENT}}     {success_element}")
            if success_message:
                variables.append(f"${{SUCCESS_MESSAGE}}     {success_message}")
        
        # Build test cases section
        test_steps = [
            "Open Browser And Navigate To Form Page",
            "Fill Form Fields"
        ]
        
        if "submit" in form_data.get("form_fields", {}):
            test_steps.append("Submit Form")
            
            # Add verification if we have success indicators
            if success_element or success_message:
                test_steps.append("Verify Form Submission")
        
        # Build keywords section
        keywords = []
        
        # Open browser keyword
        first_field = next(iter(form_data.get("form_fields", {}).items()), (None, None))[0]
        if first_field:
            first_field_var = f"${{{first_field.upper().replace(' ', '_').replace('-', '_')}_FIELD}}"
            
            keywords.append({
                "name": "Open Browser And Navigate To Form Page",
                "steps": [
                    "Open Browser    ${URL}    ${BROWSER}",
                    "Maximize Browser Window",
                    f"Wait Until Page Contains Element    {first_field_var}    timeout=10s"
                ]
            })
        
        # Fill form fields keyword
        fill_steps = []
        for field_name, field_data in form_data.get("form_fields", {}).items():
            if field_name == "submit":
                continue
                
            var_name = field_name.upper().replace(" ", "_").replace("-", "_")
            field_type = field_data.get("type", "text")
            value = field_data.get("value", "")
            
            if field_type in ["text", "email", "tel"]:
                fill_steps.append(f"Input Text    ${{{var_name}_FIELD}}    {value}")
            elif field_type == "password":
                fill_steps.append(f"Input Password    ${{{var_name}_FIELD}}    {value}")
            elif field_type == "checkbox" and value.lower() in ["true", "yes", "on", "1"]:
                fill_steps.append(f"Select Checkbox    ${{{var_name}_FIELD}}")
            elif field_type == "radio":
                fill_steps.append(f"Select Radio Button    {field_name}    {value}")
            elif field_type == "select":
                # Determine the best way to select an option
                if value:
                    # Try to pick a strategy
                    if value.isdigit():
                        fill_steps.append(f"Select From List By Index    ${{{var_name}_FIELD}}    {value}")
                    else:
                        # Prefer by value, unless it looks like a display text
                        if " " in value or value.istitle():
                            fill_steps.append(f"Select From List By Label    ${{{var_name}_FIELD}}    {value}")
                        else:
                            fill_steps.append(f"Select From List By Value    ${{{var_name}_FIELD}}    {value}")
                else:
                    # Default to selecting the first non-empty option by index
                    fill_steps.append(f"Select From List By Index    ${{{var_name}_FIELD}}    1")
            elif field_type == "textarea":
                fill_steps.append(f"Input Text    ${{{var_name}_FIELD}}    {value}")
        
        if fill_steps:
            keywords.append({
                "name": "Fill Form Fields",
                "steps": fill_steps
            })
        
        # Submit form keyword
        if "submit" in form_data.get("form_fields", {}):
            submit_var = "SUBMIT_FIELD"
            keywords.append({
                "name": "Submit Form",
                "steps": [
                    f"Click Button    ${{{submit_var}}}"
                ]
            })
            
            # Add verification keyword if we have success indicators
            if success_element or success_message:
                verify_steps = []
                
                if success_element:
                    verify_steps.append(f"Wait Until Page Contains Element    ${{SUCCESS_ELEMENT}}    timeout=10s")
                if success_message:
                    verify_steps.append(f"Page Should Contain    ${{SUCCESS_MESSAGE}}")
                
                if not verify_steps:
                    verify_steps.append("Sleep    2s    # Wait for form submission to complete")
                
                keywords.append({
                    "name": "Verify Form Submission",
                    "steps": verify_steps
                })
        
        # Build the complete test file content
        content = []
        
        # Settings section
        content.append("*** Settings ***")
        content.append(f"Documentation     Robot Framework test for automating form at {url}")
        content.append("Library           SeleniumLibrary")
        content.append("Test Teardown     Close All Browsers")
        content.append("")
        
        # Variables section
        content.append("*** Variables ***")
        for variable in variables:
            content.append(variable)
        content.append("")
        
        # Test Cases section
        content.append("*** Test Cases ***")
        content.append(test_name)
        content.append(f"    [Documentation]    Automate form submission at {url}")
        content.append("    [Tags]    form    automation    regression")
        for step in test_steps:
            content.append(f"    {step}")
        content.append("")
        
        # Keywords section
        content.append("*** Keywords ***")
        for keyword in keywords:
            content.append(keyword["name"])
            for step in keyword["steps"]:
                content.append(f"    {step}")
            content.append("")
        
        # Create the full content as a string
        full_content = "\n".join(content)
        
        # Generate a suggested filename
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace("www.", "").split(":")[0]
        suggested_filename = f"{domain}_form_test.robot"
        
        # Just return the content without saving to file
        return {
            "content": full_content,
            "suggested_filename": suggested_filename,
            "form_fields": form_data.get("form_fields", {}),
            "message": "Test script generated successfully. Save this content to a .robot file on your local machine."
        } 